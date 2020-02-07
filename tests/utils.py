import uuid
import copy
import enum
import inspect
from unittest.mock import Mock
from typing import Mapping, List

from borgy_process_agent_api_server.models import Job as OrkJob, JobSpec
from borgy_process_agent_api_server.models.base_model_ import Model

from borgy_process_agent.job import Job
from borgy_process_agent.enums import Restart
from borgy_process_agent.utils import get_now_isoformat, Indexer

SPEC_DEFAULTS = {
    'command': ['bash', '-c', 'sleep 10'],
    'name': '',
    'createdBy': '',
    'environmentVars': [],
    'interactive': False,
    'labels': [],
    'maxRunTimeSecs': 0,
    'options': {},
    'preemptable': False,
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
        return OrkJob.from_dict(self._job)

    def get_spec(self):
        return Job.spec_from_ork_job(self.get_job())

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


def mock_job_from_job(job: OrkJob, **updates) -> MockJob:
    spec = model_to_json(job.spec)
    spec.update(updates)
    return MockJob(index=job.index, **spec)


def parent_dir(path):
    from pathlib import Path
    return Path(path).absolute().parent


class AsyncMock(Mock):
    """AsyncMock that supports 'wraps'ing coroutines
    and calling through instead of just plain mocking.
    """

    async def __call__(self, *args, **kwargs):
        if self._mock_wraps is not None and inspect.iscoroutinefunction(self._mock_wraps):
            return await super().__call__(*args, **kwargs)
        return super().__call__(*args, **kwargs)


class DockerStatus(enum.Enum):
    unknown = 'unknown'
    restarting = 'restarting'
    running = 'running'
    paused = 'paused'
    exited = 'exited'


class DockerContainer:

    def __init__(self, data=None, logs=b''):
        self.attrs = {
            'Id': '',
            'Created': get_now_isoformat(),
            'Path': 'bash',
            'Args': ['-c', 'sleep 10'],
            'State': {
                'Status': DockerStatus.unknown.value,
                'Running': False,
                'Paused': False,
                'Restarting': False,
                'OOMKilled': False,
                'Dead': False,
                'Pid': 0,
                'ExitCode': None,
                'Error': 0,
                'StartedAt': '',
                'FinishedAt': '',
            },
            'Name': '',
            'Config': {
                'Env': [],
                'Cmd': [],
                'Image': '',
            }
        }
        if data:
            self.attrs.update(data)

        self._removed = False
        self._logs = logs
        self._stopped = True
        self._paused = False

    @property
    def status(self):
        return self.attrs['State']['Status']

    @status.setter
    def status(self, val):
        self.attrs['State']['Status'] = val

    def set_state(self, **kwargs):
        self.attrs['State'].update(kwargs)

    def get_state(self, attr):
        return self.attrs['State'].get(attr)

    @property
    def name(self):
        name = self.attrs.get('Name')
        if name is not None:
            return name.lstrip('/')
        return name

    @name.setter
    def name(self, val):
        self.attrs['Name'] = val

    def stop(self, timeout=None):
        self._stopped = True
        self.set_state(Status=DockerStatus.exited.value,
                       Running=False,
                       FinishedAt=get_now_isoformat())

    def terminate(self, exit_code=0):
        if not self._stopped:
            self.set_state(Status=DockerStatus.exited.value,
                           Running=False,
                           ExitCode=exit_code,
                           FinishedAt=get_now_isoformat())

    def fail(self, exit_code):
        self.terminate()
        self.set_state(ExitCode=exit_code)

    def logs(self, **kwargs):
        return self._logs

    def remove(self):
        self._removed = True
        self.set_state(Status=DockerStatus.exited.value)

    def init(self):
        self.set_state(StartedAt='',
                       FinishedAt='',
                       Status=DockerStatus.unknown.value,
                       Running=False,
                       Paused=False,
                       Restarting=False,
                       Dead=False,
                       ExitCode=None,
                       Error='')

    def start(self):
        self._stopped = False
        self.set_state(StartedAt=get_now_isoformat(),
                       Status=DockerStatus.running.value,
                       Running=True)

    def interrupt(self):
        self._stopped = False
        self._paused = True
        self.set_state(Status=DockerStatus.paused.value, Paused=True, Running=True)

    @classmethod
    def from_spec(cls, spec):
        cont = cls()
        cont.name = f'/{spec.get("name")}'
        cont.attrs['Config']['Image'] = spec.get('image')
        cont.attrs['Config']['Env'] = spec.get('environment')
        cont.attrs['Config']['Cmd'] = spec.get('command')
        return cont


class DockerIter():

    def __init__(self, containers: List[Mapping], init=True):
        self._containers: List[DockerContainer] = [DockerContainer(cont) for cont in containers]
        if init:
            for cont in self._containers:
                cont.init()

    def get_cont(self, name):
        assert name
        matches = [c for c in self._containers if c.name == name]
        if matches:
            return matches.pop()
        return None

    def run(self, *args, **kwargs):
        name = kwargs.get('name')
        cont = self.get_cont(name)
        if cont is None:
            cont = DockerContainer.from_spec(kwargs)
        cont.start()
        self._containers.append(cont)
        return cont

    def list(self, *args, **kwargs):
        return self._containers

    def __iter__(self):
        return iter(self._containers)
