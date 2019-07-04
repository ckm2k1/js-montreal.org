import datetime
import http.client
import socket
import threading
import time
import uuid

import dateutil.parser
from prometheus_client import generate_latest
from prometheus_client.core import REGISTRY

from borgy_process_agent.controllers.version_controller import borgy_process_agent_version

from borgy_process_agent_api_server.models.job_runs import JobRuns
from borgy_process_agent.metrics import expose_metrics
from borgy_process_agent.metrics.utils import sanitize_exception_message, type_name
from borgy_process_agent.metrics.process_agent import job_run_duration

from tests import BaseTestCase
from tests.utils import MockJob


# Python does not provide an API to stop a thread, and the Prometheus
# client library doesn't provide this capability for start_http_server
# so the following code will allocate a new port for use with expose_metrics.
def get_test_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    _, port = sock.getsockname()
    sock.close()
    return port


class TestMetrics(BaseTestCase):
    """
    Metrics tests
    """

    def test_type_name(self):
        job = MockJob(name='test').get_job()
        self.assertEqual(type_name(job), "borgy_process_agent_api_server.models.job.Job")

    def test_sanitize_exception_message_single(self):
        single_line_error = ValueError("single    line\terror\t message")
        self.assertEqual(sanitize_exception_message(single_line_error), "single line error message")

    def test_sanitize_exception_message_multi(self):
        multi_line_error = ValueError("""multi
        line                             error
        message
        """)
        self.assertEqual(sanitize_exception_message(multi_line_error), "multi line error message")

        multi_line_error_esc = ValueError("multi\rline\r\n error\n\r\tmessage\t")
        self.assertEqual(sanitize_exception_message(multi_line_error_esc), "multi line error message")

    def test_job_run_duration(self):
        created_on = '2018-11-27T19:30:00+00:00'
        started_on = '2018-11-27T19:36:27+00:00'
        ended_on = '2018-11-27T19:40:27+00:00'
        now = dateutil.parser.isoparse(started_on) + datetime.timedelta(seconds=7357)

        test_cases = {
            'never-started': {
                'started_on': None,
                'ended_on': None,
                'expected': 0,
            },
            'started-to-now': {
                'started_on': started_on,
                'ended_on': None,
                'expected': 7357,
            },
            'started-to-ended': {
                'started_on': started_on,
                'ended_on': ended_on,
                'expected': 240,
            }
        }

        for name, test_case in test_cases.items():
            job_run_dict = {
                'id': str(uuid.uuid4()),
                'jobId': str(uuid.uuid4()),
                'createdOn': created_on,
                'startedOn': test_case['started_on'],
                'endedOn': test_case['ended_on'],
                'state': 'QUEUING',
                'info': {},
                'ip': '127.0.0.1',
                'nodeName': 'local',
            }

            job_run = JobRuns.from_dict(job_run_dict)
            duration = job_run_duration(job_run, now)
            self.assertEqual(duration.seconds, test_case['expected'], name)

    def test_expose_metrics(self):
        expected_lines = [
            'borgy_process_agent_info{{version="{}"}} 1.0'.format(borgy_process_agent_version),
            'borgy_process_agent_ready 0.0',
            'borgy_process_agent_shutdown 0.0',
            'borgy_process_agent_last_update_timestamp_seconds 0.0',
            'http_request_inprogress 0.0',
        ]

        port = get_test_port()
        expose_metrics(self._pa, port)

        metrics = generate_latest(REGISTRY).decode()
        for line in expected_lines:
            self.assertTrue(line in metrics, line)

        # Fetch metrics from the exposed service the inhuman way!
        conn = http.client.HTTPConnection('localhost', port)
        conn.request("GET", "/")
        metrics_response = conn.getresponse().read().decode()
        for line in expected_lines:
            self.assertTrue(line in metrics_response, line)

    def test_jobs_update_callback(self):
        def mocked_now():
            return dateutil.parser.isoparse('2019-05-11T20:48:00+00:00')

        # disable PA metrics on start
        self._pa._options['metrics_enabled'] = False

        # start server in thread
        app = threading.Thread(name='Web App', target=self._pa.start)
        app.setDaemon(True)
        app.start()

        time.sleep(1)

        port = get_test_port()
        expose_metrics(self._pa, port, get_now=mocked_now)

        fixture = self._base_dir + '/fixtures/process_agent_status.json'
        response = self.client.open('/v1/jobs', method='PUT',
                                    content_type='application/json', data=open(fixture).read())
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Waiting for end of processing jobs update
        self._pa.join_pushed_jobs()

        # Shutdown the server
        self._pa.stop()

        expected_lines = [
            'borgy_process_agent_jobs{state="QUEUING"} 0.0',
            'borgy_process_agent_jobs{state="QUEUED"} 0.0',
            'borgy_process_agent_jobs{state="RUNNING"} 5.0',
            'borgy_process_agent_jobs{state="CANCELLING"} 0.0',
            'borgy_process_agent_jobs{state="CANCELLED"} 0.0',
            'borgy_process_agent_jobs{state="SUCCEEDED"} 92.0',
            'borgy_process_agent_jobs{state="FAILED"} 3.0',
            'borgy_process_agent_jobs{state="INTERRUPTED"} 0.0',

            'borgy_process_agent_jobs_duration_seconds{state="QUEUING"} 0.0',
            'borgy_process_agent_jobs_duration_seconds{state="QUEUED"} 0.0',
            'borgy_process_agent_jobs_duration_seconds{state="RUNNING"} 535818.0',
            'borgy_process_agent_jobs_duration_seconds{state="CANCELLING"} 0.0',
            'borgy_process_agent_jobs_duration_seconds{state="CANCELLED"} 0.0',
            'borgy_process_agent_jobs_duration_seconds{state="SUCCEEDED"} 1.700096e+06',
            'borgy_process_agent_jobs_duration_seconds{state="FAILED"} 0.0',
            'borgy_process_agent_jobs_duration_seconds{state="INTERRUPTED"} 309177.948519',

            'http_request_total{endpoint="/v1/jobs",method="PUT",status="200"} 1.0',
            'http_request_duration_seconds_bucket{endpoint="/v1/jobs",le="+Inf",method="PUT"}',
            'http_request_duration_seconds_count{endpoint="/v1/jobs",method="PUT"}',
            'http_request_duration_seconds_sum{endpoint="/v1/jobs",method="PUT"}',
        ]

        metrics = generate_latest(REGISTRY).decode()
        for line in expected_lines:
            self.assertTrue(line in metrics, line)

        self.assertTrue(
            'borgy_process_agent_last_update_timestamp_seconds' in metrics,
            'last update timestamps should be defined as a metric')

        self.assertTrue(
            'borgy_process_agent_last_update_timestamp_seconds 0.0' not in metrics,
            'last update timestamps should have be non-zero')
