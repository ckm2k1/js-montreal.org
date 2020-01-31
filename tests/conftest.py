import uuid
import json
from typing import List
from pathlib import Path

import pytest

from borgy_process_agent_api_server.models import JobSpec
from borgy_process_agent.jobs import Jobs

from tests.utils import make_spec

SpecList = List[JobSpec]


@pytest.fixture
def jobs(id_=None) -> Jobs:
    id_ = id_ if id_ is not None else uuid.uuid4()
    return Jobs('user', id_, job_name_prefix='myprefix')


@pytest.fixture
def specs(id_=None) -> SpecList:
    return [make_spec() for i in range(20)]


@pytest.fixture
def existing_jobs() -> List:
    fixtures = Path(__file__).absolute().parent / 'fixtures'
    with open(fixtures / 'existing_jobs.json', 'r') as fp:
        data = json.load(fp)
    return data
