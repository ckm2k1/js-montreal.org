# -*- coding: utf-8 -*-
#
# test_jobs_controller.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from __future__ import absolute_import

import os
import copy
from flask import json
from dictdiffer import diff
from tests import BaseTestCase
from tests.utils import MockJob
from borgy_process_agent import ProcessAgent, JobEventState
from borgy_process_agent_api_server.models.job import Job


class TestJobsController(BaseTestCase):
    """JobsController integration test stubs"""

    def test_v1_jobs_get_ready(self):
        """Test case when PA is not ready
        """
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 418, 'Should return 418. Response body is : ' + response.data.decode('utf-8'))

        # Define callback for first PA. Should be ready.
        self._pa.set_callback_jobs_provider(lambda pa: [])
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

    def test_v1_jobs_get_multiple_pa_ready(self):
        """Test case when multiple PA is not ready
        """
        pa2 = ProcessAgent()

        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 418, 'Should return 418. Response body is : ' + response.data.decode('utf-8'))

        # Define callback for second PA. Should still not ready.
        pa2.set_callback_jobs_provider(lambda pa: [])
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 418, 'Should return 418. Response body is : ' + response.data.decode('utf-8'))

        # Define callback for first PA. Should be ready.
        self._pa.set_callback_jobs_provider(lambda pa: [])
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        pa2.delete()

    def test_v1_jobs_get_check_environment_vars(self):
        """Test case for undefined environment variables
        """
        os.environ['BORGY_JOB_ID'] = ''
        self._pa.set_callback_jobs_provider(lambda pa: {})
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 400, 'Should return 400. Response body is : ' + response.data.decode('utf-8'))

        os.environ['BORGY_JOB_ID'] = '1234'
        os.environ['BORGY_USER'] = ''
        self._pa.set_callback_jobs_provider(lambda pa: {})
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 400, 'Should return 400. Response body is : ' + response.data.decode('utf-8'))

        del os.environ['BORGY_USER']
        self._pa.set_callback_jobs_provider(lambda pa: {})
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 400, 'Should return 400. Response body is : ' + response.data.decode('utf-8'))

        del os.environ['BORGY_JOB_ID']
        os.environ['BORGY_USER'] = 'gsm'
        self._pa.set_callback_jobs_provider(lambda pa: {})
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 400, 'Should return 400. Response body is : ' + response.data.decode('utf-8'))

    def test_v1_jobs_get_jobs_provider_types(self):
        """Test case for type returns by callback of jobs provider
        """
        failing_values = [
            "MyString",
            100,
            object(),
            [{}, "MySring"]
        ]

        for v in failing_values:
            self._pa.set_callback_jobs_provider(lambda pa: v)
            response = self.client.open('/v1/jobs', method='GET')
            self.assertStatus(response, 400, 'Should return 400. Value is: ' + str(v)
                              + '. Response body is : ' + response.data.decode('utf-8'))

        succeeded_values = [
            [],
            {},
            [{}],
            [{}, {}]
        ]

        for v in succeeded_values:
            self._pa.clear_jobs_in_creation()
            self._pa.set_callback_jobs_provider(lambda pa: v)
            response = self.client.open('/v1/jobs', method='GET')
            self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
                              + '. Response body is : ' + response.data.decode('utf-8'))

    def test_v1_jobs_get_stop_jobs_provider(self):
        """Test case for jobs keep returning 204 when pa is shutdown
        """
        self._pa.set_callback_jobs_provider(lambda pa: None)
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 204, 'Should return 204. Response body is : ' + response.data.decode('utf-8'))

        self._pa.set_callback_jobs_provider(lambda pa: [])
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 204, 'Should return 204. Response body is : ' + response.data.decode('utf-8'))

    def test_v1_jobs_keep_last_creation(self):
        """Test case for jobs keep returning last creation list
        """
        job_spec = {
            'command': ['bash', '-c', 'sleep', 'inifinity']
        }
        self._pa.set_callback_jobs_provider(lambda pa: job_spec)
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs = response.get_json()
        self.assertEqual(len(jobs), 1)
        job = Job.from_dict(jobs[0])
        self.assertEqual(job_spec['command'], job.command)

        # Check job in creation in PA
        jobs = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(job_spec['command'], jobs[0].command)

        new_job_spec = {
            'command': ['killall', 'sleep']
        }
        self._pa.set_callback_jobs_provider(lambda pa: new_job_spec)
        jobs = response.get_json()
        self.assertEqual(len(jobs), 1)
        job = Job.from_dict(jobs[0])
        self.assertNotEqual(new_job_spec['command'], job.command)
        self.assertEqual(job_spec['command'], job.command)

    def test_v1_jobs_put_check_content_type(self):
        """Test case to check content-type on v1_jobs_put
        """
        failing_values = [
            "",
            100,
            "text/html; charset=UTF-8"
        ]

        for v in failing_values:
            response = self.client.open('/v1/jobs', method='PUT', data='[]', content_type=v)
            self.assertStatus(response, 415, 'Should return 415. Value is: ' + str(v)
                              + '. Response body is : ' + response.data.decode('utf-8'))

        succeeded_values = [
            "application/json",
            "application/json; charset=UTF-8"
        ]

        for v in succeeded_values:
            response = self.client.open('/v1/jobs', method='PUT', data='[]', content_type=v)
            self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
                              + '. Response body is : ' + response.data.decode('utf-8'))

    def test_v1_jobs_put_check_input(self):
        """Test case for bad input on v1_jobs_put
        """
        simple_job = MockJob().get_job()
        failing_values = [
            100,
            "MyString",
            {},
            [100],
            [""],
            [{}],
            [simple_job, 100],
            [simple_job, ""],
            [simple_job, {}]
        ]

        for v in failing_values:
            response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(v))
            self.assertStatus(response, 400, 'Should return 400. Value is: ' + str(v)
                              + '. Response body is : ' + response.data.decode('utf-8'))

        succeeded_values = [
            [],
            [simple_job]
        ]

        for v in succeeded_values:
            response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(v))
            self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
                              + '. Response body is : ' + response.data.decode('utf-8'))

    def test_v1_jobs_put_check_add(self):
        """Test case for adding job on v1_jobs_put
        """
        simple_job = MockJob().get_job()
        values = [
            {'jobs': [], 'len': 0},
            {'jobs': [MockJob().get_job()], 'len': 1},
            {'jobs': [MockJob().get_job(), MockJob().get_job()], 'len': 2},
            {'jobs': [simple_job, simple_job], 'len': 1}
        ]

        for v in values:
            self.setUp()
            response = self.client.open('/v1/jobs', method='PUT',
                                        content_type='application/json', data=json.dumps(v['jobs']))
            self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
                              + '. Response body is : ' + response.data.decode('utf-8'))

            # Check job in creation in PA
            jobs_in_creation = self._pa.get_jobs_in_creation()
            self.assertEqual(len(jobs_in_creation), 0)

            # Check job created
            jobs_created = self._pa.get_jobs()
            self.assertEqual(len(jobs_created), v['len'])
            self.tearDown()

    def test_v1_jobs_put_check_add_in_continue(self):
        """Test case for adding job on v1_jobs_put
        """
        simple_job = MockJob().get_job()
        values = [
            {'jobs': [], 'len': 0},
            {'jobs': [MockJob().get_job()], 'len': 1},
            {'jobs': [MockJob().get_job(), MockJob().get_job()], 'len': 2},
            {'jobs': [simple_job, simple_job], 'len': 1},
            {'jobs': [simple_job], 'len': 0},
            {'jobs': [MockJob().get_job()], 'len': 1}
        ]

        total_length = 0
        for v in values:
            response = self.client.open('/v1/jobs', method='PUT',
                                        content_type='application/json', data=json.dumps(v['jobs']))
            self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
                              + '. Response body is : ' + response.data.decode('utf-8'))

            # Check job in creation in PA
            jobs_in_creation = self._pa.get_jobs_in_creation()
            self.assertEqual(len(jobs_in_creation), 0)

            total_length += v['len']
            # Check job created
            jobs_created = self._pa.get_jobs()
            self.assertEqual(len(jobs_created), total_length)

    def test_v1_jobs_put_check_callback_job_update(self):
        """Test case for adding job on v1_jobs_put
        """
        in_creation_job = MockJob().get_job()

        def get_new_jobs(pa):
            return {
                'name': 'my-job'
            }
        self._pa.set_callback_jobs_provider(get_new_jobs)

        # Governor call /v1/jobs to get jobs to schedule
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_to_create = response.get_json()
        # Should return job 'my-job'
        self.assertEqual(len(jobs_to_create), 1)
        self.assertEqual('my-job', jobs_to_create[0]['name'])

        # Check job in creation in PA
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 1)
        self.assertEqual('my-job', jobs_in_creation[0].name)

        # Check job created
        jobs_created = self._pa.get_jobs()
        self.assertEqual(len(jobs_created), 0)

        in_creation_job = MockJob(**jobs_to_create[0]).get_job()
        simple_job = MockJob().get_job()
        simple_job_updated = copy.deepcopy(simple_job)
        simple_job_updated.state = 'QUEUED'
        simple_job2 = MockJob().get_job()

        values = [
            {
                'jobs': [],
                'callback': {
                    'should_call': False,
                    'called': False  # Will be updated or not by callback_job_update
                },
                'events': []
            },
            {
                'jobs': [in_creation_job],
                'callback': {
                    'should_call': True,
                    'called': False  # Will be updated or not by callback_job_update
                },
                'events': [{
                    'update': list(diff(jobs_in_creation[0].to_dict(), in_creation_job.to_dict())),
                    'state': JobEventState.CREATED
                }]
            },
            {
                'jobs': [simple_job],
                'callback': {
                    'should_call': True,
                    'called': False  # Will be updated or not by callback_job_update
                },
                'events': [{
                    'update': list(diff({}, simple_job.to_dict())),
                    'state': JobEventState.ADDED
                }]
            },
            {
                'jobs': [simple_job],
                'callback': {
                    'should_call': False,
                    'called': False  # Will be updated or not by callback_job_update
                },
                'events': []
            },
            {
                'jobs': [simple_job2, simple_job2],
                'callback': {
                    'should_call': True,
                    'called': False  # Will be updated or not by callback_job_update
                },
                'events': [{
                    'update': list(diff({}, simple_job2.to_dict())),
                    'state': JobEventState.ADDED
                }]
            },
            {
                'jobs': [simple_job_updated],
                'callback': {
                    'should_call': True,
                    'called': False  # Will be updated or not by callback_job_update
                },
                'events': [{
                    'update': list(diff(simple_job.to_dict(), simple_job_updated.to_dict())),
                    'state': JobEventState.UPDATED
                }]
            }
        ]

        current_value = None

        # Callback
        def callback_job_update(event):
            current_value['callback']['called'] = True
            self.assertEqual(len(event.jobs), len(current_value['events']))
            for (e, e_check) in zip(event.jobs, current_value['events']):
                self.assertEqual(e['state'], e_check['state'])
                self.assertEqual(sorted(e['update']), sorted(e_check['update']))

        self._pa.subscribe_jobs_update(callback_job_update)

        # For each values, call PUT
        for v in values:
            current_value = v
            response = self.client.open('/v1/jobs', method='PUT',
                                        content_type='application/json', data=json.dumps(v['jobs']))
            self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
                              + '. Response body is : ' + response.data.decode('utf-8'))

        # Check if callback was called
        for v in values:
            self.assertEqual(v['callback']['should_call'], v['callback']['called'])

    def test_v1_status_get(self):
        """Test case for v1_status_get
        """
        response = self.client.open('/v1/status', method='GET')
        self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
        jobs = response.get_json()
        self.assertEqual(len(jobs), 0)

    def test_v1_status_get_with_one_job(self):
        """Test case for v1_status_get
        """
        # Insert a fake job in ProcessAgent
        simple_job = MockJob(name='gsm').get_job()
        self._pa._process_agent_jobs[simple_job.id] = simple_job

        response = self.client.open('/v1/status', method='GET')
        self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
        jobs = response.get_json()
        self.assertEqual(len(jobs), 1)
        job = Job.from_dict(jobs[0])
        self.assertEqual(job.name, 'gsm')


if __name__ == '__main__':
    import unittest
    unittest.main()
