import copy
import math
import time
import uuid
import logging
from timeit import default_timer as timer
from typing import List

import docker
import borgy_process_agent_api_client
from borgy_process_agent.enums import State, Restart
from borgy_process_agent.utils import (get_now, cpu_str_to_ncpu, get_now_isoformat,
                                       memory_str_to_nbytes)
from borgy_process_agent_api_server.models import Job, JobRuns, JobsOps, JobSpec

logger = logging.getLogger(__name__)


def parse_iso_datetime(val):
    return val


class DockerGovernor:

    def __init__(self, agent_host='http://localhost', agent_port=8666, poll_interval=2):
        self._running = False
        self._agent_port = agent_port
        self._agent_host = agent_host
        self._agent_url = f'{self._agent_host}:{self._agent_port}'
        self._agent_jobs_url = f'{self._agent_url}/v1/jobs'
        self._governor_jobs = {}
        self._docker = docker.from_env()
        self._poll_interval = poll_interval
        self._options = {}

        config = borgy_process_agent_api_client.Configuration()
        config.host = self._agent_url
        api_client = borgy_process_agent_api_client.ApiClient(config)
        self._jobs_api = borgy_process_agent_api_client.JobsApi(api_client)
        self._health_api = borgy_process_agent_api_client.HealthApi(api_client)

    def _get_new_jobs(self) -> JobsOps:
        if not self._running:
            return
        logger.info('Requesting new jobs from borgy_process_agent.')
        res, code, headers = self._jobs_api.v1_jobs_get_with_http_info()
        return res

    def _send_job_updates(self, jobs):
        if not self._running:
            return
        logger.info('Sending job updates to agent.')
        logger.debug('Sending update to agent: %s jobs', [j for j in jobs])
        # We need complexencoder here to support bytes objects which
        res = self._jobs_api.v1_jobs_put(jobs)
        return res

    def _wait_till_ready(self):
        attempts = 20
        ready = False

        while not ready and attempts and self._running:
            try:
                res = self._health_api.v1_health_get()
                if res.is_ready:
                    ready = True
                    logger.info('PA is ready!')
                else:
                    if not attempts:
                        raise TimeoutError
                    time.sleep(0.1)
            except TimeoutError:
                raise
            except Exception:
                time.sleep(0.1)
            finally:
                logger.info('Governor waiting for PA to start.')
                attempts -= 1

    def start(self):
        self._running = True
        logger.info('Starting governor loop')
        self._wait_till_ready()

        try:
            while self._running:
                start_time = timer()
                # Get job from PA
                logger.debug('Get job from PA')
                jobs: JobsOps = self._get_new_jobs()

                for j in jobs.submit:
                    self._create_job(j)
                for j in jobs.rerun:
                    self._rerun_job(j)
                for j in jobs.kill:
                    self._kill_job(j)

                # Start queuing jobs
                logger.info('Start queuing jobs')
                self._start_jobs()

                # Check running container with max run time
                logger.info('Check running container with max run time')
                self._check_max_run_time()

                # Check update from container
                logger.info('Check update from container')
                updated_jobs = self._check_jobs_update()

                # Push update to PA
                self._send_job_updates(updated_jobs)

                logger.info("--- run loop: %s seconds ---" % (timer() - start_time))

                # Check if self._running was updated after push update
                if self._running:
                    logger.info('Loop waiting')
                    time.sleep(self._poll_interval)

        except Exception as ex:
            logger.exception(ex)
            self._running = False
            raise

        logger.info('Gov finished running.')

    def stop(self):
        logger.info('Stopping governor')
        self._running = False

    def _kill_job(self, job_id: str) -> Job:
        job = self._update_job_state(job_id, State.CANCELLING)
        logger.info('\t\tReruning job %s (name: %s)', job_id, job['job'].name)
        return job

    def _run_job(self, job: Job):
        cpu_count = math.ceil(cpu_str_to_ncpu(job.req_cores))
        mem = memory_str_to_nbytes(str(job.req_ram_gbytes) + 'Gi')
        gpus_list = ','.join([str(i) for i in range(job.req_gpus)])
        envs_injected_before = {
            'NVIDIA_VISIBLE_DEVICES': gpus_list,
        }
        envs_injected_after = {
            'EAI_CPU_LIMIT': cpu_count,
            'EAI_JOB_ID': job.id,
            'EAI_MEMORY_LIMIT': mem,
            'EAI_RUN_INDEX': (len(job.runs) - 1),
            'EAI_TARGET_NODE': 'docker',
            'EAI_USER': job.created_by,
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

        logger.info('\t\tStart container for job %s (name: %s)', job.id, job.name)
        run_kwargs = self._options.get('docker_run_options', {})
        if not isinstance(run_kwargs, dict):
            raise TypeError('docker_run_options must be a dict')

        container = self._docker.containers.run(name=job.id,
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
                                                **run_kwargs)

        return container

    def _create_job(self, spec: JobSpec) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(**spec.to_dict())
        logger.info('\t\tCreate new job %s (name: %s)', job_id, job.name)
        job.id = job_id
        job.runs = []
        self._governor_jobs[job_id] = {'job': job, 'container': None, 'status': ''}
        self._update_job_state(job_id, State.QUEUING)
        return job

    def _update_job_state(self, job_id, state: State) -> Job:
        if job_id not in self._governor_jobs:
            raise ValueError('job not found: {}'.format(job_id))

        job = self._governor_jobs[job_id]
        if job['job'].state != state.value:
            logger.info('\t\tUpdate job %s: %s -> %s', job_id, job['job'].state, state.value)
            job['job'].state = state.value
            if state == State.QUEUING:
                run = {
                    'createdOn': get_now_isoformat(),
                    'jobId': job_id,
                    'id': str(uuid.uuid4()),
                    'ip': '127.0.0.1',
                    'nodeName': 'docker',
                    'state': State.QUEUING.value,
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
                    job['job'].runs[-1].result = job['container'].logs(
                        stdout=True, stderr=True).decode('utf8', errors='replace')
                    if self._options.get('docker_remove', True):
                        job['container'].remove()
            elif state == State.SUCCEEDED:
                ended_on = get_now_isoformat()
                if job['container']:
                    ended_on = job['container'].attrs['State']['FinishedAt']
                job['job'].runs[-1].ended_on = ended_on
                job['job'].runs[-1].exit_code = 0
                if job['container']:
                    job['job'].runs[-1].result = job['container'].logs(
                        stdout=True, stderr=True).decode('utf8', errors='replace')
                    if self._options.get('docker_remove', True):
                        job['container'].remove()
            elif state == State.INTERRUPTED:
                if job['job'].restart == Restart.ON_INTERRUPTION.value:
                    job['job'].runs[-1].state = State.INTERRUPTED.value
                    job['job'].runs[-1].ended_on = get_now_isoformat()
                    if job['container']:
                        job['job'].runs[-1].result = job['container'].logs(stdout=True,
                                                                           stderr=True).decode(
                                                                               'utf8',
                                                                               errors='replace')
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
                started_on = parse_iso_datetime(run.started_on)
                if (get_now() - started_on).total_seconds() > job['job'].max_run_time_secs:
                    logger.info('\t\tStop job %s: max run time exceed (%s seconds)', job_id,
                                job['job'].max_run_time_secs)
                    if job['container']:
                        job['container'].stop(timeout=self._options.get('docker_stop_timeout', 10))

    def _check_jobs_update(self) -> List[Job]:
        containers = self._docker.containers.list(all=True, ignore_removed=True)
        job_ids_succedded = [
            c.name for c in containers if c.attrs['State']['ExitCode'] == 0
            and not c.attrs['State']['Running'] and not c.attrs['State']['Dead']
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
