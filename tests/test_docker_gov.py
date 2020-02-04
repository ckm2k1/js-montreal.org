import enum
from typing import List, Mapping, Callable
from unittest.mock import patch, Mock

from borgy_process_agent_api_server.models import JobSpec, JobsOps

from borgy_process_agent.runners.docker_gov import DockerGovernor
from borgy_process_agent.utils import get_now_isoformat


class DockerStatus(enum.Enum):
    unknown = 'unknown'
    restarting = 'restarting'
    running = 'running'
    paused = 'paused'
    exited = 'exited'


class MockDockerContainer:

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
                'ExitCode': 0,
                'Error': '',
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

    @property
    def status(self):
        return self.attrs['State']['Status']

    @status.setter
    def status(self, val):
        self.attrs['State']['Status'] = val

    def set_state(self, **kwargs):
        self.attrs['State'].update(kwargs)

    @property
    def name(self):
        name = self.attrs.get('Name')
        if name is not None:
            return name.lstrip('/')
        return name

    @name.setter
    def name(self, val):
        self.attrs['Name'] = val

    def stop(self):
        self._stopped = True
        self.set_state(Status=DockerStatus.exited.value,
                       Running=False,
                       FinishedAt=get_now_isoformat())

    def logs(self, **kwargs):
        return self._logs

    def remove(self):
        self._removed = True
        self.status = DockerStatus.exited.value

    def init(self):
        self.set_state(StartedAt='',
                       FinishedAt='',
                       Status=DockerStatus.unknown.value,
                       Running=False,
                       Paused=False,
                       Restarting=False,
                       Dead=False,
                       ExitCode=0,
                       Error='')

    def start(self):
        self.set_state(StartedAt=get_now_isoformat(),
                       Status=DockerStatus.running.value,
                       Running=True)

    @classmethod
    def from_spec(cls, spec):
        cont = cls()
        cont.name = f'/{spec.get("name")}'
        cont.attrs['Config']['Image'] = spec.get('image')
        cont.attrs['Config']['Env'] = spec.get('environment')
        cont.attrs['Config']['Cmd'] = spec.get('command')
        return cont


class MockDockerIter():

    def __init__(self, containers: List[Mapping], init=True):
        self._containers: List[MockDockerContainer] = [
            MockDockerContainer(cont) for cont in containers
        ]
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
            cont = MockDockerContainer.from_spec(kwargs)
        cont.start()
        self._containers.append(cont)
        return cont

    def list(self, *args, **kwargs):
        return self._containers

    def __iter__(self):
        return iter(self._containers)


def empty_ops():
    return JobsOps(False, submit=[], rerun=[], kill=[])


class TestDockerGov:

    def test_create_jobs(self, fixture_loader: Callable):
        docker_iter = MockDockerIter([])
        specs_json = fixture_loader('specs.json')

        with patch('borgy_process_agent.runners.docker_gov.docker.from_env'):
            gov = DockerGovernor()
            specs = [JobSpec.from_dict(spec) for spec in specs_json['submit']]
            ops = JobsOps(submit=specs, rerun=[], kill=[])

            with patch.object(gov._docker, 'containers', wraps=docker_iter):
                with patch.multiple(gov._jobs_api,
                                    v1_jobs_get_with_http_info=Mock(side_effect=[
                                        (ops, 200, {}),
                                        (empty_ops(), 200, {}),
                                        (empty_ops(), 200, {}),
                                    ]),
                                    v1_jobs_put=Mock(return_value=None)):
                    gov._running = True
                    gov._run_iteration()
                    assert len(gov._governor_jobs) == 5

                    for jid, desc in gov._governor_jobs.items():
                        job = desc['job']
                        assert job.state == 'RUNNING'

                    # No change iteration.
                    gov._run_iteration()

                    for cont in docker_iter:
                        cont.stop()

                    gov._run_iteration()
                    assert len(gov._governor_jobs) == 5
                    for desc in gov._governor_jobs.values():
                        job = desc['job']
                        assert job.state == 'SUCCEEDED'
