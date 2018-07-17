# -*- coding: utf-8 -*-
#
# __init__.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import os
import copy
import uuid
from enum import Enum
from typing import List, Dict, Tuple
from dictdiffer import diff
from borgy_process_agent.event import Observable
from borgy_process_agent.job import Restart, State
from borgy_process_agent.exceptions import NotReadyError
from borgy_process_agent_api_server.models.job import Job
from borgy_process_agent_api_server.models.job_spec import JobSpec


class JobEventState(Enum):
    """Job Event State
    When PA dispatch job updates, this list describes the kind of event
    """
    # Created means that a job go from jobs in creation list to jobs created list
    CREATED = 'created'
    # Added means that a job go directly to jobs created list
    ADDED = 'added'
    # Updated means that a job in jobs created list was updated
    UPDATED = 'updated'


class ProcessAgentMode(Enum):
    """Process Agent Mode
    List of diffents modes for process agent
    """
    # Choose automatically the "good" mode
    AUTO = 'auto'
    # Borgy (default)
    BORGY = 'borgy'
    # Tasks will be launched in docker environnement
    DOCKER = 'docker'


process_agents = []


class ProcessAgentBase():
    def __init__(self, autokill: bool = True, autorerun_interrupted_jobs: bool = True, **kwargs):
        """Contrustor

        :rtype: NoReturn
        """
        self._autokill = False
        self._autorerun_interrupted_jobs = False
        self._options = kwargs
        self._observable_jobs_update = Observable()
        self._callback_jobs_provider = None
        self.reset()
        self.set_autokill(autokill)
        self.set_autorerun_interrupted_jobs(autorerun_interrupted_jobs)

    def _push_jobs(self, jobs: List[Job]):
        """Call when PUT API receives jobs

        :rtype: NoReturn
        """
        # Check for jobs update
        jobs_updated = []
        for j in jobs:
            jcopy = copy.deepcopy(j)
            if j.id in self._process_agent_jobs:
                # Check for rerun
                if j.id in self._process_agent_jobs_to_rerun:
                    nb_runs = len(self._process_agent_jobs[j.id].runs) + 1
                    # There is a new run
                    if len(j.runs) == nb_runs:
                        self._process_agent_jobs_to_rerun.remove(j.id)

                ddiff = list(diff(self._process_agent_jobs[j.id].to_dict(), j.to_dict()))
                if ddiff:
                    jobs_updated.append({
                        'job': jcopy,
                        'update': ddiff,
                        'state': JobEventState.UPDATED
                    })
            else:
                fnd = False
                if j.spec_index is not None:
                    for jc in self._process_agent_jobs_in_creation:
                        if jc.spec_index == j.spec_index:
                            jobs_updated.append({
                                'job': jcopy,
                                'update': list(diff(jc.to_dict(), j.to_dict())),
                                'state': JobEventState.CREATED
                            })
                            self._process_agent_jobs_in_creation.remove(jc)
                            fnd = True
                            break
                if not fnd:
                    jobs_updated.append({
                        'job': jcopy,
                        'update': list(diff({}, j.to_dict())),
                        'state': JobEventState.ADDED
                    })
            self._process_agent_jobs[j.id] = j

        if jobs_updated:
            self._observable_jobs_update.dispatch(pa=self, jobs=jobs_updated)

    def _insert(self):
        """Insert process agent in PA list

        :rtype: NoReturn
        """
        if self not in process_agents:
            process_agents.append(self)

    def _remove(self):
        """Remove process agent from PA list

        :rtype: NoReturn
        """
        if self in process_agents:
            process_agents.remove(self)

    def reset(self):
        """Reset Process Agent.

        :rtype: NoReturn
        """
        self._process_agent_jobs = {}
        self._process_agent_jobs_in_creation = []
        self._process_agent_jobs_to_rerun = []
        self._shutdown = False

    def is_shutdown(self) -> bool:
        """Return if process agent is shutdown or not

        :rtype: bool
        """
        return self._shutdown

    def is_ready(self) -> bool:
        """Return if process agent is ready or not

        :rtype: bool
        """
        return not self._shutdown and self._callback_jobs_provider and callable(self._callback_jobs_provider)

    def set_callback_jobs_provider(self, callback):
        """Define the callback which returns the job to create by the process agent

        :rtype: NoReturn
        """
        self._callback_jobs_provider = callback

    def subscribe_jobs_update(self, callback):
        """Subscribe to the event when one or more jobs are updated

        :rtype: NoReturn
        """
        self._observable_jobs_update.subscribe(callback)

    def set_autokill(self, autokill: bool):
        """Enable or disable autokill

        :rtype: NoReturn
        """
        if autokill == self._autokill:
            return

        if autokill:
            self._observable_jobs_update.subscribe(self.__class__.pa_check_autokill, 'autokill')
        else:
            self._observable_jobs_update.unsubscribe(callback=self.__class__.pa_check_autokill)
        self._autokill = autokill

    def set_autorerun_interrupted_jobs(self, autorerun_interrupted_jobs: bool):
        """Enable or disable autokill

        :rtype: NoReturn
        """
        if autorerun_interrupted_jobs == self._autorerun_interrupted_jobs:
            return

        if autorerun_interrupted_jobs:
            self._observable_jobs_update.subscribe(self.__class__.pa_autorerun_interrupted_jobs, 'autokill')
        else:
            self._observable_jobs_update.unsubscribe(callback=self.__class__.pa_autorerun_interrupted_jobs)
        self._autorerun_interrupted_jobs = autorerun_interrupted_jobs

    def kill_job(self, job_id: str) -> Tuple[Job, bool]:
        """Kill a job

        :rtype: Tuple[Job, bool]
        """
        raise NotImplementedError

    def rerun_job(self, job_id: str) -> Tuple[Job, bool]:
        """Rerun a job

        :rtype: Tuple[Job, bool]
        """
        if job_id in self._process_agent_jobs:
            is_updated = False
            if (job_id not in self._process_agent_jobs_to_rerun
               and self._process_agent_jobs[job_id].state in [State.FAILED.value, State.CANCELLED.value,
                                                              State.INTERRUPTED.value]):
                self._process_agent_jobs_to_rerun.append(job_id)
                is_updated = True
            return (copy.deepcopy(self._process_agent_jobs[job_id]), is_updated)
        return (None, False)

    def clear_jobs_in_creation(self):
        """Clear all jobs in creation by the process agent

        :rtype: NoReturn
        """
        self._process_agent_jobs_in_creation = []

    def get_jobs(self) -> Dict[str, Job]:
        """Get all jobs created by the process agent

        :rtype: Dict[str, Job]
        """
        return copy.deepcopy(self._process_agent_jobs)

    def get_job_by_id(self, job_id: str) -> Job:
        """Get a job by his id

        :rtype: Job
        """
        if job_id in self._process_agent_jobs:
            return copy.deepcopy(self._process_agent_jobs[job_id])
        return None

    def get_jobs_by_state(self, state: str) -> List[Job]:
        """Get all jobs in state

        :rtype: List[Job]
        """
        jobs = []
        for (_, j) in self._process_agent_jobs.items():
            if j.state == state:
                jobs.append(j)
        return copy.deepcopy(jobs)

    def get_jobs_by_name(self, name: str) -> List[Job]:
        """Get jobs by name

        :rtype: List[Job]
        """
        jobs = []
        for (_, j) in self._process_agent_jobs.items():
            if j.name == name:
                jobs.append(j)
        return copy.deepcopy(jobs)

    def get_jobs_to_rerun(self) -> List[str]:
        """Get all jobs to rerun by the process agent and waiting for a return of the governor

        :rtype: List[str]
        """
        return copy.deepcopy(self._process_agent_jobs_to_rerun)

    def get_jobs_in_creation(self) -> List[JobSpec]:
        """Get all jobs in creation by the process agent and waiting for a return of the governor

        :rtype: List[JobSpec]
        """
        return copy.deepcopy(self._process_agent_jobs_in_creation)

    def get_job_to_create(self) -> List[JobSpec]:
        """Return the list of jobs to create. Returns job in creation if the list is not empty.

        :rtype: List[JobSpec]
        """
        if self._shutdown:
            return None

        if not self.is_ready():
            raise NotReadyError("Process agent is not ready yet!")

        if not self._process_agent_jobs_in_creation:
            jobs = self._callback_jobs_provider(self)
            if jobs is None:
                self._shutdown = True
                # Dispatch an empty event to eventually call autokill
                self._observable_jobs_update.dispatch(pa=self, jobs=[])
                return None
            if not isinstance(jobs, list) and not isinstance(jobs, dict):
                raise TypeError("List or dict expected from jobs_provider")
            if isinstance(jobs, list) and not all(isinstance(j, dict) for j in jobs):
                raise TypeError("Dict expected in list elements from jobs_provider")
            elif isinstance(jobs, dict):
                jobs = [jobs]
            self._process_agent_jobs_in_creation = [self.get_default_job(j) for j in jobs]
            # Set job specIndex
            base_spec_index = len(self._process_agent_jobs)
            for i, job in enumerate(self._process_agent_jobs_in_creation):
                self._process_agent_jobs_in_creation[i].spec_index = base_spec_index + i

        return self.get_jobs_in_creation()

    def start(self):
        """Start process agent

        :rtype: NoReturn
        """
        raise NotImplementedError

    def stop(self):
        """Stop process agent

        :rtype: NoReturn
        """
        raise NotImplementedError

    def get_info(self):
        """Get information about the process agent

        :rtype: dict
        """
        return {
            'id': '00000000-0000-0000-0000-000000000000',
            'createdBy': 'MyUser',
        }

    def get_default_job(self, job=None) -> JobSpec:
        """Get default parameters for a job

        :rtype: JobSpec
        """
        info = self.get_info()
        result = {
            'command': [],
            'createdBy': info['createdBy'],
            'environmentVars': [],
            'image': "images.borgy.elementai.lan/borsh:latest",
            'interactive': False,
            'labels': [],
            'maxRunTimeSecs': 0,
            'name': info['id'] + "-" + str(uuid.uuid4()),
            'options': {},
            'preemptable': True,
            'reqCores': 1,
            'reqGpus': 0,
            'reqRamGbytes': 1,
            'restart': Restart.NO.value,
            'stdin': False,
            'volumes': [],
            'workdir': ""
        }
        if job and isinstance(job, dict):
            result.update(job)

        if result['restart'] == Restart.ON_INTERRUPTION.value:
            raise ValueError('Process agent job can\'t have automatic restart. Use autorerun_interrupted_jobs parameter or handle rerun on job udpate by yourself.')  # noqa: E501

        return JobSpec.from_dict(result)

    @staticmethod
    def pa_check_autokill(event):
        """Check if we have to kill the server application

        :rtype: NoReturn
        """
        if event.pa.is_shutdown():
            jobs = event.pa.get_jobs()
            jobs_running = dict(filter(lambda j: j[1].state in [
                State.QUEUING.value,
                State.QUEUED.value,
                State.RUNNING.value
            ], jobs.items()))
            if not jobs_running and not event.pa.get_jobs_to_rerun():
                event.pa.stop()

    @staticmethod
    def pa_autorerun_interrupted_jobs(event):
        """Rerun automatically all INTERRUPTED jobs

        :rtype: NoReturn
        """
        for j in event.jobs:
            if j['job'].state == State.INTERRUPTED.value:
                event.pa.rerun_job(j['job'].id)


class ProcessAgent(ProcessAgentBase):
    """Process Agent Generic
    """
    def __new__(cls, mode=ProcessAgentMode.AUTO, **kwargs):
        if mode == ProcessAgentMode.AUTO:
            mode = ProcessAgentMode.DOCKER
            if 'BORGY_JOB_ID' in os.environ and 'BORGY_USER' in os.environ:
                mode = ProcessAgentMode.BORGY
        pa_module = __import__(__name__ + '.modes.' + mode.value, fromlist=['ProcessAgent'])

        return pa_module.ProcessAgent(**kwargs)
