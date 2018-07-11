# -*- coding: utf-8 -*-
#
# test_flow_docker.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from __future__ import absolute_import

from tests import BaseTestCase
from borgy_process_agent import ProcessAgent, ProcessAgentMode
from borgy_process_agent.utils import memory_str_to_nbytes
from borgy_process_agent.job import State


class TestFlowDocker(BaseTestCase):
    """Flow tests with docker mode"""

    def setUp(self):
        if self._pa:
            self.tearDown()
        self._pa = ProcessAgent(mode=ProcessAgentMode.DOCKER, poll_interval=0.01, docker_tty=True)

    def tearDown(self):
        if self._pa:
            self._pa._remove()
        self._pa = None

    def test_docker_flow(self):
        """Test case for simple example with docker
        """

        idx_job = [0]
        commands = [
            'echo "step 1";trap "echo trap ; exit" SIGUSR1;echo "wait";read -t 120;echo done',
            'echo "step 2";trap "echo trap ; exit" SIGUSR1;echo "wait";read -t 120;echo done',
            'echo "step 3";trap "echo trap ; exit" SIGUSR1;echo "wait";read -t 120;echo done',
            'echo "step 4";trap "echo trap ; exit" SIGUSR1;echo "wait";read -t 120;echo done',
            'echo "step 5";trap "echo trap ; exit 1" SIGUSR1;echo "wait";read -t 120;echo done',
        ]

        def return_new_jobs(pa):
            idx_job[0] += 1
            if idx_job[0] > len(commands):
                return None
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

        def stop_job(job_name):
            jobs = self._pa.get_jobs_by_name(job_name)
            if jobs:
                for job in jobs:
                    self._pa._governor_jobs[job.id]['container'].kill('SIGUSR1')

        def kill_job(job_name):
            jobs = self._pa.get_jobs_by_name(job_name)
            if jobs:
                for job in jobs:
                    self._pa.kill_job(job.id)

        job_events = [
            {
                'events': [
                    {'name': 'job-1', 'state': State.RUNNING.value},
                ],
                'actions': []
            },
            {
                'events': [
                    {'name': 'job-2', 'state': State.RUNNING.value},
                ],
                'actions': []
            },
            {
                'events': [
                    {'name': 'job-3', 'state': State.RUNNING.value},
                ],
                'actions': []
            },
            {
                'events': [
                    {'name': 'job-4', 'state': State.RUNNING.value},
                ],
                'actions': [
                    [kill_job, 'job-3']
                ]
            },
            {
                'events': [
                    {'name': 'job-3', 'state': State.CANCELLED.value},
                    {'name': 'job-5', 'state': State.RUNNING.value},
                ],
                'actions': [
                    [stop_job, 'job-1']
                ]
            },
            {
                'events': [
                    {'name': 'job-1', 'state': State.SUCCEEDED.value},
                ],
                'actions': [
                    [stop_job, 'job-2']
                ]
            },
            {
                'events': [
                    {'name': 'job-2', 'state': State.SUCCEEDED.value},
                ],
                'actions': [
                    [stop_job, 'job-4']
                ]
            },
            {
                'events': [
                    {'name': 'job-4', 'state': State.SUCCEEDED.value},
                ],
                'actions': [
                    [stop_job, 'job-5']
                ]
            },
            {
                'events': [
                    {'name': 'job-5', 'state': State.FAILED.value},
                ],
                'actions': []
            }
        ]
        idx_job_events = [0]

        def jobs_update(event):
            if event.jobs:
                events = []
                print('Event '+str(idx_job_events[0])+':')
                for j in event.jobs:
                    print("\tMy job {} updated to {}".format(j['job'].name, j['job'].state))
                    events.append({'name': j['job'].name, 'state': j['job'].state})
                self.assertCountEqual(job_events[idx_job_events[0]]['events'], events)

                for a in job_events[idx_job_events[0]]['actions']:
                    print("\tAction {} on job {}".format(a[0].__name__, a[1]))
                    a[0](a[1])
                idx_job_events[0] += 1

        self._pa.subscribe_jobs_update(jobs_update)

        self._pa.start()

    def test_docker_flow_rerun(self):
        """Test case for rerun with docker
        """

        idx_job = [0]
        commands = [
            'echo "step 1";trap "echo trap ; exit $(( 1 - $BORGY_RUN_INDEX ))" SIGUSR1;echo "wait";read -t 120',
            'echo "step 2";trap "echo trap ; exit" SIGUSR1;echo "wait";read -t 120',
        ]

        def return_new_jobs(pa):
            idx_job[0] += 1
            if idx_job[0] > len(commands):
                return None
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

        def stop_job(job_name):
            jobs = self._pa.get_jobs_by_name(job_name)
            if jobs:
                for job in jobs:
                    self._pa._governor_jobs[job.id]['container'].kill('SIGUSR1')

        def rerun_job(job_name):
            jobs = self._pa.get_jobs_by_name(job_name)
            if jobs:
                for job in jobs:
                    self._pa.rerun_job(job.id)

        def kill_job(job_name):
            jobs = self._pa.get_jobs_by_name(job_name)
            if jobs:
                for job in jobs:
                    self._pa.kill_job(job.id)

        job_events = [
            {
                'events': [
                    {'name': 'job-1', 'state': State.RUNNING.value},
                ],
                'actions': []
            },
            {
                'events': [
                    {'name': 'job-2', 'state': State.RUNNING.value},
                ],
                'actions': [
                    [stop_job, 'job-1']
                ]
            },
            {
                'events': [
                    {'name': 'job-1', 'state': State.FAILED.value},
                ],
                'actions': [
                    [rerun_job, 'job-1']
                ]
            },
            {
                'events': [
                    {'name': 'job-1', 'state': State.RUNNING.value},
                ],
                'actions': [
                    [stop_job, 'job-1']
                ]
            },
            {
                'events': [
                    {'name': 'job-1', 'state': State.SUCCEEDED.value},
                ],
                'actions': [
                    [stop_job, 'job-2']
                ]
            },
            {
                'events': [
                    {'name': 'job-2', 'state': State.SUCCEEDED.value},
                ],
                'actions': []
            }
        ]
        idx_job_events = [0]

        def jobs_update(event):
            if event.jobs:
                events = []
                print('Event '+str(idx_job_events[0])+':')
                for j in event.jobs:
                    print("\tMy job {} updated to {}".format(j['job'].name, j['job'].state))
                    events.append({'name': j['job'].name, 'state': j['job'].state})
                self.assertCountEqual(job_events[idx_job_events[0]]['events'], events)

                for a in job_events[idx_job_events[0]]['actions']:
                    print("\tAction {} on job {}".format(a[0].__name__, a[1]))
                    a[0](a[1])
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
            'OMP_THREAD_LIMIT': cpu,
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

    def test_container_with_max_run_time(self):
        """Test case to check container with max run time
        """
        idx_job = [0]
        commands = [
            ['bash', '-c', 'sleep 60']
        ]

        def return_new_jobs(pa):
            idx_job[0] += 1
            if idx_job[0] > len(commands):
                return None
            res = {
                'command': commands[idx_job[0] - 1],
                'name': 'job-'+str(idx_job[0]),
                'image': 'ubuntu:16.04',
                'maxRunTimeSecs': 3
            }
            return res

        self._pa.set_callback_jobs_provider(return_new_jobs)

        self._pa.start()

        jobs = self._pa.get_jobs()
        self.assertEqual(len(jobs), 1)

        job = list(jobs.values())[0]
        self.assertEqual(job.state, State.FAILED.value)


if __name__ == '__main__':
    import unittest
    unittest.main()
