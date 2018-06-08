# -*- coding: utf-8 -*-
#
# test_process_agent.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from __future__ import absolute_import

import time
import threading
from flask import json
from mock import patch
from tests import BaseTestCase
from tests.utils import MockJob
from borgy_process_agent.job import State
from borgy_process_agent.config import Config


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

    def test_pa_check_get_job_by_state(self):
        """Test case for get_job_by_state
        """
        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        jobs = self._pa.get_job_by_state(State.QUEUED.value)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].name, 'gsm1')
        self.assertEqual(jobs[1].name, 'gsm1')

        jobs = self._pa.get_job_by_state(State.RUNNING.value)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].name, 'gsm3')

        jobs = self._pa.get_job_by_state(State.SUCCEEDED.value)
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
            return simple_job2.to_dict()

        mock_method = 'borgy_job_service_client.api.jobs_api.JobsApi.v1_jobs_job_id_delete'
        job_service_call_delete = patch(mock_method, mock_jobs_delete).start()

        # Should not call job_service
        job = self._pa.kill_job('random')
        self.assertEqual(job, None)
        self.assertEqual(count_call[0], 0)

        # Should not call job_service
        job = self._pa.kill_job(simple_job.id)
        self.assertEqual(job, simple_job)
        self.assertEqual(count_call[0], 0)

        job = self._pa.kill_job(simple_job2.id)
        self.assertEqual(job.id, simple_job2.id)
        # Test if state is directly updated to CANCELLING
        self.assertEqual(job.state, State.CANCELLING.value)
        job = self._pa.get_job_by_id(simple_job2.id)
        self.assertEqual(job.state, State.CANCELLING.value)

        # Call a second time should not call job service
        job = self._pa.kill_job(simple_job2.id)
        self.assertEqual(job.id, simple_job2.id)
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

        # Mock
        count_call = [0]

        def mock_jobs_rerun(s, job_id):
            count_call[0] += 1
            return simple_job2.to_dict()

        mock_method = 'borgy_job_service_client.api.jobs_api.JobsApi.v1_jobs_job_id_rerun_put'
        job_service_call_rerun = patch(mock_method, mock_jobs_rerun).start()

        # Should not call job_service
        job = self._pa.rerun_job('random')
        self.assertEqual(job, None)
        self.assertEqual(count_call[0], 0)

        # Should not call job_service
        job = self._pa.kill_job(simple_job.id)
        self.assertEqual(job, simple_job)
        self.assertEqual(count_call[0], 0)

        job = self._pa.rerun_job(simple_job2.id)
        self.assertEqual(job.id, simple_job2.id)
        # Test if state is directly updated to QUEUING
        self.assertEqual(job.state, State.QUEUING.value)
        job = self._pa.get_job_by_id(simple_job2.id)
        self.assertEqual(job.state, State.QUEUING.value)

        # Call a second time should not call job service
        job = self._pa.rerun_job(simple_job2.id)
        self.assertEqual(job.id, simple_job2.id)
        self.assertEqual(job.state, State.QUEUING.value)
        job = self._pa.get_job_by_id(simple_job2.id)
        self.assertEqual(job.state, State.QUEUING.value)
        # Test if job service was called only one time
        self.assertEqual(count_call[0], 1)
        del job_service_call_rerun

    def test_pa_check_callback_contains_process_agent(self):
        """Test case for get_job_by_state
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
        Config.set('port', 9652)
        count_call = [0]

        def start():
            self._pa.start()
            count_call[0] += 1

        # start server in thread
        app = threading.Thread(name='Web App', target=start)
        app.setDaemon(True)
        app.start()
        # wait 2s
        time.sleep(1)
        # Stop server
        self._pa.stop()
        # Start should go to the next instruction
        self.assertEqual(count_call[0], 1)

    def test_pa_autokill(self):
        """Autokill test case
        """
        count_call = [0, 0]

        def mock_borgy_process_agent_start(s):
            count_call[0] += 1

        def mock_borgy_process_agent_stop(s):
            count_call[1] += 1

        mock_method = 'borgy_process_agent.ProcessAgent.start'
        borgy_process_agent_start = patch(mock_method, mock_borgy_process_agent_start).start()
        mock_method = 'borgy_process_agent.ProcessAgent.stop'
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


if __name__ == '__main__':
    import unittest
    unittest.main()
