# -*- coding: utf-8 -*-
#
# __init__.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import os
import six
import copy
import uuid
import click
import connexion
import logging
from enum import Enum
from typing import List, Dict
from dictdiffer import diff
from borgy_process_agent import controllers
from borgy_process_agent.event import Observable
from borgy_process_agent.job import Restart, State
from borgy_process_agent.exceptions import NotReadyError, EnvironmentVarError
from borgy_process_agent.config import Config
import borgy_process_agent_api_server
from borgy_process_agent_api_server import encoder
from borgy_process_agent_api_server.models.job import Job
import borgy_job_service_client


process_agents = []


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


class ProcessAgent():
    """Process Agent
    """
    def __init__(self):
        """Contrustor

        :rtype: void
        """
        self._process_agent_jobs = {}
        self._process_agent_jobs_in_creation = []
        self._observable_jobs_update = Observable()
        self._callback_jobs_provider = None
        self._shutdown = False
        process_agents.append(self)
        self._job_service = self._init_job_service()

    def _init_job_service(self):
        """Delete process agent

        :rtype: JobsApi
        """
        config = borgy_job_service_client.Configuration()
        config.host = Config.get('job_service_url')
        config.ssl_ca_cert = Config.get('job_service_certificate')

        api_client = borgy_job_service_client.ApiClient(config)

        # create an instance of the API class
        return borgy_job_service_client.JobsApi(api_client)

    def delete(self):
        """Delete process agent

        :rtype: void
        """
        process_agents.remove(self)

    def _push_jobs(self, jobs: List[Job]):
        """Call when PUT API receives jobs

        :rtype: void
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

        :rtype: void
        """
        self._callback_jobs_provider = callback

    def get_jobs(self) -> Dict[str, Job]:
        """Get all jobs created by the process agent

        :rtype: Dict[id => Job]
        """
        return copy.deepcopy(self._process_agent_jobs)

    def get_job_by_id(self, job_id: str) -> Job:
        """Get a job by his id

        :rtype: Job
        """
        if job_id in self._process_agent_jobs:
            return copy.deepcopy(self._process_agent_jobs[job_id])
        return None

    def get_job_by_state(self, state: str) -> List[Job]:
        """Get all jobs in state

        :rtype: List[Job]
        """
        jobs = []
        for (job_id, j) in six.iteritems(self._process_agent_jobs):
            if j.state == state:
                jobs.append(j)
        return copy.deepcopy(jobs)

    def kill_job(self, job_id: str) -> Job:
        """Kill a job

        :rtype: Job
        """
        if job_id in self._process_agent_jobs:
            if self._process_agent_jobs[job_id].state in [State.QUEUING.value, State.QUEUED.value, State.RUNNING.value]:
                info = ProcessAgent.get_info()
                self._job_service.v1_jobs_job_id_delete(job_id, info['createdBy'])
                self._process_agent_jobs[job_id].state  = State.CANCELLING.value
            return copy.deepcopy(self._process_agent_jobs[job_id])
        return None

    def get_jobs_in_creation(self) -> List[Job]:
        """Get all jobs in creation by the process agent and waiting for a return of the governor

        :rtype: List[Job]
        """
        return copy.deepcopy(self._process_agent_jobs_in_creation)

    def get_job_to_create(self) -> List[Job]:
        """Return the list of jobs to create. Returns job in creation if the list is not empty.

        :rtype: List[Job]
        """
        if self._shutdown:
            return None

        if not self.is_ready():
            raise NotReadyError("Process agent is not ready yet!")

        if not self._process_agent_jobs_in_creation:
            jobs = self._callback_jobs_provider(self)
            if jobs is None:
                self._shutdown = True
                return None
            if not isinstance(jobs, list) and not isinstance(jobs, dict):
                raise TypeError("List or dict expected from jobs_provider")
            if isinstance(jobs, list) and not all(isinstance(j, dict) for j in jobs):
                raise TypeError("Dict expected in list elements from jobs_provider")
            elif isinstance(jobs, dict):
                jobs = [jobs]
            self._process_agent_jobs_in_creation = [ProcessAgent.get_default_job(j) for j in jobs]

        return self.get_jobs_in_creation()

    def clear_jobs_in_creation(self):
        """Clear all jobs in creation by the process agent

        :rtype: void
        """
        self._process_agent_jobs_in_creation = []

    def subscribe_jobs_update(self, callback):
        """Subscribe to the event when one or more jobs are updated

        :rtype: void
        """
        self._observable_jobs_update.subscribe(callback)

    def start(self):
        """Start server application

        :rtype: void
        """
        app = ProcessAgent.get_server_app()
        click.secho('   Warning vidange: Ignore following warning.', fg='red')
        app.app.run(port=Config.get('port'))

    @staticmethod
    def get_server_app():
        """Get server application

        :rtype: FlaskApp
        """
        logging.basicConfig(format=Config.get('logging_format'), level=Config.get('logging_level'))
        controllers.overwrite_api_controllers()
        app = connexion.App(__name__, specification_dir=borgy_process_agent_api_server.__path__[0]+'/swagger/')
        app.app.json_encoder = encoder.JSONEncoder
        app.add_api('swagger.yaml', arguments={'title': 'Borgy Process Agent'})
        return app

    @staticmethod
    def get_info():
        """Get information about the process agent

        :rtype: dict
        """
        if 'BORGY_JOB_ID' not in os.environ or not os.environ['BORGY_JOB_ID']:
            raise EnvironmentVarError('Env var BORGY_JOB_ID is not defined. Are you running in borgy ?')
        elif 'BORGY_USER' not in os.environ or not os.environ['BORGY_USER']:
            raise EnvironmentVarError('Env var BORGY_USER is not defined. Are you running in borgy ?')

        return {
            'id': os.environ['BORGY_JOB_ID'],
            'createdBy': os.environ['BORGY_USER'],
        }

    @staticmethod
    def get_default_job(job=None) -> Job:
        """Get default parameters for a  job

        :rtype: Job
        """
        info = ProcessAgent.get_info()
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
            'reqRamGbytes': 1,
            'restart': Restart.NO.value,
            'stdin': False,
            'volumes': [],
            'workdir': ""
        }
        if job and isinstance(job, dict):
            result.update(job)
        return Job.from_dict(result)
