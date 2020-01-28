# # -*- coding: utf-8 -*-
# #
# # test_jobs_controller.py
# # Guillaume Smaha, 2018-05-01
# # Copyright (c) 2018 ElementAI. All rights reserved.
# #

# from __future__ import absolute_import

# import copy
# from flask import json
# from mock import patch
# from dictdiffer import diff
# from tests import BaseTestCase
# from tests.utils import MockJob
# from borgy_process_agent import ProcessAgent, JobEventState
# from borgy_process_agent_api_server.models.job import Job


# class TestJobsController(BaseTestCase):
#     """JobsController integration test stubs"""

#     def test_v1_jobs_get_ready(self):
#         """Test case when PA is not ready
#         """
#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 418, 'Should return 418. Response body is : ' + response.data.decode('utf-8'))

#         # Define callback for PA. Should be ready.
#         self._pa.set_callback_jobs_provider(lambda pa: [])
#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

#     def test_v1_jobs_get_multiple_pa_ready(self):
#         """Test case when multiple PA is not ready
#         """
#         pa2 = ProcessAgent()
#         pa2.set_autokill(False)
#         pa2._insert()

#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 418, 'Should return 418. Response body is : ' + response.data.decode('utf-8'))

#         # Define callback for second PA. Should still not ready.
#         pa2.set_callback_jobs_provider(lambda pa: [])
#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 418, 'Should return 418. Response body is : ' + response.data.decode('utf-8'))

#         # Define callback for first PA. Should be ready.
#         self._pa.set_callback_jobs_provider(lambda pa: [])
#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

#         pa2._remove()

#     def test_v1_jobs_get_jobs_provider_types(self):
#         """Test case for type returns by callback of jobs provider
#         """
#         failing_values = [
#             {
#                 'value': "MyString",
#                 'error': '"List or dict expected from jobs_provider"'
#             },
#             {
#                 'value': 100,
#                 'error': '"List or dict expected from jobs_provider"'
#             },
#             {
#                 'value': object(),
#                 'error': '"List or dict expected from jobs_provider"'
#             },
#             {
#                 'value': [{}, "MySring"],
#                 'error': '"Dict expected in list elements from jobs_provider"'
#             }
#         ]
#         count_call = [0]

#         def mock_borgy_process_agent_stop(s, **kwargs):
#             count_call[0] += 1
#             self.assertIsInstance(kwargs.get('error'), TypeError)

#         mock_method = 'borgy_process_agent.modes.eai.ProcessAgent.stop'
#         borgy_process_agent_stop = patch(mock_method, mock_borgy_process_agent_stop)
#         borgy_process_agent_stop.start()

#         for i, v in enumerate(failing_values):
#             self._pa.set_callback_jobs_provider(lambda pa: v['value'])

#             # First call, prepare jobs in parallel (set error to return in next call)
#             response = self.client.open('/v1/jobs', method='GET')
#             self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
#             jobs_ops = response.get_json()
#             self.assertIn('submit', jobs_ops)
#             jobs = jobs_ops['submit']
#             self.assertEqual(len(jobs), 0)

#             # Wait end of jobs prepatation
#             self._pa._prepare_job_thread.join()

#             # Second call, return the error got previously
#             response = self.client.open('/v1/jobs', method='GET')
#             error = response.data.decode('utf-8').rstrip("\n")
#             self.assertStatus(response, 500, 'Should return 500. Value is: ' + str(v['value'])
#                                              + '. Response body is : ' + error)
#             self.assertEqual(error, v['error'])
#             self.assertEqual(count_call, [i + 1])

#         succeeded_values = [
#             [],
#             {},
#             [{}],
#             [{}, {}]
#         ]

#         for v in succeeded_values:
#             self._pa.clear_jobs_in_creation()
#             self._pa.set_callback_jobs_provider(lambda pa: v)
#             response = self.client.open('/v1/jobs', method='GET')
#             self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
#                               + '. Response body is : ' + response.data.decode('utf-8'))

#         borgy_process_agent_stop.stop()
#         del borgy_process_agent_stop

