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
from borgy_process_agent.utils import memory_str_to_nbytes
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
            if idx_job[0] > len(commands):
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
                        print("\tKill job {}".format(jobs[0].name))
                        event.pa.kill_job(jobs[0].id)
                self.assertCountEqual(job_events[idx_job_events[0]], events)
                idx_job_events[0] += 1

        self._pa.subscribe_jobs_update(jobs_update)

        self._pa.start()

    def test_docker_flow_rerun(self):
        """Test case for rerun with docker
        """

        idx_job = [0]
        commands = [
            'sleep 5 ; exit $(( 1 - $BORGY_RUN_INDEX ))',
            'sleep 15'
        ]

        def return_new_jobs(pa):
            idx_job[0] += 1
            if idx_job[0] > len(commands):
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
                {'name': 'job-1', 'state': State.FAILED.value},
            ],
            [
                {'name': 'job-1', 'state': State.RUNNING.value},
            ],
            [
                {'name': 'job-1', 'state': State.SUCCEEDED.value},
            ],
            [
                {'name': 'job-2', 'state': State.SUCCEEDED.value},
            ]
        ]
        idx_job_events = [0]

        def jobs_update(event):
            if event.jobs:
                events = []
                print('Event '+str(idx_job_events[0])+':')
                for j in event.jobs:
                    print("\tMy job {} updated to {}".format(j['job'].name, j['job'].state))
                    if j['job'].name == 'job-1' and j['job'].state == State.FAILED.value:
                        print("\tRerun job {}".format(j['job'].name))
                        event.pa.rerun_job(j['job'].id)
                    events.append({'name': j['job'].name, 'state': j['job'].state})
                    if j['job'].name == 'job-4' and j['job'].state == State.RUNNING.value:
                        jobs = event.pa.get_jobs_by_name('job-3')
                        event.pa.kill_job(jobs[0].id)
                self.assertCountEqual(job_events[idx_job_events[0]], events)
                idx_job_events[0] += 1

        self._pa.subscribe_jobs_update(jobs_update)

        self._pa.start()

    def test_borgy_env_var(self):
        """Test case for injection of environment variables in docker
        """
        idx_job = [0]
        commands = [
            ['bash', '-c', 'env|sort']
        ]

        cpu = 2
        memory_bytes = memory_str_to_nbytes('2Gi')

        def return_new_jobs(pa):
            idx_job[0] += 1
            if idx_job[0] > len(commands):
                return None
            res = {
                'command': commands[idx_job[0] - 1],
                'name': 'job-'+str(idx_job[0]),
                'image': 'ubuntu:16.04',
                'reqRamGbytes': 2,
                'reqCores': cpu,
                'reqGpus': 4,
            }
            return res

        self._pa.set_callback_jobs_provider(return_new_jobs)

        self._pa.start()

        jobs = self._pa.get_jobs()
        self.assertEqual(len(jobs), 1)

        job = list(jobs.values())[0]
        self.assertEqual(job.state, State.SUCCEEDED.value)

        envs = {
            'BORGY_CPU_LIMIT': cpu,
            'BORGY_JOB_ID': job.id,
            'BORGY_MEMORY_LIMIT': memory_bytes,
            'BORGY_RUN_INDEX': 0,
            'BORGY_TARGET_NODE': 'docker',
            'BORGY_USER': 'MyUser',
            'PRETEND_CPUS': cpu,
            'PRETEND_MEM': memory_bytes,
            'OMP_NUM_THREADS': cpu,
            'HOME': '/home/MyUser',
            'NVIDIA_VISIBLE_DEVICES': '0,1,2,3',
        }
        result = str(job.runs[-1].result)
        for k, v in envs.items():
            e = str(k) + '=' + str(v)
            self.assertIn(e, result)

    def test_borgy_env_var_overwrite(self):
        """Test case to overwrite environment variables injected in docker
        """
        idx_job = [0]
        commands = [
            ['bash', '-c', 'env|sort']
        ]

        def return_new_jobs(pa):
            idx_job[0] += 1
            if idx_job[0] > len(commands):
                return None
            res = {
                'command': commands[idx_job[0] - 1],
                'name': 'job-'+str(idx_job[0]),
                'image': 'ubuntu:16.04',
                'reqRamGbytes': 2,
                'reqCores': 2,
                'reqGpus': 4,
                'environmentVars': [
                    'BORGY_JOB_ID=aaaaaa',  # Should be NOT overwrite
                    'NVIDIA_VISIBLE_DEVICES=5',  # Should be overwrite
                ]
            }
            return res

        self._pa.set_callback_jobs_provider(return_new_jobs)

        self._pa.start()

        jobs = self._pa.get_jobs()
        self.assertEqual(len(jobs), 1)

        job = list(jobs.values())[0]
        self.assertEqual(job.state, State.SUCCEEDED.value)

        envs = {
            'BORGY_JOB_ID': job.id,
            'NVIDIA_VISIBLE_DEVICES': '5',
        }
        result = str(job.runs[-1].result)
        for k, v in envs.items():
            e = str(k) + '=' + str(v)
            self.assertIn(e, result)


if __name__ == '__main__':
    import unittest
    unittest.main()
