# -*- coding: utf-8 -*-
#
# __init__.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import copy
import uuid
from enum import Enum
from typing import List, Dict, Tuple
from dictdiffer import diff
from borgy_process_agent.event import Observable
from borgy_process_agent.job import Restart, State
from borgy_process_agent.exceptions import NotReadyError
from borgy_process_agent.utils import memory_str_to_nbytes
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
    # Borgy (default)
    BORGY = 'borgy'
    # Tasks will be launched in docker environnement
    DOCKER = 'docker'
    # Tasks will run one by one in the same thread
    LOCAL = 'local'


process_agents = []


class ProcessAgentBase():
    def __init__(self, autokill: bool = True, **kwargs):
        """Contrustor

        :rtype: NoReturn
        """
        process_agents.append(self)
        self._options = kwargs
        self._process_agent_jobs = {}
        self._process_agent_jobs_in_creation = []
        self._observable_jobs_update = Observable()
        self._callback_jobs_provider = None
        self._shutdown = False
        self._autokill = False
        self.set_autokill(autokill)

    def _push_jobs(self, jobs: List[Job]):
        """Call when PUT API receives jobs

        :rtype: NoReturn
        """
        jobs_updated = []
        for j in jobs:
            jcopy = copy.deepcopy(j)
            if j.id in self._process_agent_jobs:
                ddiff = list(diff(self._process_agent_jobs[j.id].to_dict(), j.to_dict()))
                if ddiff:
                    jobs_updated.append({
                        'job': jcopy,
                        'update': ddiff,
                        'state': JobEventState.UPDATED
                    })
            else:
                fnd = False
                for jc in self._process_agent_jobs_in_creation:
                    if jc.name == j.name:
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

    def delete(self):
        """Delete process agent

        :rtype: NoReturn
        """
        process_agents.remove(self)

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

    def set_autokill(self, autokill):
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

    def kill_job(self, job_id: str) -> Tuple[Job, bool]:
        """Kill a job

        :rtype: Tuple[Job, bool]
        """
        if job_id in self._process_agent_jobs:
            is_updated = False
            if self._process_agent_jobs[job_id].state in [State.QUEUING.value, State.QUEUED.value, State.RUNNING.value]:
                self._process_agent_jobs[job_id].state = State.CANCELLING.value
                is_updated = True
            return (copy.deepcopy(self._process_agent_jobs[job_id]), is_updated)
        return (None, False)

    def rerun_job(self, job_id: str) -> Tuple[Job, bool]:
        """Rerun a job

        :rtype: Tuple[Job, bool]
        """
        if job_id in self._process_agent_jobs:
            is_updated = False
            if self._process_agent_jobs[job_id].state in [State.FAILED.value, State.CANCELLED.value]:
                self._process_agent_jobs[job_id].state = State.QUEUING.value
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
            'reqCores': 1,
            'reqGpus': 0,
            'reqRamGbytes': memory_str_to_nbytes('10Mi'),
            'restart': Restart.NO.value,
            'stdin': False,
            'volumes': [],
            'workdir': ""
        }
        if job and isinstance(job, dict):
            result.update(job)
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
            if not jobs_running:
                event.pa.stop()


class ProcessAgent(ProcessAgentBase):
    """Process Agent Generic
    """
    def __new__(cls, mode=ProcessAgentMode.BORGY, **kwargs):
        pa_module = __import__(__name__ + '.modes.' + mode.value, fromlist=['ProcessAgent'])

        return pa_module.ProcessAgent(**kwargs)
