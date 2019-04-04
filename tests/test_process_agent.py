# -*- coding: utf-8 -*-
#
# test_process_agent.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from __future__ import absolute_import

import os
import copy
import uuid
import time
import threading
from flask import json
from mock import patch
from tests import BaseTestCase
from tests.utils import MockJob
from borgy_process_agent import ProcessAgent, ProcessAgentMode
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

    def test_pa_set_callbacks_are_callable(self):
        with self.assertRaises(ValueError):
            self._pa.set_callback_jobs_provider(1)

        with self.assertRaises(ValueError):
            self._pa.subscribe_jobs_update(1)

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
                         if c[1]['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 0)
        self._pa.set_autokill(True)
        list_autokill = [c for c in self._pa._observable_jobs_update._callbacks
                         if c[1]['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 1)
        self._pa.set_autokill(True)
        list_autokill = [c for c in self._pa._observable_jobs_update._callbacks
                         if c[1]['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 1)

    def test_pa_disable_autokill(self):
        """Test case to disable autokill
        """
        list_autokill = [c for c in self._pa._observable_jobs_update._callbacks
                         if c[1]['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 0)
        self._pa.set_autokill(True)
        list_autokill = [c for c in self._pa._observable_jobs_update._callbacks
                         if c[1]['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 1)
        self._pa.set_autokill(False)
        list_autokill = [c for c in self._pa._observable_jobs_update._callbacks
                         if c[1]['callback'] == ProcessAgent.pa_check_autokill]
        self.assertEqual(len(list_autokill), 0)

    def test_pa_autokill(self):
        """Autokill test case
        """
        count_call = [0, 0]

        def mock_borgy_process_agent_start(s):
            count_call[0] += 1

        def mock_borgy_process_agent_stop(s, **kwargs):
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

        # Set callback after PUT due to the call to get_jobs_to_create in a thread
        self._pa.set_callback_jobs_provider(get_stop_job)

        # # Governor call /v1/jobs to get jobs to schedule.
        # Return an empty array, and prepare next jobs in parallel.
        self._pa.set_callback_jobs_provider(lambda pa: None)
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        self.assertIn('rerun', jobs_ops)
        self.assertEqual(len(jobs_ops['submit']), 0)
        self.assertEqual(len(jobs_ops['rerun']), 0)

        # Wait end of jobs prepatation
        self._pa._prepare_job_thread.join()

        # Governor call /v1/jobs a second time to get jobs to schedule.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
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

        def mock_borgy_process_agent_stop(s, **kwargs):
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
        # Governor call /v1/jobs to get jobs to schedule
        # First call will return an empty array and prepare jobs in parallel. This thread will stop the PA
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_create = jobs_ops['submit']
        self.assertEqual(len(jobs_to_create), 0)

        # Wait end of jobs prepatation
        self._pa._prepare_job_thread.join()

        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 1])

        del borgy_process_agent_start
        del borgy_process_agent_stop

    def test_pa_autokill_with_jobs_to_rerun(self):
        """Autokill test case when there are jobs to rerun
        """
        count_call = [0, 0]

        def mock_borgy_process_agent_start(s):
            count_call[0] += 1

        def mock_borgy_process_agent_stop(s, **kwargs):
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
        simple_job = MockJob(name='gsm1', state=State.SUCCEEDED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.SUCCEEDED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.QUEUED.value).get_job()
        jobs = copy.deepcopy([simple_job, simple_job2, simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(count_call, [1, 0])
        self.assertEqual(self._pa.is_shutdown(), False)

        # Update jobs in ProcessAgent
        simple_job.state = State.SUCCEEDED.value
        simple_job2.state = State.SUCCEEDED.value
        simple_job3.state = State.FAILED.value
        jobs = copy.deepcopy([simple_job, simple_job2, simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(count_call, [1, 0])
        self.assertEqual(self._pa.is_shutdown(), False)

        # Set callback after PUT due to the call to get_jobs_to_create in a thread
        self._pa.set_callback_jobs_provider(get_stop_job)

        # Rerun last job
        j, updated = self._pa.rerun_job(simple_job3.id)
        self.assertEqual(updated, True)

        # Governor call /v1/jobs to get jobs to schedule.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 0])
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        self.assertIn('rerun', jobs_ops)
        self.assertEqual(len(jobs_ops['submit']), 0)
        self.assertEqual(len(jobs_ops['rerun']), 1)

        # Update jobs in ProcessAgent
        simple_job3.state = State.RUNNING.value
        simple_job3.runs.append(
            {
                'id': str(uuid.uuid4()),
                'jobId': simple_job3.id,
                'createdOn': get_now_isoformat(),
                'state': State.RUNNING.value,
                'info': {},
                'ip': '127.0.0.1',
                'nodeName': 'local',
            }
        )
        jobs = copy.deepcopy([simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 0])

        # Governor call /v1/jobs to get jobs to schedule.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 0])

        # Update jobs in ProcessAgent
        simple_job3.state = State.SUCCEEDED.value
        jobs = copy.deepcopy([simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 1])

        del borgy_process_agent_start
        del borgy_process_agent_stop

    def test_pa_autokill_with_interrupted_jobs_to_rerun_without_autorerun(self):
        """Autokill test case when there are interrupted jobs and without autorerun
        """
        count_call = [0, 0]

        def mock_borgy_process_agent_start(s):
            count_call[0] += 1

        def mock_borgy_process_agent_stop(s, **kwargs):
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
        self._pa.set_autorerun_interrupted_jobs(False)
        self._pa.start()
        self.assertEqual(count_call, [1, 0])

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.SUCCEEDED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.SUCCEEDED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = copy.deepcopy([simple_job, simple_job2, simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(count_call, [1, 0])
        self.assertEqual(self._pa.is_shutdown(), False)

        self._pa.set_callback_jobs_provider(get_stop_job)

        # Governor call /v1/jobs to get jobs to schedule.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 0])
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        self.assertIn('rerun', jobs_ops)
        self.assertEqual(len(jobs_ops['submit']), 0)
        self.assertEqual(len(jobs_ops['rerun']), 0)

        # Update jobs in ProcessAgent
        simple_job.state = State.SUCCEEDED.value
        simple_job2.state = State.SUCCEEDED.value
        simple_job3.state = State.INTERRUPTED.value
        jobs = copy.deepcopy([simple_job, simple_job2, simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        # PA should be stopped
        # Without autorerun, the INTERRUPTED has to be rerun by the user.
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 1])

        del borgy_process_agent_start
        del borgy_process_agent_stop

    def test_pa_autokill_with_interrupted_jobs_to_rerun_and_autorerun(self):
        """Autokill test case when there are interrupted jobs and autorerun
        """
        count_call = [0, 0]

        def mock_borgy_process_agent_start(s):
            count_call[0] += 1

        def mock_borgy_process_agent_stop(s, **kwargs):
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
        simple_job = MockJob(name='gsm1', state=State.SUCCEEDED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.SUCCEEDED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = copy.deepcopy([simple_job, simple_job2, simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(count_call, [1, 0])
        self.assertEqual(self._pa.is_shutdown(), False)

        self._pa.set_callback_jobs_provider(get_stop_job)

        # Governor call /v1/jobs to get jobs to schedule.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 0])
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        self.assertIn('rerun', jobs_ops)
        self.assertEqual(len(jobs_ops['submit']), 0)
        self.assertEqual(len(jobs_ops['rerun']), 0)

        # Update jobs in ProcessAgent
        simple_job.state = State.SUCCEEDED.value
        simple_job2.state = State.SUCCEEDED.value
        simple_job3.state = State.INTERRUPTED.value
        jobs = copy.deepcopy([simple_job, simple_job2, simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        # PA should be always running
        self.assertEqual(count_call, [1, 0])
        self.assertEqual(self._pa.is_shutdown(), True)

        # Governor call /v1/jobs to get jobs to schedule.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 0])
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        self.assertIn('rerun', jobs_ops)
        self.assertEqual(len(jobs_ops['submit']), 0)
        self.assertEqual(len(jobs_ops['rerun']), 1)

        # Update jobs in ProcessAgent
        simple_job3.state = State.CANCELLED.value
        simple_job3.runs.append(
            {
                'id': str(uuid.uuid4()),
                'jobId': simple_job3.id,
                'createdOn': get_now_isoformat(),
                'state': State.CANCELLED.value,
                'info': {},
                'ip': '127.0.0.1',
                'nodeName': 'local',
            }
        )
        jobs = copy.deepcopy([simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        # PA should be stopped
        self.assertEqual(count_call, [1, 1])

        del borgy_process_agent_start
        del borgy_process_agent_stop

    def test_pa_autokill_with_interrupted_jobs_to_rerun_and_autorerun_order(self):
        """Autokill test case when there are interrupted jobs and autorerun and try to update callbacks order
        """
        count_call = [0, 0]

        def mock_borgy_process_agent_start(s):
            count_call[0] += 1

        def mock_borgy_process_agent_stop(s, **kwargs):
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

        # Disable it to change the order of update subscribers
        self._pa.set_autokill(False)
        self._pa.set_autorerun_interrupted_jobs(False)
        # Try to enable autokill before autorerun to check if autokill is always the last callback to be called
        self._pa.set_autokill(True)
        self._pa.set_autorerun_interrupted_jobs(True)
        self._pa.start()

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.SUCCEEDED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.SUCCEEDED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = copy.deepcopy([simple_job, simple_job2, simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(count_call, [1, 0])
        self.assertEqual(self._pa.is_shutdown(), False)

        self._pa.set_callback_jobs_provider(get_stop_job)

        # Governor call /v1/jobs to get jobs to schedule.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 0])
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        self.assertIn('rerun', jobs_ops)
        self.assertEqual(len(jobs_ops['submit']), 0)
        self.assertEqual(len(jobs_ops['rerun']), 0)

        # Update jobs in ProcessAgent
        simple_job.state = State.SUCCEEDED.value
        simple_job2.state = State.SUCCEEDED.value
        simple_job3.state = State.INTERRUPTED.value
        jobs = copy.deepcopy([simple_job, simple_job2, simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        # PA should be always running
        # The autorerun and autokill call order is important for this case
        self.assertEqual(count_call, [1, 0])
        self.assertEqual(self._pa.is_shutdown(), True)

        # Governor call /v1/jobs to get jobs to schedule.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        self.assertEqual(count_call, [1, 0])
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        self.assertIn('rerun', jobs_ops)
        self.assertEqual(len(jobs_ops['submit']), 0)
        self.assertEqual(len(jobs_ops['rerun']), 1)

        # Update jobs in ProcessAgent
        simple_job3.state = State.CANCELLED.value
        simple_job3.runs.append(
            {
                'id': str(uuid.uuid4()),
                'jobId': simple_job3.id,
                'createdOn': get_now_isoformat(),
                'state': State.CANCELLED.value,
                'info': {},
                'ip': '127.0.0.1',
                'nodeName': 'local',
            }
        )
        jobs = copy.deepcopy([simple_job3])
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), True)
        # PA should be stopped
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
        def get_no_job(pa):
            return []

        def get_stop_job(pa):
            return None

        self._pa.clear_jobs_in_creation()
        # Shutdown PA on next call
        self._pa.set_callback_jobs_provider(get_no_job)

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        jobs = [simple_job]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        self.assertEqual(self._pa.is_shutdown(), False)
        self.assertEqual(len(self._pa.get_jobs()), 1)

        # Set callback after PUT due to the call to get_jobs_to_create in a thread
        self._pa.set_callback_jobs_provider(get_stop_job)

        # First call will return an empty array and prepare jobs in parallel
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_create = jobs_ops['submit']
        self.assertEqual(len(jobs_to_create), 0)

        # Wait end of jobs prepatation
        self._pa._prepare_job_thread.join()

        # Second time, Shutdown PA
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
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
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
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
        # Return [] en launch jobs preparation
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Wait end of jobs prepatation
        self._pa._prepare_job_thread.join()

        # Governor call /v1/jobs to get jobs to schedule and to rerun.
        # Return 200
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

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

        # Governor call /v1/jobs to get jobs to schedule
        # First call will return an empty array and prepare jobs in parallel
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_create = jobs_ops['submit']
        self.assertEqual(len(jobs_to_create), 0)

        # Wait end of jobs prepatation
        self._pa._prepare_job_thread.join()

        # Second time, governor call /v1/jobs to get jobs to schedule and to rerun
        response = self.client.open('/v1/jobs', method='GET')
        # Should return 500 due to restartable job
        error = response.data.decode('utf-8').rstrip("\n")
        self.assertStatus(response, 500, 'Should return 500. Response body is : ' + error)
        self.assertEqual(error, '"Process agent job can\'t have automatic restart. Use autorerun_interrupted_jobs parameter or handle rerun on job udpate by yourself."')  # noqa

    def test_pa_auto_mode(self):
        """Test case when auto mode is selected
        """
        pa_module_borgy = __import__('borgy_process_agent.modes.borgy', fromlist=['ProcessAgent'])
        pa_module_docker = __import__('borgy_process_agent.modes.docker', fromlist=['ProcessAgent'])
        pa = ProcessAgent(mode=ProcessAgentMode.AUTO)
        self.assertIsInstance(pa, pa_module_borgy.ProcessAgent)

        del os.environ['BORGY_JOB_ID']
        del os.environ['BORGY_USER']
        pa = ProcessAgent(mode=ProcessAgentMode.AUTO)
        self.assertIsInstance(pa, pa_module_docker.ProcessAgent)

    def test_pa_not_matching_jobs_by_name(self):
        """Test case for no matching by name index
        """

        def get_new_jobs(pa):
            return [{  # Will have paIndex = 0
                'reqCores': 1,
                'name': 'same-job-name'
            }, {  # Will have paIndex = 1
                'reqCores': 2,
                'name': 'same-job-name'
            }]

        self._pa.set_callback_jobs_provider(get_new_jobs)

        # First call will return an empty array and prepare jobs in parallel
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_create = jobs_ops['submit']
        self.assertEqual(len(jobs_to_create), 0)

        # Wait end of jobs prepatation
        self._pa._prepare_job_thread.join()

        # Second time, return prepared jobs
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_submit = jobs_ops['submit']
        self.assertEqual(len(jobs_to_submit), 2)
        self.assertEqual(jobs_to_submit[0]['reqCores'], 1)
        self.assertEqual(jobs_to_submit[1]['reqCores'], 2)

        # Check job in creation in PA
        jobs = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].req_cores, 1)
        self.assertEqual(jobs[1].req_cores, 2)

        # Insert job in ProcessAgent
        simple_job = MockJob(name='same-job-name', reqCores=2, paIndex=1).get_job()
        jobs = [simple_job]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        job = self._pa.get_job_by_id(simple_job.id)
        self.assertIsNotNone(job)
        self.assertEqual(job.name, 'same-job-name')
        self.assertEqual(job.req_cores, 2)

        # Check job in creation in PA
        jobs = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].req_cores, 1)

    def test_pa_check_merge_envs(self):
        """Test case to merge envs vars
        """

        envs = [
            'TEST_VAR=uuid',
            'ACCESS_KEY=password',
        ]

        envs_final = [
            'BORGY_PROCESS_AGENT_INDEX=0',
            'BORGY_PROCESS_AGENT='+os.environ['BORGY_JOB_ID']
        ] + envs

        def get_new_jobs(pa):
            return [{
                'reqCores': 1,
                'name': 'same-job-name',
                'environmentVars': envs
            }]

        self._pa.set_callback_jobs_provider(get_new_jobs)

        # First call will return an empty array and prepare jobs in parallel
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_create = jobs_ops['submit']
        self.assertEqual(len(jobs_to_create), 0)

        # Wait end of jobs prepatation
        self._pa._prepare_job_thread.join()

        # Second time, return prepared jobs
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_submit = jobs_ops['submit']
        self.assertEqual(len(jobs_to_submit), 1)
        self.assertEqual(jobs_to_submit[0]['reqCores'], 1)
        self.assertEqual(jobs_to_submit[0]['environmentVars'], envs_final)

        # Check job in creation in PA
        jobs = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].req_cores, 1)
        self.assertEqual(jobs[0].environment_vars, envs_final)

        # Insert job in ProcessAgent
        simple_job = MockJob(name='same-job-name', reqCores=1, paIndex=0, environmentVars=envs_final).get_job()
        jobs = [simple_job]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        job = self._pa.get_job_by_id(simple_job.id)
        self.assertIsNotNone(job)
        self.assertEqual(job.name, 'same-job-name')
        self.assertEqual(job.req_cores, 1)
        self.assertEqual(jobs[0].environment_vars, envs_final)

    def test_pa_prepare_job_to_create_after_jobs_push(self):
        """Test case to check next jobs will be NOT prepared in parallel after PUT call
        """

        def get_job(pa):
            return {
                'name': 'my-job'
            }

        self._pa.clear_jobs_in_creation()
        self._pa.set_callback_jobs_provider(get_job)

        # Insert fake jobs in ProcessAgent
        # After jobs pushed in PA, PA starts a thread to prepare next jobs
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.RUNNING.value)

        # No jobs prepatation: no thread
        self.assertIsNone(self._pa._prepare_job_thread)

        # Check jobs in creation
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 0)

        # Get jobs and launch jobs preparation
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_submit = jobs_ops['submit']
        self.assertEqual(len(jobs_to_submit), 0)

        # Wait end of jobs prepatation
        self._pa._prepare_job_thread.join()

        # Check job in creation in PA
        # Should have 1 job in creation
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 1)

    def test_pa_slow_get_job_to_create(self):
        """Test case when the call to get_job_to_create is too long for the governor
        """

        def get_slow_job(pa):
            time.sleep(1)
            return {
                'name': 'my-job'
            }

        self._pa.clear_jobs_in_creation()

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.RUNNING.value)

        # Set callback after PUT due to the call to get_jobs_to_create in a thread
        self._pa.set_callback_jobs_provider(get_slow_job)

        # During the GET call, _prepare_jobs_to_create should be called in parallel.
        # and the result sould be an empty array
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_submit = jobs_ops['submit']
        self.assertEqual(jobs_to_submit, [])

        time.sleep(1.1)

        # After 1.1 second, the jobs should be ready
        # and the GET should return the spec for 'my-job'
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 1)

        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_submit = jobs_ops['submit']
        self.assertEqual(len(jobs_to_submit), 1)

    def test_pa_parallel_get_job_to_create(self):
        """Test case when there are parallel calls of GET /v1/jobs
        """
        count_call = [0]

        def get_slow_job(pa):
            count_call[0] += 1
            time.sleep(1)
            return {
                'name': 'my-job'
            }

        def governor_get_job():
            response = self.client.open('/v1/jobs', method='GET')
            self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
            jobs_ops = response.get_json()
            self.assertIn('submit', jobs_ops)
            jobs_to_submit = jobs_ops['submit']
            self.assertEqual(jobs_to_submit, [])

        self._pa.clear_jobs_in_creation()

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.RUNNING.value)

        # Set callback after PUT due to the call to get_jobs_to_create in a thread
        self._pa.set_callback_jobs_provider(get_slow_job)

        # During the GET call, first thread should prepare the new jobs in parallel and should return an empty array
        # Second thread should not prepare the new jobs and just return an empty array
        thread1 = threading.Thread(target=governor_get_job)
        thread1.setDaemon(True)
        thread1.start()
        time.sleep(0.5)
        thread2 = threading.Thread(target=governor_get_job)
        thread2.setDaemon(True)
        thread2.start()

        time.sleep(1.1)

        # The callback should be called just one time
        self.assertEqual(count_call[0], 1)

        # After 1.1 second, the jobs should be ready
        # and the GET should return the spec for 'my-job'
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 1)

        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_submit = jobs_ops['submit']
        self.assertEqual(len(jobs_to_submit), 1)
        simple_job4 = MockJob(**jobs_to_submit[0]).get_job()

        # Push job created in PA. Next jobs will be prepared in parallel because there are no more jobs in creation
        jobs = [simple_job4]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Start a thread to get jobs
        # Should get an empty array and don't prepare jobs in parallel (already running)
        time.sleep(0.5)
        thread3 = threading.Thread(target=governor_get_job)
        thread3.setDaemon(True)
        thread3.start()

        time.sleep(1.1)

        # The callback should be called just a second time
        self.assertEqual(count_call[0], 2)

        # After 1.1 second, the jobs should be ready
        # and the GET should return the spec for 'my-job'
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 1)

        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_submit = jobs_ops['submit']
        self.assertEqual(len(jobs_to_submit), 1)

    def test_pa_parallel_get_job_to_create_stress(self):
        """Test case when there are parallel calls of GET /v1/jobs
        """
        count_call = [0]

        def get_slow_job(pa):
            count_call[0] += 1
            time.sleep(1)
            return {
                'name': 'my-job'
            }

        def governor_get_job():
            response = self.client.open('/v1/jobs', method='GET')
            self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
            jobs_ops = response.get_json()
            self.assertIn('submit', jobs_ops)
            jobs_to_submit = jobs_ops['submit']
            self.assertEqual(jobs_to_submit, [])

        self._pa.clear_jobs_in_creation()

        # Insert fake jobs in ProcessAgent
        simple_job = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job2 = MockJob(name='gsm1', state=State.QUEUED.value).get_job()
        simple_job3 = MockJob(name='gsm3', state=State.RUNNING.value).get_job()
        jobs = [simple_job, simple_job2, simple_job3]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        job = self._pa.get_jobs_by_name(simple_job3.name)[0]
        self.assertEqual(job.state, State.RUNNING.value)

        # Set callback after PUT due to the call to get_jobs_to_create in a thread
        self._pa.set_callback_jobs_provider(get_slow_job)

        # Stress call with 100 threads
        threads = []
        for _ in range(100):
            thread = threading.Thread(target=governor_get_job)
            thread.setDaemon(True)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        self._pa._prepare_job_thread.join()

        # The callback should be called just one time
        self.assertEqual(count_call[0], 1)

        # After end of threads, the jobs should be ready
        # and the GET should return the spec for 'my-job'
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 1)

        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_submit = jobs_ops['submit']
        self.assertEqual(len(jobs_to_submit), 1)
        simple_job4 = MockJob(**jobs_to_submit[0]).get_job()

        # Push job created in PA. Next jobs will be prepared in parallel because there are no more jobs in creation
        jobs = [simple_job4]
        response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(jobs))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Should get an empty array and don't prepare jobs in parallel (already running)
        # Stress with 100 threads
        threads = []
        for _ in range(100):
            thread = threading.Thread(target=governor_get_job)
            thread.setDaemon(True)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        self._pa._prepare_job_thread.join()

        # The callback should be called just a second time
        self.assertEqual(count_call[0], 2)

        # After end of threads, the jobs should be ready
        # and the GET should return the spec for 'my-job'
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 1)

        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        jobs_to_submit = jobs_ops['submit']
        self.assertEqual(len(jobs_to_submit), 1)


if __name__ == '__main__':
    import unittest
    unittest.main()
