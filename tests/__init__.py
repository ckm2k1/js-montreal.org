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
from borgy_process_agent.modes import borgy


class BaseTestCase(TestCase):
    def create_app(self):
        self._base_dir = os.path.dirname(os.path.realpath(__file__))
        self._pa = None
        logging.getLogger('connexion.operation').setLevel('ERROR')
        self._app = borgy.ProcessAgent.get_server_app()
        return self._app.app

    def setUp(self):
        os.environ['BORGY_JOB_ID'] = str(uuid.uuid4())
        os.environ['BORGY_USER'] = 'guillaume_smaha'
        if not self._pa:
            self._pa = ProcessAgent()
            self._pa.set_autokill(False)
            self._pa._insert()

    def tearDown(self):
        if self._pa:
            self._pa._remove()
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
        self._pa = None
