# -*- coding: utf-8 -*-
#
# test_process_agent.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from __future__ import absolute_import


import copy
import time
import threading
from tests import BaseTestCaseDocker
from tests.utils import MockJob
from borgy_process_agent.job import State, Restart


class TestProcessAgentDocker(BaseTestCaseDocker):
    """ProcessAgent Docker Mode integration test"""

    def test_pa_kill_job(self):
        """Test case for kill_job
        """
        # Insert fake jobs in ProcessAgent
        simple_job_spec = MockJob(name='gsm1', state=State.INTERRUPTED.value).get_job()
        simple_job_spec2 = MockJob(name='gsm2', state=State.INTERRUPTED.value).get_job()
        simple_job_spec3 = MockJob(name='gsm3', state=State.INTERRUPTED.value).get_job()
        jobs = [simple_job_spec, simple_job_spec2, simple_job_spec3]
        for i, j in enumerate(jobs):
            jobs[i] = self._pa._create_job(j)
        self._pa._push_jobs(jobs)

        # Waiting for end of processing jobs update
        self._pa.join_pushed_jobs()

        # Should not call job_service
        is_updated = self._pa.kill_job('random')
        self.assertEqual(is_updated, False)

        # Should not call job_service
        is_updated = self._pa.kill_job(jobs[0].id)
        self.assertEqual(is_updated, True)

        # Should call job_service
        is_updated = self._pa.kill_job(jobs[1].id)
        self.assertEqual(is_updated, True)

        # Waiting for end of processing jobs update
        self._pa.join_pushed_jobs()

        # Test if state is directly updated to CANCELLING
        job = self._pa.get_job_by_id(jobs[1].id)
        self.assertEqual(job.state, State.CANCELLING.value)

        # Call a second time should not call job service
        is_updated = self._pa.kill_job(jobs[1].id)
        self.assertEqual(is_updated, False)
        job = self._pa.get_job_by_id(jobs[1].id)
        self.assertEqual(job.state, State.CANCELLING.value)

    def test_pa_rerun_job(self):
        """Test case for rerun_job
        """
        # Insert fake jobs in ProcessAgent
        simple_job_spec = MockJob(name='gsm1', state=State.FAILED.value).get_job()
        simple_job_spec2 = MockJob(name='gsm2', state=State.FAILED.value).get_job()
        simple_job_spec3 = MockJob(name='gsm3', state=State.FAILED.value).get_job()
        jobs = [simple_job_spec, simple_job_spec2, simple_job_spec3]
        for i, j in enumerate(jobs):
            jobs[i] = self._pa._create_job(j)
        self._pa._push_jobs(copy.deepcopy(jobs))
        self._pa.join_pushed_jobs()

        self._pa._update_job_state(jobs[1].id, State.QUEUED)
        self._pa._push_jobs(copy.deepcopy([jobs[1]]))
        self._pa.join_pushed_jobs()
        self._pa._update_job_state(jobs[1].id, State.CANCELLING)
        self._pa._push_jobs(copy.deepcopy([jobs[1]]))
        self._pa.join_pushed_jobs()
        self._pa._update_job_state(jobs[1].id, State.CANCELLED)
        self._pa._push_jobs(copy.deepcopy([jobs[1]]))
        self._pa.join_pushed_jobs()

        # Should not add job_id in rerun list
        is_updated = self._pa.rerun_job('random')
        self.assertEqual(is_updated, False)

        # Should not add job_id in rerun list
        is_updated = self._pa.rerun_job(jobs[0].id)
        self.assertEqual(is_updated, False)

        # Should add job_id in rerun list
        is_updated = self._pa.rerun_job(jobs[1].id)
        self.assertEqual(is_updated, True)
        # Test if job is added in job list to rerun
        self.assertEqual(self._pa.get_jobs_to_rerun(), [jobs[1].id])
        job = self._pa.get_job_by_id(jobs[1].id)
        self.assertEqual(job.state, State.CANCELLED.value)

        # Call a second time should not add job_id in rerun list
        is_updated = self._pa.rerun_job(jobs[1].id)
        self.assertEqual(is_updated, False)
        self.assertEqual(self._pa.get_jobs_to_rerun(), [jobs[1].id])

        # Update and push update
        self._pa._update_job_state(jobs[1].id, State.QUEUING)
        self._pa._push_jobs([self._pa._governor_jobs[jobs[1].id]['job']])
        self._pa.join_pushed_jobs()

        # Test if job is removed from job list to rerun
        self.assertEqual(self._pa.get_jobs_to_rerun(), [])
        job = self._pa.get_job_by_id(jobs[1].id)
        self.assertEqual(job.state, State.QUEUING.value)

        # Call a second time should not add job in rerun list
        is_updated = self._pa.rerun_job(jobs[1].id)
        self.assertEqual(is_updated, False)
        job = self._pa.get_job_by_id(jobs[1].id)
        self.assertEqual(job.state, State.QUEUING.value)

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
        # wait 2s
        time.sleep(2)
        # Stop server
        self._pa.stop()
        # wait 3s
        time.sleep(3)
        # Start should go to the next instruction
        self.assertEqual(count_call[0], 1)

    def test_update_state_unknow_job(self):
        """Test case for update state of unknow job
        """
        with self.assertRaises(ValueError):
            self._pa._update_job_state('unknow', State.QUEUED)

    def test_node_name(self):
        """Test case for node_name
        """
        # Insert fak jobs in ProcessAgent
        job = MockJob(name='gsm1', state=State.INTERRUPTED.value).get_job()

        job = self._pa._create_job(job)
        self.assertEqual(job.state, State.QUEUING.value)
        self.assertEqual(len(job.runs), 1)
        self.assertEqual(job.runs[-1].state, State.QUEUING.value)
        self.assertEqual(job.runs[-1].node_name, 'docker')

    def test_ip(self):
        """Test case for ip
        """
        # Insert fak jobs in ProcessAgent
        job = MockJob(name='gsm1', state=State.INTERRUPTED.value).get_job()

        job = self._pa._create_job(job)
        self.assertEqual(job.state, State.QUEUING.value)
        self.assertEqual(len(job.runs), 1)
        self.assertEqual(job.runs[-1].state, State.QUEUING.value)
        self.assertEqual(job.runs[-1].ip, '127.0.0.1')

    def test_update_job_state(self):
        """Test case for update job state
        """
        # Insert fak jobs in ProcessAgent
        job = MockJob(name='gsm1', state=State.INTERRUPTED.value).get_job()

        job = self._pa._create_job(job)
        job_id = job.id
        self.assertEqual(job.state, State.QUEUING.value)
        self.assertEqual(len(job.runs), 1)
        self.assertEqual(job.runs[-1].state, State.QUEUING.value)

        job = self._pa._update_job_state(job_id, State.QUEUED)
        self.assertEqual(job['job'].state, State.QUEUED.value)
        self.assertEqual(len(job['job'].runs), 1)
        self.assertEqual(job['job'].runs[-1].state, State.QUEUED.value)

        job = self._pa._update_job_state(job_id, State.RUNNING)
        self.assertEqual(job['job'].state, State.RUNNING.value)
        self.assertEqual(len(job['job'].runs), 1)
        self.assertEqual(job['job'].runs[-1].state, State.RUNNING.value)

        # kill
        job = self._pa._update_job_state(job_id, State.CANCELLING)
        self.assertEqual(job['job'].state, State.CANCELLING.value)
        self.assertEqual(len(job['job'].runs), 1)
        self.assertEqual(job['job'].runs[-1].state, State.CANCELLING.value)

        job = self._pa._update_job_state(job_id, State.CANCELLED)
        self.assertEqual(job['job'].state, State.CANCELLED.value)
        self.assertEqual(len(job['job'].runs), 1)
        self.assertEqual(job['job'].runs[-1].state, State.CANCELLED.value)

        # rerun
        job = self._pa._update_job_state(job_id, State.QUEUING)
        self.assertEqual(job['job'].state, State.QUEUING.value)
        self.assertEqual(len(job['job'].runs), 2)
        self.assertEqual(job['job'].runs[0].state, State.CANCELLED.value)
        self.assertEqual(job['job'].runs[1].state, State.QUEUING.value)

        job = self._pa._update_job_state(job_id, State.QUEUED)
        self.assertEqual(job['job'].state, State.QUEUED.value)
        self.assertEqual(len(job['job'].runs), 2)
        self.assertEqual(job['job'].runs[0].state, State.CANCELLED.value)
        self.assertEqual(job['job'].runs[1].state, State.QUEUED.value)

        job = self._pa._update_job_state(job_id, State.RUNNING)
        self.assertEqual(job['job'].state, State.RUNNING.value)
        self.assertEqual(len(job['job'].runs), 2)
        self.assertEqual(job['job'].runs[0].state, State.CANCELLED.value)
        self.assertEqual(job['job'].runs[1].state, State.RUNNING.value)

        job = self._pa._update_job_state(job_id, State.FAILED)
        self.assertEqual(job['job'].state, State.FAILED.value)
        self.assertEqual(len(job['job'].runs), 2)
        self.assertEqual(job['job'].runs[0].state, State.CANCELLED.value)
        self.assertEqual(job['job'].runs[1].state, State.FAILED.value)
        self.assertEqual(job['job'].runs[1].exit_code, 255)

        job = self._pa._update_job_state(job_id, State.SUCCEEDED)
        self.assertEqual(job['job'].state, State.SUCCEEDED.value)
        self.assertEqual(len(job['job'].runs), 2)
        self.assertEqual(job['job'].runs[0].state, State.CANCELLED.value)
        self.assertEqual(job['job'].runs[1].state, State.SUCCEEDED.value)
        self.assertEqual(job['job'].runs[1].exit_code, 0)

        job = self._pa._update_job_state(job_id, State.INTERRUPTED)
        self.assertEqual(job['job'].state, State.INTERRUPTED.value)
        self.assertEqual(len(job['job'].runs), 2)
        self.assertEqual(job['job'].runs[0].state, State.CANCELLED.value)
        self.assertEqual(job['job'].runs[1].state, State.INTERRUPTED.value)

        job2 = MockJob(name='gsm2', state=State.INTERRUPTED.value, restart=Restart.ON_INTERRUPTION.value).get_job()
        job2 = self._pa._create_job(job2)
        job2 = self._pa._update_job_state(job2.id, State.INTERRUPTED)
        self.assertEqual(job2['job'].state, State.QUEUING.value)
        self.assertEqual(len(job2['job'].runs), 2)
        self.assertEqual(job2['job'].runs[0].state, State.INTERRUPTED.value)
        self.assertEqual(job2['job'].runs[1].state, State.QUEUING.value)


if __name__ == '__main__':
    import unittest
    unittest.main()