#     def test_v1_jobs_get_stop_jobs_provider(self):
#         """Test case for jobs stop being in shutdown state
#         """
#         self._pa.set_callback_jobs_provider(lambda pa: None)
#         # First call, prepare jobs in parallel (will define shutdown state)
#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
#         jobs_ops = response.get_json()
#         self.assertIn('submit', jobs_ops)
#         jobs = jobs_ops['submit']
#         self.assertEqual(len(jobs), 0)

#         # Wait end of jobs prepatation
#         self._pa._prepare_job_thread.join()

#         # Second time, return shutdown state
#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

#         # Wait end of jobs preparation
#         self._pa._prepare_job_thread.join()
#         self.assertEqual(self._pa.is_shutdown(), True)

#         # PA should remove shutdown state
#         self._pa.set_callback_jobs_provider(lambda pa: [])
#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))

#         # Wait end of jobs prepatation
#         self._pa._prepare_job_thread.join()

#         self.assertEqual(self._pa.is_shutdown(), False)

#     def test_v1_jobs_keep_last_creation(self):
#         """Test case for jobs keep returning last creation list
#         """
#         job_spec = {
#             'command': ['bash', '-c', 'sleep', 'inifinity']
#         }
#         self._pa.set_callback_jobs_provider(lambda pa: job_spec)

#         # First call, prepare jobs in parallel
#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
#         jobs_ops = response.get_json()
#         self.assertIn('submit', jobs_ops)
#         jobs = jobs_ops['submit']
#         self.assertEqual(len(jobs), 0)

#         # Wait end of jobs prepatation
#         self._pa._prepare_job_thread.join()

#         # Second call, return prepared jobs
#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
#         jobs_ops = response.get_json()
#         self.assertIn('submit', jobs_ops)
#         jobs = jobs_ops['submit']
#         self.assertEqual(len(jobs), 1)
#         job = Job.from_dict(jobs[0])
#         self.assertEqual(job_spec['command'], job.command)

#         # Check job in creation in PA
#         jobs = self._pa.get_jobs_in_creation()
#         self.assertEqual(len(jobs), 1)
#         self.assertEqual(job_spec['command'], jobs[0].command)

#         new_job_spec = {
#             'command': ['killall', 'sleep']
#         }
#         self._pa.set_callback_jobs_provider(lambda pa: new_job_spec)
#         response = self.client.open('/v1/jobs', method='GET')
#         jobs_ops = response.get_json()
#         self.assertIn('submit', jobs_ops)
#         jobs = jobs_ops['submit']
#         self.assertEqual(len(jobs), 1)
#         job = Job.from_dict(jobs[0])
#         self.assertNotEqual(new_job_spec['command'], job.command)
#         self.assertEqual(job_spec['command'], job.command)

#     def test_v1_jobs_put_check_content_type(self):
#         """Test case to check content-type on v1_jobs_put
#         """
#         failing_values = [
#             "",
#             100,
#             "text/html; charset=UTF-8"
#         ]

#         for v in failing_values:
#             response = self.client.open('/v1/jobs', method='PUT', data='[]', content_type=v)
#             self.assertStatus(response, 415, 'Should return 415. Value is: ' + str(v)
#                               + '. Response body is : ' + response.data.decode('utf-8'))

#         succeeded_values = [
#             "application/json",
#             "application/json; charset=UTF-8"
#         ]

#         for v in succeeded_values:
#             response = self.client.open('/v1/jobs', method='PUT', data='[]', content_type=v)
#             self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
#                               + '. Response body is : ' + response.data.decode('utf-8'))

#     def test_v1_jobs_put_check_input(self):
#         """Test case for bad input on v1_jobs_put
#         """
#         simple_job = MockJob().get_job()
#         failing_values = [
#             100,
#             "MyString",
#             {},
#             [100],
#             [""],
#             [{}],
#             [simple_job, 100],
#             [simple_job, ""],
#             [simple_job, {}]
#         ]

#         for v in failing_values:
#             response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(v))
#             self.assertStatus(response, 400, 'Should return 400. Value is: ' + str(v)
#                               + '. Response body is : ' + response.data.decode('utf-8'))

#         succeeded_values = [
#             [],
#             [simple_job]
#         ]

