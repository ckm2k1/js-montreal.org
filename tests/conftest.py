import uuid
import json
from typing import List

import pytest

from borgy_process_agent.jobs import Jobs
from borgy_process_agent.models import OrkSpec

from tests.utils import make_spec, parent_dir

SpecList = List[OrkSpec]


@pytest.fixture
def jobs(id_=None) -> Jobs:
    id_ = id_ if id_ is not None else uuid.uuid4()
    return Jobs('user', id_, job_name_prefix='myprefix')


@pytest.fixture
def specs() -> SpecList:
    return [make_spec() for i in range(20)]


@pytest.fixture
def fixture_loader():

    def load(path, **load_opts):
        with open(parent_dir(__file__) / f'fixtures/{path}') as file:
            data = json.load(file, **load_opts)
        return data

    return load


@pytest.fixture
def existing_jobs(fixture_loader) -> List:
    return fixture_loader('existing_jobs.json')
