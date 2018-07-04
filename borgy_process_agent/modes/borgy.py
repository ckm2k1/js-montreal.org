# -*- coding: utf-8 -*-
#
# borgy.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import os
import copy
import connexion
import logging
from typing import Tuple
from werkzeug.serving import make_server
from borgy_process_agent import controllers, ProcessAgentBase
from borgy_process_agent.job import State
from borgy_process_agent.config import Config
import borgy_process_agent_api_server
from borgy_process_agent_api_server import encoder
from borgy_process_agent_api_server.models.job import Job
from borgy_process_agent.exceptions import EnvironmentVarError
import borgy_job_service_client

logger = logging.getLogger(__name__)


class ProcessAgent(ProcessAgentBase):
    """Process Agent for Borgy
    """
    def __init__(self, **kwargs):
        """Contrustor

        :rtype: NoReturn
        """
        super().__init__(**kwargs)
        self._job_service = self._init_job_service()
        self._server_app = None

    def _init_job_service(self):
        """Delete process agent

        :rtype: JobsApi
        """
        info = self.get_info()

        config = borgy_job_service_client.Configuration()
        config.host = Config.get('job_service_url')
        config.ssl_ca_cert = Config.get('job_service_certificate')

        api_client = borgy_job_service_client.ApiClient(config)
        api_client.set_default_header('X-User', info['createdBy'])

        # create an instance of the API class
        return borgy_job_service_client.JobsApi(api_client)

    def kill_job(self, job_id: str) -> Tuple[Job, bool]:
        """Kill a job

        :rtype: Tuple[Job, bool]
        """
        if job_id in self._process_agent_jobs:
            is_updated = False
            if self._process_agent_jobs[job_id].state in [State.QUEUING.value, State.QUEUED.value, State.RUNNING.value]:
                info = self.get_info()
                job = self._job_service.v1_jobs_job_id_delete(job_id, info['createdBy'])
                # Push job event
                self._push_jobs([job])
                is_updated = True
            return (copy.deepcopy(self._process_agent_jobs[job_id]), is_updated)
        return (None, False)

    def rerun_job(self, job_id: str) -> Tuple[Job, bool]:
        """Rerun a job

        :rtype: Tuple[Job, bool]
        """
        if job_id in self._process_agent_jobs:
            is_updated = False
            if self._process_agent_jobs[job_id].state in [State.FAILED.value, State.CANCELLED.value, State.INTERRUPTED.value]:
                job = self._job_service.v1_jobs_job_id_rerun_put(job_id)
                # Push job event
                self._push_jobs([job])
                is_updated = True
            return (copy.deepcopy(self._process_agent_jobs[job_id]), is_updated)
        return (None, False)

    def get_app(self):
        """Return current server application

        :rtype: FlaskApp
        """
        return self._server_app

    def start(self):
        """Start process agent - start server application

        :rtype: NoReturn
        """
        self._insert()
        self._server_app = self.__class__.get_server_app()
        self._server_srv = make_server('0.0.0.0', self._options.get('port', 8080), self._server_app)
        logger.info('Start Process Agent server')
        self._server_srv.serve_forever()
        self._remove()

    def stop(self):
        """Stop process agent - stop server application

        :rtype: NoReturn
        """
        logger.info('Shutdown Process Agent server')
        self._server_srv.shutdown()

    @staticmethod
    def get_server_app():
        """Get server application

        :rtype: FlaskApp
        """
        controllers.overwrite_api_controllers()
        app = connexion.App(__name__, specification_dir=borgy_process_agent_api_server.__path__[0]+'/swagger/')
        app.app.json_encoder = encoder.JSONEncoder
        app.add_api('swagger.yaml', arguments={'title': 'Borgy Process Agent'})
        return app

    def get_info(self):
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
