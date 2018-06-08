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
from borgy_process_agent import ProcessAgent


class BaseTestCase(TestCase):
    def create_app(self):
        self._base_dir = os.path.dirname(os.path.realpath(__file__))
        self._pa = None
        logging.getLogger('connexion.operation').setLevel('ERROR')
        app = ProcessAgent.get_server_app()
        return app.app

    def setUp(self):
        os.environ['BORGY_JOB_ID'] = str(uuid.uuid4())
        os.environ['BORGY_USER'] = 'guillaume_smaha'
        if not self._pa:
            self._pa = ProcessAgent()
            self._pa.set_autokill(False)

    def tearDown(self):
        if self._pa:
            self._pa.delete()
        self._pa = None
