import uuid
import copy
from typing import Mapping

from borgy_process_agent_api_server.models import Job, JobSpec
from borgy_process_agent_api_server.models.base_model_ import Model

from borgy_process_agent.job import Restart
from borgy_process_agent.utils import get_now_isoformat, Indexer

SPEC_DEFAULTS = {
    'command': ['bash', '-c', 'sleep 10'],
    'createdBy': '',
    'environmentVars': [],
    'interactive': False,
    'labels': [],
    'maxRunTimeSecs': 0,
    'name': '',
    'options': {},
    'preemptable': True,
    'reqCores': 1,
    'reqGpus': 0,
    'reqRamGbytes': 1,
    'restart': Restart.NO.value,
    'stdin': False,
    'volumes': [],
    'workdir': ''
}


class MockJob():

    def __init__(self, index=None, **kwargs):
        self._idx = Indexer()
        job_id = str(uuid.uuid4())
        self._job = {
            'alive': False,
            'billCode': '',
            'command': [],
            'createdBy': 'guillaume.smaha@elementai.com',
            'createdOn': get_now_isoformat(),
            'environmentVars': [f'EAI_PROCESS_AGENT_INDEX={self._idx.next()}'],
            'evictOthersIfNeeded': False,
            'image': 'images.borgy.elementai.net/borgy/borsh:latest',
            'id': job_id,
            'interactive': False,
            'isProcessAgent': False,
            'labels': [],
            'maxRunTimeSecs': 0,
            'name': job_id + "-" + str(uuid.uuid4()),
            'options': {},
            'preemptable': True,
            'reqCores': 1,
            'reqGpus': 0,
            'reqRamGbytes': 1,
            'restart': Restart.NO.value,
            'runs': [{
                'id': str(uuid.uuid4()),
                'jobId': job_id,
                'createdOn': get_now_isoformat(),
                'state': 'QUEUING',
                'info': {},
                'ip': '127.0.0.1',
                'nodeName': 'local',
            }],
            'state': 'QUEUING',
            'stateInfo': '',
            'stdin': False,
            'volumes': [],
            'workdir': ""
        }

        if 'state' in kwargs:
            self._job['state'] = kwargs['state']
            self._job['runs'][0]['state'] = kwargs['state']

        for k, v in kwargs.items():
            self._job[k] = v

        if index is not None:
            self._set_index(index)

    def get(self):
        return self._job

    def _set_index(self, index):
        for var in self._job['environmentVars']:
            if var.startswith('EAI_PROCESS_AGENT_INDEX='):
                self._job['environmentVars'].remove(var)
                break
        self._job['environmentVars'].append(f"EAI_PROCESS_AGENT_INDEX={index}")

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


def model_to_json(model: Model) -> Mapping:
    mdict = model.to_dict()
    out = {}
    for k, v in mdict.items():
        out[model.attribute_map[k]] = v
    return out


def make_spec(*args, **kwargs) -> JobSpec:
    spec = copy.deepcopy(SPEC_DEFAULTS)
    spec.update(kwargs)
    return JobSpec.from_dict(spec)


def mock_job_from_job(job: Job, **updates) -> MockJob:
    spec = model_to_json(job.spec)
    spec.update(updates)
    return MockJob(index=job.index, **spec)
