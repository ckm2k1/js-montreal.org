import uuid
import copy
import enum
import inspect
from pathlib import Path
from unittest.mock import Mock
from typing import Mapping, List

from borgy_process_agent.job import Job
from borgy_process_agent.models import OrkJob, OrkSpec, JOB_SPEC_DEFAULTS, EnvList
from borgy_process_agent.enums import Restart, State
from borgy_process_agent.utils import get_now_isoformat, Indexer

SPEC_DEFAULTS = copy.deepcopy(JOB_SPEC_DEFAULTS)
SPEC_DEFAULTS.update({
    'command': ['bash', '-c', 'sleep 10'],
    'createdBy': '',
    'name': '',
    'workdir': '',
    'billCode': '',
})


class MockJob():

    def __init__(self, index=None, **kwargs):
        self._idx = Indexer()
        job_id = str(uuid.uuid4())
        self._job = {
            'alive': False,
            'billCode': '',
            'command': [],
            'createdBy': 'user@elementai.com',
            'createdOn': get_now_isoformat(),
            'environmentVars': [
                'EAI_PROCESS_AGENT=12341234-1234-1234-1234-123456789012',
                f'EAI_PROCESS_AGENT_INDEX={self._idx.next()}',
            ],
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
                'state': State.QUEUING.value,
                'info': {},
                'ip': '127.0.0.1',
                'nodeName': 'local',
            }],
            'state': State.QUEUING.value,
            'stateInfo': '',
            'stdin': False,
            'volumes': [],
            'workdir': ""
        }

        if 'state' in kwargs:
            self._job['state'] = kwargs['state']
            self._job['runs'][0]['state'] = kwargs['state']

        for k, v in kwargs.items():
            if k == 'environmentVars':
                self._job[k] = self._merge_env(self._job[k], v or [])
            else:
                self._job[k] = v

        if index is not None:
            self._set_index(index)

    def get(self) -> dict:
        return self._job

    def _merge_env(self, local, overrides):
        local = EnvList(local)
        overrides = EnvList(overrides)
        local.update(overrides)
        return local.to_list()

    def _set_index(self, index: int):
        env = EnvList(self._job['environmentVars'])
        env['EAI_PROCESS_AGENT_INDEX'] = index
        self._job['environmentVars'] = env.to_list()

    def get_job(self) -> OrkJob:
        return OrkJob.from_json(self._job)


def make_spec(*args, **kwargs) -> OrkSpec:
    spec = copy.deepcopy(SPEC_DEFAULTS)
    spec.update(kwargs)
    return OrkSpec.from_json(spec)


def mock_job_from_job(job: Job, **updates) -> MockJob:
    oj = job.to_spec().to_json()
    oj.update(updates)
    return MockJob(index=job.index, **oj)


def parent_dir(path) -> Path:
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