#         for v in succeeded_values:
#             response = self.client.open('/v1/jobs', method='PUT', content_type='application/json', data=json.dumps(v))
#             self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
#                               + '. Response body is : ' + response.data.decode('utf-8'))

#     def test_v1_jobs_put_check_add(self):
#         """Test case for adding job on v1_jobs_put
#         """
#         simple_job = MockJob().get_job()
#         values = [
#             {'jobs': [], 'len': 0},
#             {'jobs': [MockJob().get_job()], 'len': 1},
#             {'jobs': [MockJob().get_job(), MockJob().get_job()], 'len': 2},
#             {'jobs': [simple_job, simple_job], 'len': 1}
#         ]

#         for v in values:
#             self.setUp()
#             response = self.client.open('/v1/jobs', method='PUT',
#                                         content_type='application/json', data=json.dumps(v['jobs']))
#             self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
#                               + '. Response body is : ' + response.data.decode('utf-8'))

#             # Waiting for end of processing jobs update
#             self._pa.join_pushed_jobs()

#             # Check job in creation in PA
#             jobs_in_creation = self._pa.get_jobs_in_creation()
#             self.assertEqual(len(jobs_in_creation), 0)

#             # Check job created
#             jobs_created = self._pa.get_jobs()
#             self.assertEqual(len(jobs_created), v['len'])
#             self.tearDown()

#     def test_v1_jobs_put_check_add_in_continue(self):
#         """Test case for adding job on v1_jobs_put
#         """
#         simple_job = MockJob().get_job()
#         values = [
#             {'jobs': [], 'len': 0},
#             {'jobs': [MockJob().get_job()], 'len': 1},
#             {'jobs': [MockJob().get_job(), MockJob().get_job()], 'len': 2},
#             {'jobs': [simple_job, simple_job], 'len': 1},
#             {'jobs': [simple_job], 'len': 0},
#             {'jobs': [MockJob().get_job()], 'len': 1}
#         ]

#         total_length = 0
#         for v in values:
#             response = self.client.open('/v1/jobs', method='PUT',
#                                         content_type='application/json', data=json.dumps(v['jobs']))
#             self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
#                               + '. Response body is : ' + response.data.decode('utf-8'))

#             # Waiting for end of processing jobs update
#             self._pa.join_pushed_jobs()

#             # Check job in creation in PA
#             jobs_in_creation = self._pa.get_jobs_in_creation()
#             self.assertEqual(len(jobs_in_creation), 0)

#             total_length += v['len']
#             # Check job created
#             jobs_created = self._pa.get_jobs()
#             self.assertEqual(len(jobs_created), total_length)

#     def test_v1_jobs_put_check_callback_job_update(self):
#         """Test case for adding job on v1_jobs_put
#         """

#         def get_new_jobs(pa):
#             return {
#                 'name': 'my-job'
#             }
#         self._pa.set_callback_jobs_provider(get_new_jobs)

#         # Governor call /v1/jobs to get jobs to schedule.
#         # Prepare jobs in parallel and return an empty array
#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
#         jobs_ops = response.get_json()
#         self.assertIn('submit', jobs_ops)
#         jobs_to_create = jobs_ops['submit']
#         self.assertEqual(len(jobs_to_create), 0)

#         # Wait end of jobs prepatation
#         self._pa._prepare_job_thread.join()

#         # Governor call /v1/jobs a second time to get jobs to schedule
#         response = self.client.open('/v1/jobs', method='GET')
#         self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
#         jobs_ops = response.get_json()
#         self.assertIn('submit', jobs_ops)
#         jobs_to_create = jobs_ops['submit']
#         # Should return job 'my-job'
#         self.assertEqual(len(jobs_to_create), 1)
#         self.assertEqual('my-job', jobs_to_create[0]['name'])

#         # Check job in creation in PA
#         jobs_in_creation = self._pa.get_jobs_in_creation()
#         self.assertEqual(len(jobs_in_creation), 1)
#         self.assertEqual('my-job', jobs_in_creation[0].name)

#         # Check job created
#         jobs_created = self._pa.get_jobs()
#         self.assertEqual(len(jobs_created), 0)

#         in_creation_job = MockJob(**jobs_to_create[0]).get_job()
#         simple_job = MockJob().get_job()
#         simple_job_updated = copy.deepcopy(simple_job)
#         simple_job_updated.state = 'QUEUED'
#         simple_job2 = MockJob().get_job()

