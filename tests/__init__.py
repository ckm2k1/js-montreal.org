# -*- coding: utf-8 -*-
#
# __init__.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import os
import uuid
import logging

from flask_testing import TestCase
from borgy_process_agent import ProcessAgent, ProcessAgentMode
from borgy_process_agent.modes import eai


class BaseTestCase(TestCase):
    def create_app(self):
        self._base_dir = os.path.dirname(os.path.realpath(__file__))
        self._pa = None
        logging.getLogger('connexion.operation').setLevel('ERROR')
        self._app = eai.ProcessAgent.get_server_app()
        return self._app.app

    def setUp(self):
        os.environ['EAI_JOB_ID'] = str(uuid.uuid4())
        os.environ['EAI_USER'] = 'guillaume_smaha'
        if not self._pa:
            self._pa = ProcessAgent(mode=ProcessAgentMode.EAI, port=1234, app=self._app)
            self._pa.set_autokill(False)
            self._pa._insert()

    def tearDown(self):
        if self._pa:
            self._pa._remove()
            # Stop thread
            self._pa._push_job_thread_running = False
            self._pa._push_job_queue.put([])
            if self._pa._push_job_thread:
                self._pa._push_job_thread.join()
        self._pa = None


class BaseTestCaseDocker(BaseTestCase):

    def setUp(self):
        if not self._pa:
            self._pa = ProcessAgent(mode=ProcessAgentMode.DOCKER, poll_interval=1)
            self._pa.set_autokill(False)
            self._pa._insert()

            # Mock
            def mock_run(j):
                return None
            self._run_job_fct = self._pa._run_job
            self._pa._run_job = mock_run

    def tearDown(self):
        if self._pa:
            self._pa._run_job = self._run_job_fct
            self._pa._remove()
            # Stop thread
            self._pa._push_job_thread_running = False
            self._pa._push_job_queue.put([])
            if self._pa._push_job_thread:
                self._pa._push_job_thread.join()
        self._pa = None
