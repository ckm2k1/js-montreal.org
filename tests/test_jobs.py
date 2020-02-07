import uuid
import pytest
from typing import List

from borgy_process_agent_api_server.models import JobSpec

from borgy_process_agent.job import Job
from borgy_process_agent.jobs import Jobs
from borgy_process_agent.enums import State
from tests.utils import MockJob, model_to_json, mock_job_from_job

SpecList = List[JobSpec]


@pytest.mark.usefixtures('jobs', 'specs')
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
        jobs.create(s.to_dict() for s in specs)
        assert jobs.has_pending() is True
        pending = jobs.get_pending()
        assert len(pending) == 20
        assert all(map(lambda j: isinstance(j, Job), pending))
        jobs.create(None)
        assert jobs.has_more() is False
        assert jobs.all_done() is False

    def test_submitted(self, jobs: Jobs, specs: SpecList):
        jobs.create(s.to_dict() for s in specs)
        jobs.submit_pending(count=10)
        assert len(jobs.get_pending()) == 10
        assert len(jobs.get_submitted()) == 10
        # submit without count limit, which will
        # flush the rest of the pending queue given
        # it's default is 100.
        jobs.submit_pending()
        assert len(jobs.get_pending()) == 0
        assert len(jobs.get_submitted()) == 20
        assert jobs.all_done() is False

    def test_submit_max_running(self, jobs: Jobs, specs: SpecList):
        pass

    def test_update(self, jobs: Jobs, specs: SpecList):
        jobs.create(s.to_dict() for s in specs)
        ojs = [
            mock_job_from_job(job, state=State.RUNNING.value).get() for job in jobs.get_pending()
        ]
        jobs.update(ojs)
        assert jobs.has_pending() is False
        assert len(jobs.get_submitted()) == 0
        assert len(jobs.get_acked()) == 20
        assert all(map(lambda j: j.state == State.RUNNING, jobs.get_acked()))

        # no change in state
        job = jobs.get_acked()[0]
        last_update = job.updated
        assert job.state == State.RUNNING
        jobs.update([mock_job_from_job(job, state=State.RUNNING.value).get()])
        assert job.state == State.RUNNING
        assert job.updated > last_update

    def test_update_non_existant(self, jobs: Jobs, specs: SpecList):
        ojs = []
        for i, spec in enumerate(specs):
            spec = model_to_json(spec)
            spec['state'] = State.RUNNING.value
            ojs.append(MockJob(index=i, **spec).get())
        jobs.update(ojs)
        assert jobs.has_pending() is False
        assert len(jobs.get_submitted()) == 0
        assert len(jobs._acked_jobs) == 20
        assert all(map(lambda j: j.state == State.RUNNING, jobs.get_acked()))

    def test_duplicate_jobs_after_restart(self, jobs: Jobs, specs: SpecList):
        ojs = []
        for i, spec in enumerate(specs):
            spec = model_to_json(spec)
            spec['state'] = State.RUNNING.value
            ojs.append(MockJob(index=i, **spec).get())
        jobs.update(ojs)
        assert len(jobs.get_acked()) == 20
        jobs.create(s.to_dict() for s in specs)
        # We shouldn't have any pending or submitted jobs
        # since they're already running from the update.
        assert len(jobs.get_pending()) == 0
        assert len(jobs.get_submitted()) == 0

    def test_kill(self, jobs: Jobs, specs: SpecList):
        jobs.create(s.to_dict() for s in specs)
        assert len(jobs.get_pending()) == 20
        jobs.submit_pending(count=10)
        assert len(jobs.get_pending()) == 10
        assert len(jobs.get_submitted()) == 10
        ojs = [
            mock_job_from_job(job, state=State.RUNNING.value).get()
            for job in jobs.get_submitted()[:10]
        ]
        jobs.update(ojs)
        assert len(jobs.get_pending()) == 10
        assert len(jobs.get_submitted()) == 0
        assert len(jobs.get_acked()) == 10
        # Make a finished job
        job = jobs.get_acked()[0]
        spec = model_to_json(job.spec)
        foj = MockJob(index=job.index, **spec).get()
        foj['state'] = State.FAILED.value
        jobs.update([foj])
        assert len(jobs.get_finished()) == 1

        p1 = jobs.get_pending()[0]
        a1 = jobs.get_acked()[0]
        f1 = jobs.get_finished()[0]
        # Pending jobs go straight to finished.
        jobs.kill_job(p1)
        jobs.kill_job(a1)
        # Finished jobs don't need any killin'
        jobs.kill_job(f1)
        assert len(jobs._kill_jobs) == 1
        assert not jobs._kill_jobs.difference(set([a1.index]))
        assert p1.is_finished() is True and p1.state == State.KILLED
        assert p1 in jobs.get_finished() and p1.index not in jobs._kill_jobs
        assert f1 in jobs.get_finished() and f1.index not in jobs._kill_jobs
        assert [a1] == jobs.submit_kills() and a1.jid == jobs.submit_kills()[0].jid
        jobs.update([mock_job_from_job(a1, state=State.CANCELLED.value).get()])
        assert len(jobs._kill_jobs) == 0
        assert a1.is_finished()
        assert a1 in jobs.get_finished()

    def test_rerun(self, jobs: Jobs, specs: SpecList):
        jobs.create(s.to_dict() for s in specs)
        assert len(jobs.get_pending()) == 20
        jobs.submit_pending(count=10)
        assert len(jobs.get_pending()) == 10
        assert len(jobs.get_submitted()) == 10
        ojs = [
            mock_job_from_job(job, state=State.SUCCEEDED.value).get()
            for job in jobs.get_submitted()
        ]
        jobs.update(ojs)
        assert len(jobs.get_pending()) == 10
        assert len(jobs.get_submitted()) == 0
        assert len(jobs.get_finished()) == 10
        for job in jobs.get_finished():
            jobs.rerun_job(job)
        assert len(jobs.get_rerun()) == 10
        assert not jobs._rerun_jobs.difference(set(j.index for j in jobs.get_finished()))
        assert len(jobs.submit_reruns()) == 10
        # Make all rerun jobs
        ojs = [
            mock_job_from_job(job, state=State.RUNNING.value).get() for job in jobs.get_finished()
        ]
        jobs.update(ojs)
        assert len(jobs.get_finished()) == 0
        assert len(jobs.get_acked()) == 10
        assert len(jobs.get_rerun()) == 0

        # Reruning non (interrupted or finished) jobs is a no-op.
        jobs.rerun_job(jobs.get_by_state(State.RUNNING)[0])
        jobs.rerun_job(jobs.get_by_state(State.PENDING)[0])
        assert len(jobs.get_rerun()) == 0

    def test_auto_rerun(self, jobs: Jobs, specs: SpecList):
        jobs.create(s.to_dict() for s in specs)
        jobs.submit_pending()
        assert all(map(lambda j: j.is_submitted(), jobs.get_submitted()))
        ojs = [
            mock_job_from_job(job, state=State.RUNNING.value).get()
            for job in jobs.get_submitted()
        ]
        jobs.update(ojs)
        job = jobs.get_acked()[0]
        oj = mock_job_from_job(job, state=State.INTERRUPTED.value).get()
        jobs.update([oj])
        assert job.is_interrupted()
        assert job.index in jobs._acked_jobs and job.index in jobs._rerun_jobs
        oj['state'] = State.RUNNING.value
        jobs.update([oj])
        assert job.is_acked()
        assert len(jobs.get_rerun()) == 0

        # Disable autorerun, interrupts go to the
        # finished queue.
        jobs._auto_rerun = False
        job = jobs.get_acked()[0]
        assert job.is_acked()
        oj = mock_job_from_job(job, state=State.INTERRUPTED.value).get()
        jobs.update([oj])
        assert job.is_interrupted()
        assert job in jobs.get_finished()

    def test_done(self, jobs: Jobs, specs: SpecList):
        jobs.create(s.to_dict() for s in specs)
        jobs.submit_pending()
        ojs = [
            mock_job_from_job(job, state=State.SUCCEEDED.value).get()
            for job in jobs.get_submitted()
        ]
        jobs.update(ojs)
        assert jobs.all_done() is False
        jobs.create(None)
        assert jobs.all_done() is True

    def test_nonew(self, jobs: Jobs, specs: SpecList):
        jobs.create(s.to_dict() for s in specs)
        jobs.submit_pending()
        jobs.update(
            mock_job_from_job(job, state=State.SUCCEEDED.value).get()
            for job in jobs.get_submitted())
        jobs.create(None)
        assert jobs.has_more() is False

    def test_get_by(self, jobs: Jobs, specs: SpecList):
        jobs.create(s.to_dict() for s in specs)
        assert len(jobs.get_by_state(State.PENDING)) == 20
        jobs.submit_pending(10)
        assert len(jobs.get_by_state(State.SUBMITTED)) == 10
        assert len(jobs.get_by_state(State.PENDING)) == 10
        assert len(jobs.get_by_state(State.SUCCEEDED)) == 0
        assert len(jobs.get_by_state(State.RUNNING)) == 0
        jobs.update(
            mock_job_from_job(job, state=State.RUNNING.value).get()
            for job in jobs.get_submitted())
        assert len(jobs.get_by_state(State.RUNNING)) == 10

        assert len(jobs.get_failed()) == 0
        assert jobs.get_by_index(5).index == jobs._all_jobs[5].index

        jobs.update(
            mock_job_from_job(job, state=State.FAILED.value).get()
            for job in jobs.get_by_state(State.RUNNING)[:5])
        assert len(jobs.get_failed()) == 5

    def test_stats(self, jobs: Jobs, specs: SpecList):
        stats = jobs.get_counts()
        assert stats == {
            'pending': 0,
            'submitted': 0,
            'acked': 0,
            'succeeded': 0,
            'failed': 0,
            'cancelled': 0,
            'total': 0
        }
        jobs.create(s.to_dict() for s in specs)
        assert jobs.get_counts()['pending'] == 20
        jobs.submit_pending(5)

        counts = jobs.get_counts()
        assert counts['pending'] == 15
        assert counts['submitted'] == 5

        jobs.update(
            mock_job_from_job(job, state=State.SUCCEEDED.value).get()
            for job in jobs.get_submitted())
        counts = jobs.get_counts()
        assert counts['pending'] == 15
        assert counts['submitted'] == 0
        assert counts['succeeded'] == 5

        jobs.submit_pending(5)
        assert len(jobs.get_submitted()) == 5
        jobs.update(
            mock_job_from_job(job, state=State.FAILED.value).get() for job in jobs.get_submitted())
        counts = jobs.get_counts()
        assert counts['pending'] == 10
        assert counts['submitted'] == 0
        assert counts['failed'] == 5
        assert counts['succeeded'] == 5
