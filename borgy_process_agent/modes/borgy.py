# -*- coding: utf-8 -*-
#
# borgy.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import os
import connexion
import logging
import threading
import pkg_resources
from werkzeug.serving import make_server
from borgy_process_agent import controllers, ProcessAgentBase
import borgy_process_agent_api_server
from borgy_process_agent_api_server import encoder
from borgy_process_agent.exceptions import EnvironmentVarError

logger = logging.getLogger(__name__)

borgy_process_agent_version = pkg_resources.get_distribution('borgy_process_agent').version


class ProcessAgent(ProcessAgentBase):
    """Process Agent for Borgy
    """
    def __init__(self, **kwargs):
        """Constructor

        :rtype: NoReturn
        """
        missing_env = []

        def check_env_var(name):
            nonlocal missing_env
            value = os.getenv(name, None)
            if not value:
                missing_env.append(name)
            return value

        pa_job_id = check_env_var('BORGY_JOB_ID')
        pa_user = check_env_var('BORGY_USER')

        if missing_env:
            raise EnvironmentVarError('Env var(s) {} not defined or empty. Are you running in borgy ?'.
                                      format(missing_env))

        super().__init__(pa_job_id=pa_job_id, pa_user=pa_user, **kwargs)

        self._server_app = None
        self._server_srv = None
        self._stop_error = None

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
        self._server_app = ProcessAgent.get_server_app()
        self._server_srv = make_server('0.0.0.0', self._options.get('port', 8666), self._server_app)
        logger.info('Start Process Agent server')
        self._server_srv.serve_forever()
        self._remove()
        if self._stop_error:
            raise self._stop_error

    def stop(self, **kwargs):
        """Stop process agent - stop server application

        :rtype: NoReturn
        """
        if self._server_srv:
            logger.info('Shutdown Process Agent server')
            error = kwargs.get('error')
            if error:
                self._stop_error = error
            logger.info('Go kill it')

            def call_shutdown():
                self._server_srv.shutdown()
                logger.info('Killed !')
            app = threading.Thread(name='Shutdown', target=call_shutdown)
            app.setDaemon(True)
            app.start()
        else:
            logger.warn('Process Agent server is not running')

    @staticmethod
    def get_server_app():
        """Get server application

        :rtype: FlaskApp
        """
        controllers.overwrite_api_controllers()
        app = connexion.App(__name__, specification_dir=borgy_process_agent_api_server.__path__[0]+'/openapi/')
        app.app.json_encoder = encoder.JSONEncoder
        app.add_api('openapi.yaml', arguments={'title': 'Borgy Process Agent'})
        return app
