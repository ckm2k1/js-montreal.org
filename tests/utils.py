# -*- coding: utf-8 -*-
#
# utils.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import uuid
from borgy_process_agent.job import Restart
from borgy_process_agent.utils import get_now_isoformat
from borgy_process_agent_api_server.models.job import Job


class MockJob(object):
    def __init__(self, **kwargs):
        job_id = str(uuid.uuid4())
        self._job = {
            'alive': False,
            'billCode': '',
            'command': [],
            'createdBy': 'guillaume.smaha@elementai.com',
            'createdOn': get_now_isoformat(),
            'environmentVars': [],
            'evictOthersIfNeeded': False,
            'image': "images.borgy.elementai.lan/borsh:latest",
            'id': job_id,
            'interactive': False,
            'isProcessAgent': False,
            'labels': [],
            'maxRunTimeSecs': 0,
            'name': job_id + "-" + str(uuid.uuid4()),
            'options': {},
            'reqCores': 1,
            'reqGpus': 0,
            'reqRamGbytes': 1,
            'restart': Restart.NO.value,
            'state': 'QUEUING',
            'stateInfo': '',
            'stdin': False,
            'volumes': [],
            'workdir': ""
        }
        if kwargs and isinstance(kwargs, dict):
            for k, v in kwargs.items():
                self._job[k] = v

    def get(self):
        return self._job

    def get_job(self):
        return Job.from_dict(self._job)

    def __contains__(self, key):
        return key in self._job

    def __getitem__(self, key):
        return self._job[key]

    def __setitem__(self, key, value):
        self._job[key] = value

    def __delitem__(self, key):
        del self._job[key]

    def __len__(self):
        return len(self._job)

    def __iter__(self):
        return iter(self._job)

    def __reversed__(self):
        return reversed(self._job)

    def __repr__(self):
        return repr(self._job)

    def __getstate__(self):
        return self._job

    def __setstate__(self, job):
        self._job = job
