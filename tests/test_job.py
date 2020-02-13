from typing import List
import pytest

from borgy_process_agent_api_server.models import JobSpec, Job as OrkJob

from borgy_process_agent.job1 import Job, State, Restart

from tests.utils import make_spec, MockJob


class TestJob:

    def test_init_fail(self, specs: List[JobSpec]):
        with pytest.raises(expected_exception=Exception,
                           match='A spec or OrkJob is required to initialize a job.'):
            Job(1, 'user', 'pa_id')

        with pytest.raises(
                expected_exception=ValueError,
                match='Process agent job can\'t have automatic restart. Use '
                'autorerun_interrupted_jobs parameter or handle rerun on job udpate by yourself.'):
            spec = make_spec(restart=Restart.ON_INTERRUPTION.value)
            Job(1, 'user', 'pa_id', spec=spec)

    @pytest.mark.parametrize('spec', [make_spec(), make_spec().to_dict()])
    def test_basic_init(self, spec: JobSpec):
        job = Job(1, 'user', 'pa_id', spec=spec)
        assert job.jid is None
        assert job.index == 1
        assert job.user == 'user'
        assert job.pa_id == 'pa_id'
        assert isinstance(job.spec, JobSpec)
        assert job.spec.name == 'pa_child_job_1'
        assert job.spec.name == job.name
        assert job.spec.created_by == 'user'
        assert job.spec.preemptable is False
        assert job.spec.interactive is False

    def test_get_index(self, existing_jobs: List[OrkJob]):
        oj = OrkJob.from_dict(existing_jobs[0])
        assert Job.get_index(oj) == 0

        with pytest.raises(expected_exception=Exception,
                           match=f'{oj.id}: No environment vars present on job. '
                           'Most likely doesn\'t belong to this PA.'):
            oj = OrkJob.from_dict(existing_jobs[0])
            oj.environment_vars = []
            Job.get_index(oj)

        with pytest.raises(expected_exception=Exception,
                           match=f'{oj.id}: No environment var matching AGENT_INDEX.'):
            oj = OrkJob.from_dict(existing_jobs[0])
            oj.environment_vars = ['SOMEVAR=someval']
            Job.get_index(oj)

        with pytest.raises(expected_exception=Exception,
                           match=f'{oj.id}: index `EAI_PROCESS_AGENT_INDEX=nope` '
                           'could not be parsed as integer.'):
            oj = OrkJob.from_dict(existing_jobs[0])
            ind = oj.environment_vars.index('EAI_PROCESS_AGENT_INDEX=0')
            oj.environment_vars[ind] = 'EAI_PROCESS_AGENT_INDEX=nope'
            Job.get_index(oj)

    def test_methods(self):
        job = Job(1, 'user', 'pa_id', spec=make_spec())
        assert job.is_pending() is True
        assert job.is_submitted() is False
        assert job.is_finished() is False
        assert job.is_failed() is False
        assert job.is_acked() is False
        assert job.is_interrupted() is False
        assert job.is_successful() is False
        assert job.has_changed('state') is False
        assert len(job.get_runs()) == 0

        job.submit()
        assert job.is_submitted()
        assert job.is_pending() is False

        oj = MockJob(index=0, state=State.RUNNING.value)
        job.update_from_ork(oj.get_job())
        assert job.is_submitted() is False
        assert job.is_acked()
        assert job.has_changed('state')

        ojdict = oj.get()
        ojdict['state'] = State.SUCCEEDED.value
        job.update_from_ork(ojdict)
        assert job.is_acked() is False
        assert job.is_finished()
        assert job.has_changed('state')

        runs = job.get_runs()
        assert len(runs) == 1
        assert runs[0].job_id is not None and runs[0].job_id == job.jid
        assert job.has_changed('state')

    def test_equality(self):
        # index based
        j1 = Job(1, 'user', 'blah', spec=make_spec())
        j2 = Job(2, 'user', 'blah', spec=make_spec())
        assert j1 != j2

        j1 = Job(1, 'user', 'blah', spec=make_spec())
        j2 = Job(1, 'user', 'blah', spec=make_spec())
        assert j1 == j2

        # jid based
        j1 = Job(1, 'user', 'blah', spec=make_spec())
        j1.jid = 'abc123'
        j2 = Job(3, 'user', 'blah', spec=make_spec())
        j2.jid = 'abc123'
        assert j1 == j2

        j1 = Job(1, 'user', 'blah', spec=make_spec())
        j1.jid = 'abc123'
        j2 = Job(1, 'user', 'blah', spec=make_spec())
        j2.jid = 'xyz789'
        assert j1 != j2

    def test_copy(self):
        j1 = Job(1, 'user', 'blah', spec=make_spec())
        j2 = j1.copy()

        assert j1.index == j2.index
        assert j1.name == j2.name
        assert j1.created == j2.created
        assert j1.user == j2.user
        assert j1.pa_id == j2.pa_id
        # Equivalent but not same object,
        # protects against shallow copy
        # mistakes.
        assert id(j1.spec) != id(j2.spec)
        assert id(j1.ork_job) != id(j2.ork_job)
