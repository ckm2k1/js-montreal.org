# -*- coding: utf-8 -*-
#
# test_process_agent.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from __future__ import absolute_import

import uuid
import time
import threading
from flask import json
from mock import patch
from tests import BaseTestCase
from tests.utils import MockJob
from borgy_process_agent import ProcessAgent
from borgy_process_agent.job import State, Restart
from borgy_process_agent.utils import get_now_isoformat


class TestProcessAgent(BaseTestCase):
    """ProcessAgent integration test"""

    def test_pa_check_get_job_by_id(self):
        """Test case for get_job_by_id
        """
        # Insert a fake job in ProcessAgent
        simple_job = MockJob(name='gsm').get_job()
        jobs = [simple_job]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        job = self._pa.get_job_by_id(simple_job.id)
        self.assertIsNotNone(job)
        self.assertEqual(job.name, 'gsm')

        job = self._pa.get_job_by_id('my-id')
        self.assertIsNone(job)

    def test_pa_check_get_jobs_by_name(self):
        """Test case for get_jobs_by_name
        """
        # Insert a fake job in ProcessAgent
        simple_job = MockJob(name='gsm').get_job()
        jobs = [simple_job]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        job = self._pa.get_jobs_by_name(simple_job.name)
        self.assertEqual(len(job), 1)
        self.assertEqual(job[0].name, 'gsm')

        job = self._pa.get_jobs_by_name('my-name')
        self.assertEqual(len(job), 0)

    def test_pa_check_get_jobs_by_state(self):
        """Test case for get_jobs_by_state
        """
        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        jobs = self._pa.get_jobs_by_state(State.QUEUED.value)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].name, 'gsm1')
        self.assertEqual(jobs[1].name, 'gsm1')

        jobs = self._pa.get_jobs_by_state(State.RUNNING.value)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].name, 'gsm3')

        jobs = self._pa.get_jobs_by_state(State.SUCCEEDED.value)
        self.assertEqual(len(jobs), 0)

    def test_pa_kill_job(self):
        """Test case for kill_job
        """
        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.SUCCEEDED.value).get_job()
        simple_job2 = MockJob(name='gsm2', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Mock
        count_call = [0]

        def mock_jobs_delete(s, job_id, user):
            count_call[0] += 1
            simple_job2.state = State.CANCELLING.value
            return simple_job2

        mock_method = 'borgy_job_service_client.api.jobs_api.JobsApi.v1_jobs_job_id_delete'
        job_service_call_delete = patch(mock_method, mock_jobs_delete).start()

        # Should not call job_service
        job, is_updated = self._pa.kill_job('random')
        self.assertEqual(job, None)
        self.assertEqual(is_updated, False)
        self.assertEqual(count_call[0], 0)

        # Should not call job_service
        job, is_updated = self._pa.kill_job(simple_job.id)
        self.assertEqual(job, simple_job)
        self.assertEqual(is_updated, False)
        self.assertEqual(count_call[0], 0)

        # Should call job_service
        job, is_updated = self._pa.kill_job(simple_job2.id)
        self.assertEqual(job.id, simple_job2.id)
        self.assertEqual(is_updated, True)
        # Test if state is directly updated to CANCELLING
        self.assertEqual(job.state, State.CANCELLING.value)
        job = self._pa.get_job_by_id(simple_job2.id)
        self.assertEqual(job.state, State.CANCELLING.value)

        # Call a second time should not call job service
        job, is_updated = self._pa.kill_job(simple_job2.id)
        self.assertEqual(job.id, simple_job2.id)
        self.assertEqual(is_updated, False)
        self.assertEqual(job.state, State.CANCELLING.value)
        job = self._pa.get_job_by_id(simple_job2.id)
        self.assertEqual(job.state, State.CANCELLING.value)
        # Test if job service was called only one time
        self.assertEqual(count_call[0], 1)
        del job_service_call_delete

    def test_pa_rerun_job(self):
        """Test case for rerun_job
        """
        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.SUCCEEDED.value).get_job()
        simple_job2 = MockJob(name='gsm2', state=State.FAILED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Should not add job_id in rerun list
        job, is_updated = self._pa.rerun_job('random')
        self.assertEqual(job, None)
        self.assertEqual(is_updated, False)

        # Should not add job_id in rerun list
        job, is_updated = self._pa.rerun_job(simple_job.id)
        self.assertEqual(job, simple_job)
        self.assertEqual(is_updated, False)

        # Should add job_id in rerun list
        job, is_updated = self._pa.rerun_job(simple_job2.id)
        self.assertEqual(job.id, simple_job2.id)
        self.assertEqual(is_updated, True)
        # Test if job is added in job list to rerun
        self.assertEqual(self._pa.get_jobs_to_rerun(), [simple_job2.id])
        self.assertEqual(job.state, State.FAILED.value)
        job = self._pa.get_job_by_id(simple_job2.id)
        self.assertEqual(job.state, State.FAILED.value)

        # Call a second time should add job_id in rerun list
        job, is_updated = self._pa.rerun_job(simple_job2.id)
        self.assertEqual(job.id, simple_job2.id)
        self.assertEqual(is_updated, False)
        self.assertEqual(self._pa.get_jobs_to_rerun(), [simple_job2.id])

        # Check rerun list provided by PA
        self._pa.set_callback_jobs_provider(lambda pa: [])
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('rerun', jobs_ops)
        jobs_to_rerun = jobs_ops['rerun']
        self.assertEqual(jobs_to_rerun, [simple_job2.id])

        # Governor push job updated
        simple_job2.state = State.QUEUING.value
        simple_job2.runs.append({
            'id': str(uuid.uuid4()),
            'jobId': simple_job2.id,
            'createdOn': get_now_isoformat(),
            'state': State.QUEUING.value,
            'info': {},
            'ip': '127.0.0.1',
            'nodeName': 'local',
        })
        jobs = [simple_job2]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Test if job is removed from job list to rerun
        self.assertEqual(self._pa.get_jobs_to_rerun(), [])
        job = self._pa.get_job_by_id(simple_job2.id)
        self.assertEqual(job.state, State.QUEUING.value)

        # Call a second time should not add job in rerun list
        job, is_updated = self._pa.rerun_job(simple_job2.id)
        self.assertEqual(job.id, simple_job2.id)
        self.assertEqual(is_updated, False)
        self.assertEqual(job.state, State.QUEUING.value)
        job = self._pa.get_job_by_id(simple_job2.id)
        self.assertEqual(job.state, State.QUEUING.value)

    def test_pa_check_callback_contains_process_agent(self):
        """Test case for get_jobs_by_state
        """
        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        def get_new_jobs(pa):
            jobs = pa.get_jobs()
            self.assertEquals(len(jobs), 3)
            return {
                'name': 'my-job'
            }
        self._pa.set_callback_jobs_provider(get_new_jobs)
        self.client.open('/v1/jobs', method='GET')

    def test_start_stop_server(self):
        """Test case to test start and stop server application
        """
        # Update port
        count_call = [0]

        def start():
            self._pa.start()
            count_call[0] += 1

        # start server in thread
        app = threading.Thread(name='Web App', target=start)
        app.setDaemon(True)
        app.start()
        # wait 1s
        time.sleep(1)
        # Stop server
        self._pa.stop()
        # wait 1s
        time.sleep(1)
        # Start should go to the next instruction
        self.assertEqual(count_call[0], 1)

    def test_pa_set_autokill_twice(self):
        """Test case for setting autokill multiple time
        """
        list_autokill = [c for c in self._pa._observable_jobs_update._callbacks
                         if c['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 0)
        self._pa.set_autokill(True)
        list_autokill = [c for c in self._pa._observable_jobs_update._callbacks
                         if c['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 1)
        self._pa.set_autokill(True)
        list_autokill = [c for c in self._pa._observable_jobs_update._callbacks
                         if c['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 1)

    def test_pa_disable_autokill(self):
        """Test case to disable autokill
        """
        list_autokill = [c for c in self._pa._observable_jobs_update._callbacks
                         if c['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 0)
        self._pa.set_autokill(True)
        list_autokill = [c for c in self._pa._observable_jobs_update._callbacks
                         if c['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 1)
        self._pa.set_autokill(False)
        list_autokill = [c for c in self._pa._observable_jobs_update._callbacks
                         if c['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 0)

    def test_pa_autokill(self):
        """Autokill test case
        """
        count_call = [0, 0]

        def mock_borgy_process_agent_start(s):
            count_call[0] += 1

        def mock_borgy_process_agent_stop(s):
            count_call[1] += 1

        mock_method = 'borgy_process_agent.modes.borgy.ProcessAgent.start'
        borgy_process_agent_start = patch(mock_method, mock_borgy_process_agent_start).start()
        mock_method = 'borgy_process_agent.modes.borgy.ProcessAgent.stop'
        borgy_process_agent_stop = patch(mock_method, mock_borgy_process_agent_stop).start()

        def get_stop_job(pa):
            return None

        self._pa.clear_jobs_in_creation()
        self._pa.set_callback_jobs_provider(get_stop_job)

        self._pa.set_autokill(True)
        self._pa.start()
        self.assertEqual(count_call, [1, 0])

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(count_call, [1, 0])
        self.assertEqual(self._pa.is_shutdown(), False)

        # Update jobs in ProcessAgent
        simple_job.state = State.RUNNING.value
        simple_job2.state = State.RUNNING.value
        simple_job3.state = State.FAILED.value
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(count_call, [1, 0])
        self.assertEqual(self._pa.is_shutdown(), False)

        # Governor call /v1/jobs to get jobs to schedule.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 204, 'Should return 204. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 0])

        # Update jobs in ProcessAgent
        simple_job.state = State.CANCELLED.value
        simple_job2.state = State.SUCCEEDED.value
        jobs = [simple_job, simple_job2]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        # self._pa.stop() should be call
        self.assertEqual(count_call, [1, 1])

        del borgy_process_agent_start
        del borgy_process_agent_stop

    def test_pa_autokill_after_finish(self):
        """Autokill test case after all job are finished
        """
        count_call = [0, 0]

        def mock_borgy_process_agent_start(s):
            count_call[0] += 1

        def mock_borgy_process_agent_stop(s):
            count_call[1] += 1

        mock_method = 'borgy_process_agent.modes.borgy.ProcessAgent.start'
        borgy_process_agent_start = patch(mock_method, mock_borgy_process_agent_start).start()
        mock_method = 'borgy_process_agent.modes.borgy.ProcessAgent.stop'
        borgy_process_agent_stop = patch(mock_method, mock_borgy_process_agent_stop).start()

        def get_no_job(pa):
            return []

        def get_stop_job(pa):
            return None

        self._pa.clear_jobs_in_creation()
        self._pa.set_callback_jobs_provider(get_no_job)

        self._pa.set_autokill(True)
        self._pa.start()
        self.assertEqual(count_call, [1, 0])

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(count_call, [1, 0])
        self.assertEqual(self._pa.is_shutdown(), False)

        # Update jobs in ProcessAgent
        simple_job.state = State.RUNNING.value
        simple_job2.state = State.RUNNING.value
        simple_job3.state = State.FAILED.value
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(count_call, [1, 0])
        self.assertEqual(self._pa.is_shutdown(), False)
        self.assertEqual(count_call, [1, 0])

        # Governor call /v1/jobs to get jobs to schedule.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), False)

        # Update jobs in ProcessAgent
        simple_job.state = State.CANCELLED.value
        simple_job2.state = State.SUCCEEDED.value
        jobs = [simple_job, simple_job2]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(count_call, [1, 0])

        # Update callback
        self._pa.set_callback_jobs_provider(get_stop_job)

        # Governor call /v1/jobs to get jobs to schedule.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 204, 'Should return 204. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        # self._pa.stop() should be call
        self.assertEqual(count_call, [1, 1])

        del borgy_process_agent_start
        del borgy_process_agent_stop

    def test_pa_reset_is_ready(self):
        """Reset test case: always ready
        """
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 418, 'Should return 418. Response body is : ' + response.data.decode('utf-8'))

        # Define callback for PA. Should be ready.
        self._pa.set_callback_jobs_provider(lambda pa: [])
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Reset PA
        self._pa.reset()

        # Define callback for PA. Should be always ready.
        self._pa.set_callback_jobs_provider(lambda pa: [])
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

    def test_pa_reset(self):
        """Reset test case
        """
        def get_stop_job(pa):
            return None

        self._pa.clear_jobs_in_creation()
        # Shutdown PA on next call
        self._pa.set_callback_jobs_provider(get_stop_job)

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        jobs = [simple_job]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), False)
        self.assertEqual(len(self._pa.get_jobs()), 1)

        # Shutdown PA
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 204, 'Should return 204. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(len(self._pa.get_jobs()), 1)

        # Reset PA
        self._pa.reset()
        self.assertEqual(self._pa.is_shutdown(), False)
        self.assertEqual(len(self._pa.get_jobs()), 0)

    def test_pa_autorerun_interrupted_jobs_off(self):
        """Test case when autorerun for interrupted jobs is disabled
        """

        def get_stop_job(pa):
            return []

        self._pa.clear_jobs_in_creation()
        self._pa.set_callback_jobs_provider(get_stop_job)

        self._pa.set_autorerun_interrupted_jobs(False)

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.RUNNING.value)

        # Update jobs in ProcessAgent
        simple_job.state = State.RUNNING.value
        simple_job2.state = State.RUNNING.value
        simple_job3.state = State.INTERRUPTED.value
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.INTERRUPTED.value)

        # Governor call /v1/jobs to get jobs to schedule and to rerun.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 204. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('rerun', jobs_ops)
        jobs_to_rerun = jobs_ops['rerun']
        self.assertEqual(jobs_to_rerun, [])

    def test_pa_autorerun_interrupted_jobs_on(self):
        """Test case when autorerun for interrupted jobs is enabled
        """

        def get_stop_job(pa):
            return []

        self._pa.clear_jobs_in_creation()
        self._pa.set_callback_jobs_provider(get_stop_job)

        self._pa.set_autorerun_interrupted_jobs(True)

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.RUNNING.value)

        # Update jobs in ProcessAgent
        simple_job.state = State.RUNNING.value
        simple_job2.state = State.RUNNING.value
        simple_job3.state = State.INTERRUPTED.value
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.INTERRUPTED.value)

        # Governor call /v1/jobs to get jobs to schedule and to rerun.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('rerun', jobs_ops)
        jobs_to_rerun = jobs_ops['rerun']
        self.assertEqual(jobs_to_rerun, [job.id])

    def test_pa_autorerun_interrupted_jobs_off_with_shutdown(self):
        """Test case when autorerun for interrupted jobs is disabled and PA is shutting down
        """

        def get_stop_job(pa):
            return None

        self._pa.clear_jobs_in_creation()
        self._pa.set_callback_jobs_provider(get_stop_job)

        self._pa.set_autorerun_interrupted_jobs(False)

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.RUNNING.value)

        # Update jobs in ProcessAgent
        simple_job.state = State.RUNNING.value
        simple_job2.state = State.RUNNING.value
        simple_job3.state = State.INTERRUPTED.value
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.INTERRUPTED.value)

        # Governor call /v1/jobs to get jobs to schedule and to rerun.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 204, 'Should return 204. Response body is : ' + response.data.decode('utf-8'))

    def test_pa_autorerun_interrupted_jobs_on_with_shutdown(self):
        """Test case when autorerun for interrupted jobs is enabled and PA is shutting down
        """

        def get_stop_job(pa):
            return None

        self._pa.clear_jobs_in_creation()
        self._pa.set_callback_jobs_provider(get_stop_job)

        self._pa.set_autorerun_interrupted_jobs(True)

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.RUNNING.value)

        # Update jobs in ProcessAgent
        simple_job.state = State.RUNNING.value
        simple_job2.state = State.RUNNING.value
        simple_job3.state = State.INTERRUPTED.value
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.INTERRUPTED.value)

        # Governor call /v1/jobs to get jobs to schedule and to rerun.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('rerun', jobs_ops)
        jobs_to_rerun = jobs_ops['rerun']
        self.assertEqual(jobs_to_rerun, [job.id])

    def test_raise_jobspec_restartable(self):
        """Test case when jobspec is restartable
        """

        def get_restartable_job(pa):
            return {
                'restart': Restart.ON_INTERRUPTION.value
            }

        self._pa.set_callback_jobs_provider(get_restartable_job)

        # Governor call /v1/jobs to get jobs to schedule and to rerun.
        response = self.client.open('/v1/jobs', method='GET')
        # Should return 400 due to restartable job
        self.assertStatus(response, 400, 'Should return 400. Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
