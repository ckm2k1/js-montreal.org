# -*- coding: utf-8 -*-
#
# __init__.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import copy
import connexion
import logging
from werkzeug.serving import make_server
from borgy_process_agent import controllers
from borgy_process_agent.job import State
from borgy_process_agent.config import Config
import borgy_process_agent_api_server
from borgy_process_agent_api_server import encoder
from borgy_process_agent_api_server.models.job import Job
import borgy_job_service_client


class ProcessAgent():
    """Process Agent for Borgy
    """
    def __init__(self, **kwargs):
        """Contrustor

        :rtype: void
        """
        super().__init__(**kwargs)
        self._job_service = self._init_job_service()
        self._server_app = None

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

    def kill_job(self, job_id: str) -> Job:
        """Kill a job

        :rtype: Job
        """
        if job_id in self._process_agent_jobs:
            if self._process_agent_jobs[job_id].state in [State.QUEUING.value, State.QUEUED.value, State.RUNNING.value]:
                info = self.__class__.get_info()
                self._job_service.v1_jobs_job_id_delete(job_id, info['createdBy'])
                self._process_agent_jobs[job_id].state = State.CANCELLING.value
            return copy.deepcopy(self._process_agent_jobs[job_id])
        return None

    def rerun_job(self, job_id: str) -> Job:
        """Rerun a job

        :rtype: Job
        """
        if job_id in self._process_agent_jobs:
            if self._process_agent_jobs[job_id].state in [State.FAILED.value, State.CANCELLED.value]:
                self._job_service.v1_jobs_job_id_rerun_put(job_id)
                self._process_agent_jobs[job_id].state = State.QUEUING.value
            return copy.deepcopy(self._process_agent_jobs[job_id])
        return None

    def get_app(self):
        """Return current server application

        :rtype: FlaskApp
        """
        return self._server_app

    def start(self):
        """Start process agent - start server application

        :rtype: void
        """
        self._server_app = self.__class__.get_server_app()
        self._server_srv = make_server('0.0.0.0', Config.get('port'), self._server_app)
        self._server_srv.serve_forever()

    def stop(self):
        """Stop process agent - stop server application

        :rtype: void
        """
        self._server_srv.shutdown()

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