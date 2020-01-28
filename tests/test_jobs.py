import uuid
import pytest

from borgy_process_agent.jobs import Jobs
from tests.utils import make_spec


@pytest.fixture
def jobs(id_=None) -> Jobs:
    id_ = id_ if id_ is not None else uuid.uuid4()
    return Jobs('user', id_, job_name_prefix='myprefix')


class TestJobs:

    def test_init(self):
        id_ = uuid.uuid4()
        jobs = Jobs('user', id_, job_name_prefix='myprefix')
        assert jobs._user == 'user'
        assert jobs._pa_id == id_
        assert jobs._job_name_prefix == 'myprefix'
        assert jobs._auto_rerun is True
        assert jobs._no_new is False

    def test_create(self, jobs: Jobs):
        specs = [make_spec() for i in range(3)]
        jobs.create(specs)
        assert jobs.has_pending() is True
        pending = jobs.get_by_type('pending')
        assert len(pending) == 3
        assert pending[0]

    def test_update(self, jobs: Jobs):
        pass

    def test_pending(self, jobs: Jobs):
        pass

    def test_submitted(self, jobs: Jobs):
        pass

    def test_acked(self, jobs: Jobs):
        pass

    def test_kill(self, jobs: Jobs):
        pass

    def test_rerun(self, jobs: Jobs):
        pass

    def test_done(self, jobs: Jobs):
        pass

    def test_nonew(self, jobs: Jobs):
        pass
