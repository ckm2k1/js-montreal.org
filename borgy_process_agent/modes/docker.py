# -*- coding: utf-8 -*-
#
# docker.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import copy
import math
import time
import uuid
import docker
import logging
import pkg_resources
from typing import List
from dateutil.parser import parse
from borgy_process_agent import ProcessAgentBase, process_agents
from borgy_process_agent.controllers import jobs_controller
from borgy_process_agent.job import State, Restart
from borgy_process_agent.utils import get_now, get_now_isoformat, cpu_str_to_ncpu, memory_str_to_nbytes
from borgy_process_agent_api_server.models.job import Job, JobRuns
from borgy_process_agent_api_server.models.job_spec import JobSpec

logger = logging.getLogger(__name__)

borgy_process_agent_version = pkg_resources.get_distribution('borgy_process_agent').version


class ProcessAgent(ProcessAgentBase):
    """Process Agent for Docker
    """
    def __init__(self, **kwargs):
        """Constructor

        :rtype: NoReturn
        """
        self._job_id = kwargs.get('job_id', str(uuid.uuid4()))
        super().__init__(pa_job_id=self._job_id, pa_user='MyUser', **kwargs)
        self._docker = docker.from_env()
        self._poll_interval = kwargs.get('poll_interval', 10)

    def reset(self):
        """Reset Process Agent.

        :rtype: NoReturn
        """
        super().reset()
        self._running = False
        self._governor_jobs = {}

    def _run_job(self, job: Job):
        """Run a job in docker

        :rtype: NoReturn
        """
        cpu_count = math.ceil(cpu_str_to_ncpu(job.req_cores))
        mem = memory_str_to_nbytes(str(job.req_ram_gbytes) + 'Gi')
        gpus_list = ','.join([str(i) for i in range(job.req_gpus)])
        envs_injected_before = {
            'NVIDIA_VISIBLE_DEVICES': gpus_list,
        }
        envs_injected_after = {
            'BORGY_CPU_LIMIT': cpu_count,
            'BORGY_JOB_ID': job.id,
            'BORGY_MEMORY_LIMIT': mem,
            'BORGY_RUN_INDEX': (len(job.runs) - 1),
            'BORGY_TARGET_NODE': 'docker',
            'BORGY_USER': job.created_by,
            'PRETEND_CPUS': cpu_count,
            'PRETEND_MEM': mem,
            'OMP_NUM_THREADS': cpu_count,
            'OMP_THREAD_LIMIT': cpu_count,
            'HOME': '/home/' + job.created_by,
        }

        envs = []
        for k, v in envs_injected_before.items():
            envs.append(str(k) + '=' + str(v))
        envs += copy.copy(job.environment_vars)
        for k, v in envs_injected_after.items():
            envs.append(str(k) + '=' + str(v))

        logger.debug('\t\tStart container for job {} (name: {})'.format(job.id, job.name))
        run_kwargs = self._options.get('docker_run_options', {})
        if not isinstance(run_kwargs, dict):
            raise TypeError('docker_run_options must be a dict')

        container = self._docker.containers.run(
            name=job.id,
            image=job.image,
            command=job.command,
            environment=envs,
            labels=job.labels,
            cpu_count=cpu_count,
            mem_limit=mem,
            volumes=job.volumes,
            working_dir=job.workdir,
            detach=self._options.get('docker_detach', True),
            runtime=self._options.get('docker_runtime'),
            tty=self._options.get('docker_tty'),
            auto_remove=False,
            **run_kwargs
        )

        return container

    def _rerun_job(self, job_id: str) -> Job:
        job = self._update_job_state(job_id, State.QUEUING)
        logger.debug('\t\tRerun job {} (name: {})'.format(job_id, job['job'].name))
        return job

    def _kill_job(self, job_id: str) -> Job:
        job = self._update_job_state(job_id, State.CANCELLING)
        logger.debug('\t\tRerun job {} (name: {})'.format(job_id, job['job'].name))
        return job

    def _create_job(self, job_spec: JobSpec) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(**job_spec.to_dict())
        logger.debug('\t\tCreate new job {} (name: {})'.format(job_id, job.name))
        job.id = job_id
        job.runs = []
        self._governor_jobs[job_id] = {
            'job': job,
            'container': None,
            'status': ''
        }
        self._update_job_state(job_id, State.QUEUING)
        return job

    def _update_job_state(self, job_id, state: State) -> Job:
        if job_id not in self._governor_jobs:
            raise ValueError('job not found: {}'.format(job_id))

        job = self._governor_jobs[job_id]
        if job['job'].state != state.value:
            logger.debug('\t\tUpdate job {}: {} -> {}'.format(job_id, job['job'].state, state.value))
            job['job'].state = state.value
            if state == State.QUEUING:
                run = {
                    'createdOn': get_now_isoformat(),
                    'jobId': job_id,
                    'id': str(uuid.uuid4()),
                    'ip': '127.0.0.1',
                    'nodeName': 'docker',
                    'state': State.QUEUING.value
                }
                job['job'].runs.append(JobRuns.from_dict(run))
            elif state == State.QUEUED:
                job['job'].runs[-1].queued_on = get_now_isoformat()
                job['container'] = self._run_job(job['job'])
            elif state == State.RUNNING:
                if job['container']:
                    job['job'].runs[-1].started_on = job['container'].attrs['State']['StartedAt']
                else:
                    job['job'].runs[-1].started_on = get_now_isoformat()
            elif state == State.CANCELLING:
                job['job'].runs[-1].cancel_requested_on = get_now_isoformat()
                if job['container']:
                    job['container'].stop(timeout=self._options.get('docker_stop_timeout', 10))
            elif state == State.CANCELLED:
                ended_on = get_now_isoformat()
                if job['container']:
                    ended_on = job['container'].attrs['State']['FinishedAt']
                job['job'].runs[-1].cancelled_on = ended_on
                job['job'].runs[-1].ended_on = ended_on
            elif state == State.FAILED:
                ended_on = get_now_isoformat()
                if job['container']:
                    ended_on = job['container'].attrs['State']['FinishedAt']
                job['job'].runs[-1].ended_on = ended_on
                job['job'].runs[-1].exit_code = 255
                if job['container']:
                    job['job'].runs[-1].result = job['container'].logs(stdout=True, stderr=True)
                    if self._options.get('docker_remove', True):
                        job['container'].remove()
            elif state == State.SUCCEEDED:
                ended_on = get_now_isoformat()
                if job['container']:
                    ended_on = job['container'].attrs['State']['FinishedAt']
                job['job'].runs[-1].ended_on = ended_on
                job['job'].runs[-1].exit_code = 0
                if job['container']:
                    job['job'].runs[-1].result = job['container'].logs(stdout=True, stderr=True)
                    if self._options.get('docker_remove', True):
                        job['container'].remove()
            elif state == State.INTERRUPTED:
                if job['job'].restart == Restart.ON_INTERRUPTION.value:
                    job['job'].runs[-1].state = State.INTERRUPTED.value
                    job['job'].runs[-1].ended_on = get_now_isoformat()
                    if job['container']:
                        job['job'].runs[-1].result = job['container'].logs(stdout=True, stderr=True)
                    new_run = {
                        'createdOn': get_now_isoformat(),
                        'jobId': job_id,
                        'id': str(uuid.uuid4()),
                        'ip': '127.0.0.1',
                        'nodeName': 'docker',
                        'state': State.QUEUING.value
                    }
                    job['job'].runs.append(JobRuns.from_dict(new_run))
                    job['job'].state = State.QUEUING.value

            if job['job'].runs:
                job['job'].runs[-1].state = job['job'].state

        return job

    def _start_jobs(self):
        for job_id, job in self._governor_jobs.items():
            if job['job'].state == State.QUEUING.value:
                self._update_job_state(job_id, State.QUEUED)

    def _check_max_run_time(self):
        for job_id, job in self._governor_jobs.items():
            if job['job'].state == State.RUNNING.value and job['job'].max_run_time_secs > 0:
                run = job['job'].runs[-1]
                started_on = parse(run.started_on)
                if (get_now() - started_on).total_seconds() > job['job'].max_run_time_secs:
                    logger.debug('\t\tStop job {}: max run time exceed ({} seconds)'
                                 .format(job_id, job['job'].max_run_time_secs))
                    if job['container']:
                        job['container'].stop(timeout=self._options.get('docker_stop_timeout', 10))

    def _check_jobs_update(self) -> List[Job]:
        containers = self._docker.containers.list(all=True, ignore_removed=True)
        job_ids_succedded = [
            c.name for c in containers
            if c.attrs['State']['ExitCode'] == 0 and not c.attrs['State']['Running'] and not c.attrs['State']['Dead']
        ]

        updates = {}
        for c in containers:
            job_id = c.name
            if job_id in self._governor_jobs:
                job = self._governor_jobs[job_id]
                job['container'] = c
                current_state = job['job'].state

                if job['status'] != c.status:
                    if c.status == 'running':
                        self._update_job_state(job_id, State.RUNNING)
                    elif c.status == 'exited':
                        if job['job'].state == State.CANCELLING.value:
                            self._update_job_state(job_id, State.CANCELLED)
                        elif job_id in job_ids_succedded:
                            self._update_job_state(job_id, State.SUCCEEDED)
                        else:
                            self._update_job_state(job_id, State.FAILED)
                job['status'] = c.status

                if job['job'].state != current_state:
                    updates[job_id] = copy.deepcopy(job['job'])

        return list(updates.values())

    def start(self):
        from timeit import default_timer as timer
        """Start process agent

        :rtype: NoReturn
        """
        self._insert()
        self._running = True
        logger.debug('Start Process Agent server')
        while self._running:
            start_time = timer()
            # Get job from PA
            logger.debug(' - Get job from PA')
            jobs = jobs_controller.v1_jobs_get()
            code = 200
            if isinstance(jobs, set):
                jobs, code = jobs

            if code != 200:
                logger.warning('Error to get jobs, got: {}'.format(jobs))
            elif isinstance(jobs, dict):
                if isinstance(jobs['submit'], list):
                    for j in jobs['submit']:
                        self._create_job(j)
                if isinstance(jobs['rerun'], list):
                    for j in jobs['rerun']:
                        self._rerun_job(j)
                if isinstance(jobs['kill'], list):
                    for j in jobs['kill']:
                        self._kill_job(j)

            # Start queuing jobs
            logger.debug(' - Start queuing jobs')
            self._start_jobs()

            # Check running container with max run time
            logger.debug(' - Check running container with max run time')
            self._check_max_run_time()

            # Check update from container
            logger.debug(' - Check update from container')
            updated_jobs = self._check_jobs_update()

            # Push update to PA
            logger.debug(' - Push update to PA')
            for pa in process_agents:
                pa._push_jobs(updated_jobs)

            # Wait for push processing
            for pa in process_agents:
                pa.join_pushed_jobs()

            logger.debug("--- run loop: %s seconds ---" % (timer() - start_time))
            # Check if self._running was updated after push update
            if self._running:
                # Wait
                logger.debug(' - Wait')
                time.sleep(self._poll_interval)
        self._remove()

    def stop(self):
        """Stop process agent

        :rtype: NoReturn
        """
        logger.debug('Shutdown Process Agent server')
        self._running = False
