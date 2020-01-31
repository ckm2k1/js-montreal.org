import uuid
import pytest
from typing import List

from borgy_process_agent_api_server.models import JobSpec

from borgy_process_agent.jobs import Jobs
from borgy_process_agent.job import Job
from borgy_process_agent.enums import State
from tests.utils import make_spec, model_to_json, MockJob

SpecList = List[JobSpec]


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
        assert jobs.has_more() is True

    def test_create(self, jobs: Jobs, specs: SpecList):
        jobs.create([s.to_dict() for s in specs])
        assert jobs.has_pending() is True
        pending = jobs.get_pending()
        assert len(pending) == 20
        assert all(map(lambda j: isinstance(j, Job), pending))
        jobs.create(None)
        assert jobs.has_more() is False
        assert jobs.all_done() is False

    def test_submitted(self, jobs: Jobs, specs: SpecList):
        jobs.create([s.to_dict() for s in specs])
        jobs.submit_pending(count=10)
        assert len(jobs.get_pending()) == 10
        assert len(jobs.get_submitted()) == 10
        jobs.submit_pending()
        assert len(jobs.get_pending()) == 0
        assert len(jobs.get_submitted()) == 20
        assert jobs.all_done() is False

    def test_update(self, jobs: Jobs, specs: SpecList):
        jobs.create([s.to_dict() for s in specs])
        ojs = []
        for job in jobs.get_pending():
            ork = MockJob(index=job.index, **model_to_json(job.spec))
            ork = ork.get()
            ork['state'] = State.RUNNING.value
            ojs.append(ork)
        jobs.update_jobs(ojs)
        assert jobs.has_pending() is False
        assert len(jobs.get_submitted()) == 0
        assert len(jobs.acked_jobs) == 20
        assert all(map(lambda j: j.state == State.RUNNING, jobs.get_acked()))

    def test_update_non_existant(self, jobs: Jobs, specs: SpecList):
        ojs = []
        for i, spec in enumerate(specs):
            spec = model_to_json(spec)
            spec['state'] = State.RUNNING.value
            ojs.append(MockJob(index=i, **spec).get())
        jobs.update_jobs(ojs)
        assert jobs.has_pending() is False
        assert len(jobs.get_submitted()) == 0
        assert len(jobs.acked_jobs) == 20
        assert all(map(lambda j: j.state == State.RUNNING, jobs.get_acked()))

    def test_duplicate_jobs_after_restart(self, jobs: Jobs, specs: SpecList):
        ojs = []
        for i, spec in enumerate(specs):
            spec = model_to_json(spec)
            spec['state'] = State.RUNNING.value
            ojs.append(MockJob(index=i, **spec).get())
        jobs.update_jobs(ojs)
        assert len(jobs.get_acked()) == 20
        jobs.create([s.to_dict() for s in specs])
        # We shouldn't have any pending or submitted jobs
        # since they're already running from the update.
        assert len(jobs.get_pending()) == 0
        assert len(jobs.get_submitted()) == 0

    def test_kill(self, jobs: Jobs, specs: SpecList):
        jobs.create([s.to_dict() for s in specs])
        assert len(jobs.get_pending()) == 20
        jobs.submit_pending(count=10)
        assert len(jobs.get_pending()) == 10
        assert len(jobs.get_submitted()) == 10
        ojs = []
        for i, spec in enumerate(specs[:10]):
            spec = model_to_json(spec)
            spec['state'] = State.RUNNING.value
            ojs.append(MockJob(index=i, **spec).get())
        jobs.update_jobs(ojs)
        assert len(jobs.get_pending()) == 10
        assert len(jobs.get_submitted()) == 0
        assert len(jobs.get_acked()) == 10
        # Make a finished job
        job = jobs.get_acked()[0]
        spec = model_to_json(job.spec)
        foj = MockJob(index=job.index, **spec).get()
        foj['state'] = State.FAILED.value
        jobs.update_jobs([foj])
        assert len(jobs.get_finished()) == 1

        p1 = jobs.get_pending()[0]
        a1 = jobs.get_acked()[0]
        f1 = jobs.get_finished()[0]
        # Pending jobs go straight to finished.
        jobs.kill_job(p1)
        jobs.kill_job(a1)
        # Finished jobs don't need any killin'
        jobs.kill_job(f1)
        assert len(jobs.kill_jobs) == 1
        assert not jobs.kill_jobs.difference(set([a1.index]))
        assert p1 in jobs.get_finished() and p1.index not in jobs.kill_jobs
        assert f1 in jobs.get_finished() and f1.index not in jobs.kill_jobs

    def test_rerun(self, jobs: Jobs):
        pass

    def test_done(self, jobs: Jobs):
        pass

    def test_nonew(self, jobs: Jobs):
        pass
