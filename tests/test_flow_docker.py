# -*- coding: utf-8 -*-
#
# test_jobs_controller.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from __future__ import absolute_import

import time
from tests import BaseTestCase
from borgy_process_agent import ProcessAgent, ProcessAgentMode
from borgy_process_agent.job import State


class TestFlowDocker(BaseTestCase):
    """Flow tests with docker mode"""

    def setUp(self):
        if self._pa:
            self.tearDown()
        self._pa = ProcessAgent(mode=ProcessAgentMode.DOCKER, poll_interval=0.01, docker_stop_timeout=1)

    def tearDown(self):
        if self._pa:
            self._pa.delete()
        self._pa = None

    def test_docker_flow(self):
        """Test case for simple example with docker
        """

        idx_job = [0]
        commands = [
            'echo "step 1";for i in $(seq 1 1);do echo $i;sleep 30;done;echo done',
            'echo "step 2";for i in $(seq 1 1);do echo $i;sleep 30;done;echo done',
            'echo "step 3";for i in $(seq 1 1);do echo $i;sleep 60;done;echo done',
            'echo "step 4";for i in $(seq 1 1);do echo $i;sleep 25;done;echo done',
            'echo "step 5";for i in $(seq 1 1);do echo $i;sleep 20;done;echo done;exit 1',
        ]

        def return_new_jobs(pa):
            idx_job[0] += 1
            if idx_job[0] > 5:
                return None
            time.sleep(idx_job[0])
            res = {
                'command': [
                    'bash',
                    '-c',
                    commands[idx_job[0] - 1]
                ],
                'name': 'job-'+str(idx_job[0]),
                'image': 'ubuntu:16.04'
            }
            return res

        self._pa.set_callback_jobs_provider(return_new_jobs)

        job_events = [
            [
                {'name': 'job-1', 'state': State.RUNNING.value},
            ],
            [
                {'name': 'job-2', 'state': State.RUNNING.value},
            ],
            [
                {'name': 'job-3', 'state': State.RUNNING.value},
            ],
            [
                {'name': 'job-4', 'state': State.RUNNING.value},
            ],
            [
                {'name': 'job-5', 'state': State.RUNNING.value},
                {'name': 'job-3', 'state': State.CANCELLED.value},
            ],
            [
                {'name': 'job-1', 'state': State.SUCCEEDED.value},
            ],
            [
                {'name': 'job-2', 'state': State.SUCCEEDED.value},
            ],
            [
                {'name': 'job-4', 'state': State.SUCCEEDED.value},
            ],
            [
                {'name': 'job-5', 'state': State.FAILED.value},
            ],
        ]
        idx_job_events = [0]

        def jobs_update(event):
            if event.jobs:
                events = []
                print('Event '+str(idx_job_events[0])+':')
                for j in event.jobs:
                    print("\tMy job {} updated to {}".format(j['job'].name, j['job'].state))
                    events.append({'name': j['job'].name, 'state': j['job'].state})
                    if j['job'].name == 'job-4' and j['job'].state == State.RUNNING.value:
                        jobs = event.pa.get_jobs_by_name('job-3')
                        event.pa.kill_job(jobs[0].id)
                self.assertCountEqual(job_events[idx_job_events[0]], events)
                idx_job_events[0] += 1

        self._pa.subscribe_jobs_update(jobs_update)

        self._pa.start()


if __name__ == '__main__':
    import unittest
    unittest.main()