#         values = [
#             {
#                 'jobs': [],
#                 'callback': {
#                     'should_call': False,
#                     'called': False  # Will be updated or not by callback_job_update
#                 },
#                 'events': []
#             },
#             {
#                 'jobs': [in_creation_job],
#                 'callback': {
#                     'should_call': True,
#                     'called': False  # Will be updated or not by callback_job_update
#                 },
#                 'events': [{
#                     'update': list(diff(jobs_in_creation[0].to_dict(), in_creation_job.to_dict())),
#                     'state': JobEventState.CREATED
#                 }]
#             },
#             {
#                 'jobs': [simple_job],
#                 'callback': {
#                     'should_call': True,
#                     'called': False  # Will be updated or not by callback_job_update
#                 },
#                 'events': [{
#                     'update': list(diff({}, simple_job.to_dict())),
#                     'state': JobEventState.ADDED
#                 }]
#             },
#             {
#                 'jobs': [simple_job],
#                 'callback': {
#                     'should_call': False,
#                     'called': False  # Will be updated or not by callback_job_update
#                 },
#                 'events': []
#             },
#             {
#                 'jobs': [simple_job2, simple_job2],
#                 'callback': {
#                     'should_call': True,
#                     'called': False  # Will be updated or not by callback_job_update
#                 },
#                 'events': [{
#                     'update': list(diff({}, simple_job2.to_dict())),
#                     'state': JobEventState.ADDED
#                 }]
#             },
#             {
#                 'jobs': [simple_job_updated],
#                 'callback': {
#                     'should_call': True,
#                     'called': False  # Will be updated or not by callback_job_update
#                 },
#                 'events': [{
#                     'update': list(diff(simple_job.to_dict(), simple_job_updated.to_dict())),
#                     'state': JobEventState.UPDATED
#                 }]
#             }
#         ]

#         current_value = None

#         # Callback
#         def callback_job_update(event):
#             self.assertIn('pa', event)
#             current_value['callback']['called'] = True
#             self.assertEqual(len(event.jobs), len(current_value['events']))
#             for (e, e_check) in zip(event.jobs, current_value['events']):
#                 self.assertEqual(e['state'], e_check['state'])
#                 self.assertEqual(sorted(e['update']), sorted(e_check['update']))

#         self._pa.subscribe_jobs_update(callback_job_update)

#         # For each values, call PUT
#         for v in values:
#             current_value = v
#             response = self.client.open('/v1/jobs', method='PUT',
#                                         content_type='application/json', data=json.dumps(v['jobs']))
#             self.assertStatus(response, 200, 'Should return 200. Value is: ' + str(v)
#                               + '. Response body is : ' + response.data.decode('utf-8'))

#             # Waiting for end of processing jobs update
#             self._pa.join_pushed_jobs()

#         # Check if callback was called
#         for v in values:
#             self.assertEqual(v['callback']['should_call'], v['callback']['called'])

#     def test_v1_status_get(self):
#         """Test case for v1_status_get
#         """
#         response = self.client.open('/v1/status', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         self.assertEqual(len(jobs), 0)

#     def test_v1_status_get_with_one_job(self):
#         """Test case for v1_status_get
#         """
#         # Insert a fake job in ProcessAgent
#         simple_job = MockJob(name='gsm').get_job()
#         self._pa._process_agent_jobs[simple_job.id] = simple_job

#         response = self.client.open('/v1/status', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         self.assertEqual(len(jobs), 1)
#         job = Job.from_dict(jobs[0])
#         self.assertEqual(job.name, 'gsm')

#     def test_v1_status_get_limit_sort_offset(self):
#         """Test case for v1_status_get with limit, offset and sort
#         """
#         # Insert fake jobs in ProcessAgent

