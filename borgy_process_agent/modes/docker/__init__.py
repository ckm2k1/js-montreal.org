# -*- coding: utf-8 -*-
#
# __init__.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import time
import uuid
import docker
from typing import Tuple, NoReturn, List
from borgy_process_agent import controllers, ProcessAgentBase, process_agents
from borgy_process_agent.controllers import jobs_controller
from borgy_process_agent.job import State, Restart
from borgy_process_agent.utils import get_now_isoformat
from borgy_process_agent_api_server.models.job import Job, JobRuns


class ProcessAgent(ProcessAgentBase):
    """Process Agent for Docker
    """
    def __init__(self, **kwargs) -> NoReturn:
        """Contrustor

        :rtype: NoReturn
        """
        super().__init__(**kwargs)
        self._docker = docker.from_env()
        self._running = False
        self._options = kwargs
        self._job_id = kwargs.get('job_id', uuid.uuid4())
        self._poll_interval = kwargs.get('poll_interval', 10)
        self._governor_jobs = {}

    def kill_job(self, job_id: str) -> Tuple[Job, bool]:
        """Kill a job

        :rtype: Tuple[Job, bool]
        """
        result = super().kill_job(job_id)
        if result[1]:
            self._update_job_state(job_id, State.CANCELLING)
        return result

    def rerun_job(self, job_id: str) -> Tuple[Job, bool]:
        """Rerun a job

        :rtype: Tuple[Job, bool]
        """
        result = super().rerun_job(job_id)
        if result[1]:
            self._update_job_state(job_id, State.QUEUING)
        return result

    def _run_job(self, job: Job) -> NoReturn:
        """Run a job in docker

        :rtype: NoReturn
        """
        container = self._docker.containers.run(
            name=job.id,
            image=job.image,
            command=job.command,
            environment=job.environment_vars,
            labels=job.labels,
            cpu_count=job.req_cores,
            mem_limit=job.req_ram_gbytes,
            volumes=job.volumes,
            working_dir=job.workdir,
            detach=self._options.get('docker_detach', True),
            auto_remove=False
        )

        return container

    def _create_job(self, job: Job) -> NoReturn:
        job_id = str(uuid.uuid4())
        job.id = job_id
        job.state = ''
        self._governor_jobs[job_id] = {
            'job_id': job_id,
            'job': job,
            'container': None,
            'status': ''
        }
        self._update_job_state(job_id, State.QUEUING)

    def _update_job_state(self, job_id, state: State) -> Job:
        if job_id not in self._governor_jobs:
            raise ValueError('job not found: {}'.format(job_id))

        job = self._governor_jobs[job_id]
        if job['job'].state != state.value:
            job['job'].state = state.value
            if job.runs:
                job['job'].runs[-1].state = state.value

            if state == State.QUEUING:
                run = {
                    'created_on': get_now_isoformat(),
                    'id': uuid.uuid4(),
                    'job_id': job_id,
                    'state': State.QUEUING.value
                }
                job.runs.append(JobRuns.from_dict(run))
            elif state == State.QUEUED:
                job['job'].runs[-1].queued_on = get_now_isoformat()
                job['container'] = self._run_job(job['job'])
            elif state == State.RUNNING:
                job['job'].runs[-1].started_on = get_now_isoformat()
            elif state == State.CANCELLING:
                job['job'].runs[-1].cancel_requested_on = get_now_isoformat()
                job['container'].stop(timeout=self._options.get('docker_stop_timeout', 10))
            elif state == State.CANCELLED:
                cancelled_on = get_now_isoformat()
                job['job'].runs[-1].cancelled_on = cancelled_on
                job['job'].runs[-1].ended_on = cancelled_on
            elif state == State.FAILED:
                job['job'].runs[-1].ended_on = get_now_isoformat()
                job['job'].runs[-1].exit_code = 255
                job['job'].runs[-1].result = job['container'].logs(stdout=True, stderr=True)
                job['container'].remove()
            elif state == State.SUCCEEDED:
                job['job'].runs[-1].ended_on = get_now_isoformat()
                job['job'].runs[-1].exit_code = 0
                job['job'].runs[-1].result = job['container'].logs(stdout=True, stderr=True)
                job['container'].remove()
            elif state == State.INTERRUPTED:
                if job.restart == Restart.ON_INTERRUPTION.value:
                    job['job'].runs[-1].ended_on = get_now_isoformat()
                    job['job'].runs[-1].result = job['container'].logs(stdout=True, stderr=True)
                    new_run = {
                        'created_on': get_now_isoformat(),
                        'id': uuid.uuid4(),
                        'job_id': job_id,
                        'state': State.QUEUING.value
                    }
                    job.runs.append(JobRuns.from_dict(new_run))
                    state.value = State.QUEUING.value
        return job

    def _start_jobs(self) -> NoReturn:
        for j in self._governor_jobs:
            if j['job'].state == State.QUEUING.value:
                self._update_job_state(j['job_id'], State.QUEUED)

    def _check_jobs_update(self) -> List[Job]:
        containers = self._docker.containers.list(all=True)
        containers_succedded = self._docker.containers.list(all=True, filters={'exited': 0, 'status': 'exited'})
        job_ids_succedded = []
        for c in containers_succedded:
            job_ids_succedded.append(c.name)

        updates = {}
        for c in containers:
            job_id = c.name
            if job_id in self._governor_jobs:
                job = self._governor_jobs[job_id]
                current_state = job['job'].state

                if job['status'] != c.status:
                    if c.status == 'running':
                        self._update_job_state(job_id, State.RUNNING)
                    elif c.status == 'exited':
                        if job['job'].state == State.CANCELLING:
                            self._update_job_state(job_id, State.CANCELLED)
                        elif job_id in containers_succedded:
                            self._update_job_state(job_id, State.SUCCEEDED)
                        elif job_id in containers_succedded:
                            self._update_job_state(job_id, State.FAILED)
                job['status'] = c.status

                if job['job'].state != current_state:
                    updates[job_id] = job

        return list(updates.values())

    def start(self) -> NoReturn:
        """Start process agent

        :rtype: NoReturn
        """
        self._running = True
        while self._running:
            # Get job from PA
            jobs = jobs_controller.v1_jobs_get()
            if isinstance(jobs, set):
                jobs, _ = jobs

            if isinstance(jobs, list):
                for j in jobs:
                    self._create_job(j)

            # Start queing jobs
            self._start_jobs()

            # Check update from container
            update_jobs = self._check_jobs_update()

            # Push update to PA
            for pa in process_agents:
                pa._push_jobs([Job.from_dict(j) for j in update_jobs])

            # Wait
            time.sleep(self._poll_interval)

    def stop(self) -> NoReturn:
        """Stop process agent

        :rtype: NoReturn
        """
        self._running = False

    def get_info(self):
        """Get information about the process agent

        :rtype: dict
        """
        return {
            'id': self._job_id,
            'createdBy': 'MyUser',
        }
