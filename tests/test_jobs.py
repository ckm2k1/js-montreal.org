import uuid
import pytest
from typing import List

from borgy_process_agent_api_server.models import JobSpec, Job as OrkJob

from borgy_process_agent.jobs import Jobs
from borgy_process_agent.job import Job
from tests.utils import make_spec, model_to_json, MockJob


@pytest.fixture
def jobs(id_=None) -> Jobs:
    id_ = id_ if id_ is not None else uuid.uuid4()
    return Jobs('user', id_, job_name_prefix='myprefix')


@pytest.fixture
def specs(id_=None) -> Jobs:
    return [make_spec() for i in range(20)]


class TestJobs:

    def test_init(self):
        id_ = uuid.uuid4()
        jobs = Jobs('user', id_, job_name_prefix='myprefix')
        assert jobs._user == 'user'
        assert jobs._pa_id == id_
        assert jobs._job_name_prefix == 'myprefix'
        assert jobs._auto_rerun is True
        assert jobs._no_new is False

    def test_create(self, jobs: Jobs, specs: List[JobSpec]):
        jobs.create([s.to_dict() for s in specs])
        assert jobs.has_pending() is True
        pending = jobs.get_pending()
        assert len(pending) == 20
        assert all(map(lambda j: isinstance(j, Job), pending))
        jobs.create(None)
        assert jobs._no_new is True
        assert jobs.all_done() is False

    def test_submitted(self, jobs: Jobs, specs: List[JobSpec]):
        jobs.create([s.to_dict() for s in specs])
        jobs.submit_pending(count=10)
        assert len(jobs.get_pending()) == 10
        assert len(jobs.get_submitted()) == 10
        jobs.submit_pending()
        assert len(jobs.get_pending()) == 0
        assert len(jobs.get_submitted()) == 20
        assert jobs.all_done() is False

    def test_update(self, jobs: Jobs, specs: List[JobSpec]):
        jobs.create([s.to_dict() for s in specs])
        ojs = []
        for job in jobs.get_pending():
            ork = MockJob(index=job.index, **model_to_json(job.spec))
            ork = ork.get()
            ork['state'] = 'RUNNING'
            ojs.append(ork)
        jobs.update_jobs(ojs)
        assert jobs.has_pending() is False
        assert len(jobs.get_submitted()) == 0
        assert len(jobs.acked_jobs) == 20
        assert all(map(lambda j: j.state.value == 'RUNNING', jobs.get_acked()))

    def test_kill(self, jobs: Jobs):
        pass

    def test_rerun(self, jobs: Jobs):
        pass

    def test_done(self, jobs: Jobs):
        pass

    def test_nonew(self, jobs: Jobs):
        pass