#         prefix_id = "2c5a1103-c63f-401d-b95f-fd73b8141"
#         name_idx = 0
#         for i in range(10):
#             j = MockJob(id="{}{:0>3}".format(prefix_id, 100-i),
#                         name="{:0>3}".format(name_idx),
#                         createdOn="2018-10-02 {:0>2}:{:0>2}:59Z".format(10 + (i // 60), i % 60)).get_job()
#             self._pa._process_agent_jobs[j.id] = j
#             name_idx += 1
#         # Same date, different ID
#         for i in range(10):
#             j = MockJob(id="{}{:0>3}".format(prefix_id, 200-i),
#                         name="{:0>3}".format(name_idx),
#                         createdOn="2018-10-02 {:0>2}:{:0>2}:59Z".format(10 + (i // 60), i % 60)).get_job()
#             self._pa._process_agent_jobs[j.id] = j
#             name_idx += 1

#         response = self.client.open('/v1/status', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         self.assertEqual(len(jobs), 20)

#         # Default sort by createdOn:asc
#         response = self.client.open('/v1/status?limit=5', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "100",
#             "200",
#             "099",
#             "199",
#             "098"
#         ])

#         # Limit to 5 jobs
#         response = self.client.open('/v1/status?limit=5&sort=name', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "100",
#             "099",
#             "098",
#             "097",
#             "096"
#         ])

#         # Limit to 5 jobs with an offset of 5
#         response = self.client.open('/v1/status?limit=5&offset=5&sort=name', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "095",
#             "094",
#             "093",
#             "092",
#             "091"
#         ])

#         # Limit to 5 jobs with an offset of -5
#         response = self.client.open('/v1/status?offset=-5&limit=5&sort=name', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "195",
#             "194",
#             "193",
#             "192",
#             "191"
#         ])

#         # Jobs with an offset of -5
#         response = self.client.open('/v1/status?offset=-5&sort=name', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "195",
#             "194",
#             "193",
#             "192",
#             "191"
#         ])

#         # Jobs with an offset of -5 and a limit of -2
#         response = self.client.open('/v1/status?offset=-5&limit=-2&sort=name', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "195",
#             "194",
#             "193"
#         ])

#         # Jobs with an offset of 15 and a limit of -2
#         response = self.client.open('/v1/status?offset=15&limit=-2&sort=name', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "195",
#             "194",
#             "193"
#         ])

#         # Sort by id ascending and limit to 5 jobs
#         response = self.client.open('/v1/status?limit=5&sort=id', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "091",
#             "092",
#             "093",
#             "094",
#             "095"
#         ])

#         # Sort by id ascending and limit to 5 jobs
#         response = self.client.open('/v1/status?limit=5&sort=id:asc', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "091",
#             "092",
#             "093",
#             "094",
#             "095"
#         ])

#         # Sort by id ascending and limit to 5 jobs with an offset of 5
#         response = self.client.open('/v1/status?limit=5&sort=id:asc&offset=5', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "096",
#             "097",
#             "098",
#             "099",
#             "100"
#         ])

#         # Sort by id ascending and limit to 5 jobs with an offset of -5
#         response = self.client.open('/v1/status?limit=5&sort=id:asc&offset=-5', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "196",
#             "197",
#             "198",
#             "199",
#             "200"
#         ])

#         # Sort by id ascending and limit to 5 jobs
#         response = self.client.open('/v1/status?limit=5&sort=id:desc', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "200",
#             "199",
#             "198",
#             "197",
#             "196"
#         ])

#         # Sort by id ascending and limit to 5 jobs with an offset of 5
#         response = self.client.open('/v1/status?limit=5&sort=id:desc&offset=5', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "195",
#             "194",
#             "193",
#             "192",
#             "191"
#         ])

#         # Sort by created_on date and id and limit to 5 jobs
#         response = self.client.open('/v1/status?limit=5&sort=createdOn:desc&sort=id:asc', method='GET')
#         self.assert200(response, 'Response body is : ' + response.data.decode('utf-8'))
#         jobs = response.get_json()
#         ids = [j['id'][-3:] for j in jobs]
#         self.assertEqual(ids, [
#             "091",
#             "191",
#             "092",
#             "192",
#             "093"
#         ])

#         # Sort by an unknow key will return status code 400
#         response = self.client.open('/v1/status?sort=unknow', method='GET')
#         self.assert400(response, 'Response body is : ' + response.data.decode('utf-8'))


# if __name__ == '__main__':
#     import unittest
#     unittest.main()
