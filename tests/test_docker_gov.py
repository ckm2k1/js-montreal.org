import json
from typing import List, Mapping, Callable
from unittest.mock import patch, DEFAULT, Mock

import pytest

from borgy_process_agent_api_server.models import JobSpec, JobRuns, JobsOps, Job

from borgy_process_agent.runners.docker_gov import DockerGovernor
from tests.utils import model_to_json, parent_dir, make_spec


class MockDockerContainer:

    def __init__(self, data, logs=b''):
        self.attrs = data
        self._removed = False
        self._logs = logs
        self._stopped = True

    def stop(self):
        self._stopped = True

    def logs(self):
        return self._logs

    def remove(self):
        self._removed = True

def get_container(*args, **kwargs):
    name = kwargs.get('name')

# @pytest.fixture
# def fixture_loader():
#     with open(parent_dir(__file__) / 'fixtures/containers.json') as file:
#         data = json.load(file)
#     return [MockDockerContainer(cont) for cont in data]


@pytest.fixture
def fixture_loader():

    def load(path, **load_opts):
        with open(parent_dir(__file__) / f'fixtures/{path}') as file:
            data = json.load(file, **load_opts)
        return data

    return load


class TestDockerGov:

    def test_create_jobs(self, fixture_loader: Callable):
        containers_json = fixture_loader('containers.json')
        specs_json = fixture_loader('specs.json')

        gov = DockerGovernor()
        specs = [JobSpec.from_dict(spec) for spec in specs_json['submit']]
        ops = JobsOps(submit=specs, rerun=[], kill=[])

        with patch.multiple(gov,
                            # _update_job_state=DEFAULT,
                            _send_job_updates=DEFAULT,
                            _get_new_jobs=Mock(return_value=ops),
                            _check_jobs_update=Mock(return_value=[])):
            # with patch.object(gov._docker.containers.run, wraps=get_container)
            gov._running = True
            # gov._run_iteration()
            # assert len(gov._governor_jobs) == 5

            # for jid, desc in gov._governor_jobs.items():
            #     job = desc['job']
            #     assert job.state == 'QUEUED'
