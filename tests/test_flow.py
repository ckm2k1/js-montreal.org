# -*- coding: utf-8 -*-
#
# test_jobs_controller.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from __future__ import absolute_import

from collections import defaultdict
from flask import json
from tests import BaseTestCase
from tests.utils import MockJob
from borgy_process_agent_api_server.models.job import Job
from borgy_process_agent import JobEventState


class TestFlow(BaseTestCase):
    """Flow tests"""

    def test_flow_simple(self):
        """Simple flow test case
        """
        callback_called = [0]
        callbacks = defaultdict(lambda: {'called': 0, 'states': []})

        # Callback
        def callback_job_update(event):
            callback_called[0] += 1
            for j in event.jobs:
                callbacks[j['job'].name]['called'] += 1
                callbacks[j['job'].name]['states'].append(j['state'])

        self._pa.subscribe_jobs_update(callback_job_update)

        i_job = [1]

        # Set callback to return only job
        def get_new_jobs():
            job = {
                'name': 'job-' + str(i_job[0])
            }
            i_job[0] += 1
            return job

        governor_jobs = []

        self._pa.clear_jobs_in_creation()
        self._pa.set_callback_jobs_provider(get_new_jobs)

        # Governor call /v1/jobs to get jobs to schedule
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_to_create = response.get_json()
        # Should return job 'job-1'
        self.assertEqual(len(jobs_to_create), 1)
        job = Job.from_dict(jobs_to_create[0])
        self.assertEqual('job-1', job.name)

        # Add job to governor
        governor_jobs.append(MockJob(**jobs_to_create[0]).get_job())

        # Check job in creation in PA
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 1)
        self.assertEqual('job-1', jobs_in_creation[0].name)

        # Check job created
        jobs_created = self._pa.get_jobs()
        self.assertEqual(len(jobs_created), 0)

        # Governor call again to get jobs to schedule
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_to_create = response.get_json()
        # Should always return job 'job-1'
        self.assertEqual(len(jobs_to_create), 1)
        job = Job.from_dict(jobs_to_create[0])
        self.assertEqual('job-1', job.name)

        # Governor create job and call PUT /v1/jobs to update job state in PA
        governor_jobs[0].state = 'QUEUED'
        jobs_sent = governor_jobs
        response = self.client.open('/v1/jobs', method='PUT',
                                    content_type='application/json', data=json.dumps(jobs_sent))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Check job in creation in PA
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 0)

        # Check job created
        jobs_created = self._pa.get_jobs()
        self.assertEqual(len(jobs_created), 1)
        self.assertEqual('job-1', jobs_created[jobs_sent[0].id].name)
        self.assertEqual('QUEUED', jobs_created[jobs_sent[0].id].state)

        # Governor update job and call PUT /v1/jobs to update state
        governor_jobs[0].state = 'RUNNING'
        jobs_sent = governor_jobs
        response = self.client.open('/v1/jobs', method='PUT',
                                    content_type='application/json', data=json.dumps(jobs_sent))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Check job in creation in PA
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 0)

        # Check job created
        jobs_created = self._pa.get_jobs()
        self.assertEqual(len(jobs_created), 1)
        self.assertEqual('job-1', jobs_created[jobs_sent[0].id].name)
        self.assertEqual('RUNNING', jobs_created[jobs_sent[0].id].state)

        # Governor call to get jobs to schedule
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_to_create = response.get_json()
        # Should return job 'job-2'
        self.assertEqual(len(jobs_to_create), 1)
        job = Job.from_dict(jobs_to_create[0])
        self.assertEqual('job-2', job.name)

        # Add job to governor
        governor_jobs.append(MockJob(**jobs_to_create[0]).get_job())

        # Check job in creation in PA
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 1)
        self.assertEqual('job-2', jobs_in_creation[0].name)

        # Check job created
        jobs_created = self._pa.get_jobs()
        self.assertEqual(len(jobs_created), 1)
        self.assertEqual('job-1', jobs_created[list(jobs_created.keys())[0]].name)

        # Check callback calls
        self.assertEqual(callback_called[0], 2)
        self.assertEqual(callbacks['job-1']['called'], 2)
        self.assertEqual(callbacks['job-1']['states'], [JobEventState.CREATED, JobEventState.UPDATED])

    def test_flow_multiple_jobs_same_time(self):
        """Simple flow test case
        """
        callback_called = [0]
        callbacks = defaultdict(lambda: {'called': 0, 'states': []})

        # Callback
        def callback_job_update(event):
            callback_called[0] += 1
            for j in event.jobs:
                callbacks[j['job'].name]['called'] += 1
                callbacks[j['job'].name]['states'].append(j['state'])

        self._pa.subscribe_jobs_update(callback_job_update)

        i_job = [1]

        # Set callback to return only job
        def get_new_jobs():
            jobs = [{
                'name': 'job-' + str(i_job[0])
            }, {
                'name': 'job-' + str(i_job[0] + 1)
            }, {
                'name': 'job-' + str(i_job[0] + 2)
            }]
            i_job[0] += 3
            return jobs

        governor_jobs = []

        self._pa.clear_jobs_in_creation()
        self._pa.set_callback_jobs_provider(get_new_jobs)

        # Governor call /v1/jobs to get jobs to schedule
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_to_create = response.get_json()
        # Should return job 'job-1', 'job-2' and 'job-3'
        self.assertEqual(len(jobs_to_create), 3)
        job1 = Job.from_dict(jobs_to_create[0])
        job2 = Job.from_dict(jobs_to_create[1])
        job3 = Job.from_dict(jobs_to_create[2])
        self.assertEqual('job-1', job1.name)
        self.assertEqual('job-2', job2.name)
        self.assertEqual('job-3', job3.name)

        # Add job to governor
        governor_jobs.append(MockJob(**jobs_to_create[0]).get_job())
        governor_jobs.append(MockJob(**jobs_to_create[1]).get_job())
        governor_jobs.append(MockJob(**jobs_to_create[2]).get_job())

        # Check job in creation in PA
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 3)
        self.assertEqual('job-1', jobs_in_creation[0].name)
        self.assertEqual('job-2', jobs_in_creation[1].name)
        self.assertEqual('job-3', jobs_in_creation[2].name)

        # Check job created
        jobs_created = self._pa.get_jobs()
        self.assertEqual(len(jobs_created), 0)

        # Governor call again to get jobs to schedule
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_to_create = response.get_json()
        # Should always return job 'job-1', 'job-2' and 'job-3'
        self.assertEqual(len(jobs_to_create), 3)
        job1 = Job.from_dict(jobs_to_create[0])
        job2 = Job.from_dict(jobs_to_create[1])
        job3 = Job.from_dict(jobs_to_create[2])
        self.assertEqual('job-1', job1.name)
        self.assertEqual('job-2', job2.name)
        self.assertEqual('job-3', job3.name)

        # Governor create job and call PUT /v1/jobs to update job state in PA
        # Only for 'job-1'
        governor_jobs[0].state = 'QUEUED'
        jobs_sent = [governor_jobs[0]]
        response = self.client.open('/v1/jobs', method='PUT',
                                    content_type='application/json', data=json.dumps(jobs_sent))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Check job in creation in PA
        # Should still have 2 jobs in creation
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 2)
        self.assertEqual('job-2', jobs_in_creation[0].name)
        self.assertEqual('job-3', jobs_in_creation[1].name)

        # Check job created
        jobs_created = self._pa.get_jobs()
        self.assertEqual(len(jobs_created), 1)
        self.assertEqual('job-1', jobs_created[jobs_sent[0].id].name)
        self.assertEqual('QUEUED', jobs_created[jobs_sent[0].id].state)

        # Governor update job and call PUT /v1/jobs to update state
        governor_jobs[0].state = 'RUNNING'
        jobs_sent = [governor_jobs[0]]
        response = self.client.open('/v1/jobs', method='PUT',
                                    content_type='application/json', data=json.dumps(jobs_sent))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Check job in creation in PA
        # Should still have 2 jobs in creation
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 2)
        self.assertEqual('job-2', jobs_in_creation[0].name)
        self.assertEqual('job-3', jobs_in_creation[1].name)

        # Check job created
        jobs_created = self._pa.get_jobs()
        self.assertEqual(len(jobs_created), 1)
        self.assertEqual('job-1', jobs_created[jobs_sent[0].id].name)
        self.assertEqual('RUNNING', jobs_created[jobs_sent[0].id].state)

        # Governor call to get jobs to schedule
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_to_create = response.get_json()
        # Should return job the 2 remaining job in creation: 'job-2' and 'job-3'
        self.assertEqual(len(jobs_to_create), 2)
        job2 = Job.from_dict(jobs_to_create[0])
        job3 = Job.from_dict(jobs_to_create[1])
        self.assertEqual('job-2', job2.name)
        self.assertEqual('job-3', job3.name)

        # Governor call PUT /v1/jobs to update state
        # All jobs are sent, PA will not call callback for job-1 because there is no update
        jobs_sent = governor_jobs
        response = self.client.open('/v1/jobs', method='PUT',
                                    content_type='application/json', data=json.dumps(jobs_sent))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Check job in creation in PA
        # Should shave 0 jobs in creation
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 0)

        # Check job created
        jobs_created = self._pa.get_jobs()
        self.assertEqual(len(jobs_created), 3)
        self.assertEqual('job-1', jobs_created[jobs_sent[0].id].name)
        self.assertEqual('RUNNING', jobs_created[jobs_sent[0].id].state)
        self.assertEqual('job-2', jobs_created[jobs_sent[1].id].name)
        self.assertEqual('QUEUING', jobs_created[jobs_sent[1].id].state)
        self.assertEqual('job-3', jobs_created[jobs_sent[2].id].name)
        self.assertEqual('QUEUING', jobs_created[jobs_sent[2].id].state)

        # Governor call /v1/jobs to get jobs to schedule
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_to_create = response.get_json()
        # Should return job 'job-4', 'job-5' and 'job-6'
        self.assertEqual(len(jobs_to_create), 3)
        job1 = Job.from_dict(jobs_to_create[0])
        job2 = Job.from_dict(jobs_to_create[1])
        job3 = Job.from_dict(jobs_to_create[2])
        self.assertEqual('job-4', job1.name)
        self.assertEqual('job-5', job2.name)
        self.assertEqual('job-6', job3.name)

        # Check job in creation in PA
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 3)
        self.assertEqual('job-4', jobs_in_creation[0].name)
        self.assertEqual('job-5', jobs_in_creation[1].name)
        self.assertEqual('job-6', jobs_in_creation[2].name)

        # Check job created
        jobs_created = self._pa.get_jobs()
        self.assertEqual(len(jobs_created), 3)

        # Add job to governor a job unknow by PA
        governor_jobs.append(MockJob(id='33339999-0000-2222-8888-666655554444', name='job-X').get_job())

        # Governor call PUT /v1/jobs to update state
        jobs_sent = [governor_jobs[3]]
        response = self.client.open('/v1/jobs', method='PUT',
                                    content_type='application/json', data=json.dumps(jobs_sent))
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

        # Check job in creation in PA
        jobs_in_creation = self._pa.get_jobs_in_creation()
        self.assertEqual(len(jobs_in_creation), 3)
        self.assertEqual('job-4', jobs_in_creation[0].name)
        self.assertEqual('job-5', jobs_in_creation[1].name)
        self.assertEqual('job-6', jobs_in_creation[2].name)

        # Check job created
        jobs_created = self._pa.get_jobs()
        self.assertEqual(len(jobs_created), 4)
        self.assertEqual('job-X', jobs_created['33339999-0000-2222-8888-666655554444'].name)
        self.assertEqual('QUEUING', jobs_created['33339999-0000-2222-8888-666655554444'].state)

        # Check callback calls
        self.assertEqual(callback_called[0], 4)
        self.assertEqual(callbacks['job-1']['called'], 2)
        self.assertEqual(callbacks['job-1']['states'], [JobEventState.CREATED, JobEventState.UPDATED])
        self.assertEqual(callbacks['job-2']['called'], 1)
        self.assertEqual(callbacks['job-2']['states'], [JobEventState.CREATED])
        self.assertEqual(callbacks['job-3']['called'], 1)
        self.assertEqual(callbacks['job-3']['states'], [JobEventState.CREATED])
        self.assertEqual(callbacks['job-X']['called'], 1)
        self.assertEqual(callbacks['job-X']['states'], [JobEventState.ADDED])


if __name__ == '__main__':
    import unittest
    unittest.main()