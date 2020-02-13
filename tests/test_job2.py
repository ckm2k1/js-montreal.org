import uuid
from unittest.mock import patch
from datetime import datetime, timezone

import pytest

from borgy_process_agent.models import OrkJob, EnvList
from borgy_process_agent.enums import State, Restart
from borgy_process_agent.job2 import Job

UTC = timezone.utc
fixed_dt = datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)


def make_spec(**kwargs):
    spec = {
        'command': ["/bin/bash"],
        'image': 'ubuntu:18.04',
    }
    spec.update(kwargs)
    return spec


class TestJob2:

    @patch('borgy_process_agent.job2.get_now', return_value=fixed_dt)
    def test_init_from_new_spec(self, utcmock):
        job = Job.from_spec(1, 'user', 'parent', spec=make_spec())

        assert job.user == 'user'
        assert job.parent_id == 'parent'
        assert job.index == 1
        assert isinstance(job.ork_job, OrkJob)
        assert job.state == State.PENDING
        assert not job.has_changed('state')
        assert job.id is None
        assert job.created == datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert job.ork_job.command == ['/bin/bash']
        assert job.ork_job.image == 'ubuntu:18.04'
        assert job.ork_job.restart == Restart.NO.value
        assert job.name == 'child-job-1'
        assert utcmock.call_count == 1
        assert job.is_pending()
        env = EnvList(job.ork_job.environment_vars)
        assert env['EAI_PROCESS_AGENT_INDEX'] == '1'
        assert env['EAI_PROCESS_AGENT'] == 'parent'

        # custom name
        job = Job.from_spec(1, 'user', 'parent', spec=make_spec(name='customname'))
        assert job.name == 'customname-1'

        with pytest.raises(expected_exception=ValueError,
                           match='Process agent jobs can\'t have automatic restart. '
                           'The agent will handle restarts automatically.'):
            Job.from_spec(1, 'user', 'blah', make_spec(restart=Restart.ON_INTERRUPTION.value))

    @pytest.mark.parametrize('as_dict', [True, False])
    @patch('borgy_process_agent.job2.get_now', return_value=fixed_dt)
    def test_init_from_ork(self, utcmock, fixture_loader, as_dict):
        ojdict = fixture_loader('ork_job.json')
        if as_dict:
            job = Job.from_ork(ojdict)
        else:
            job = Job.from_ork(OrkJob.from_dict(ojdict))

        assert isinstance(job.ork_job, OrkJob)
        assert job.user == 'user@elementai.com'
        assert job.parent_id == 'aaaabbbb-1234-1234-1234-aaabbbcccddd'
        assert job.state == State.RUNNING
        assert not job.has_changed('state')
        assert job.id == 'ddddffff-1234-1234-1234-cccdddeeefff'
        assert job.created == datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert job.ork_job.command == ["/bin/bash"]
        assert job.ork_job.image == 'ubuntu:18.04'
        assert job.ork_job.restart == Restart.NO.value
        assert job.name == 'child-job-0'
        assert utcmock.call_count == 1
        assert job.is_acked()

        evars = EnvList(ojdict['environmentVars'])
        with pytest.raises(
                expected_exception=Exception,
                match='OrkJob does not have a valid index or agent id in it\'s environment.'):
            ojdict['environmentVars'] = []
            Job.from_ork(ojdict)

        with pytest.raises(
                expected_exception=Exception,
                match='OrkJob does not have a valid index or agent id in it\'s environment.'):
            env = evars.copy()
            env.pop('EAI_PROCESS_AGENT_INDEX')
            ojdict['environmentVars'] = env.to_list()
            Job.from_ork(ojdict)

        with pytest.raises(
                expected_exception=Exception,
                match='OrkJob does not have a valid index or agent id in it\'s environment.'):
            env = evars.copy()
            env.pop('EAI_PROCESS_AGENT')
            ojdict['environmentVars'] = env.to_list()
            Job.from_ork(ojdict)

    @patch('borgy_process_agent.job2.get_now', return_value=fixed_dt)
    def test_update_from(self, utcmock, fixture_loader):
        ojdict = fixture_loader('ork_job.json')
        spec = {
            'command': ['/bin/bash'],
            'image': 'ubuntu:18.04',
        }
        job = Job.from_spec(0,
                            'user@elementai.com',
                            'aaaabbbb-1234-1234-1234-aaabbbcccddd',
                            spec=spec)

        assert isinstance(job.ork_job, OrkJob)
        assert job.id is None
        assert job.user == 'user@elementai.com'
        assert job.parent_id == 'aaaabbbb-1234-1234-1234-aaabbbcccddd'
        assert job.state == State.PENDING
        assert not job.has_changed('state')
        assert job.ork_job.restart == Restart.NO.value
        assert job.name == 'child-job-0'
        assert utcmock.call_count == 1
        assert job.is_pending()

        job.update_from(OrkJob.from_dict(ojdict))
        assert job.id == 'ddddffff-1234-1234-1234-cccdddeeefff'
        assert job.created == datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert job.updated == datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert job.ork_job.command == ["/bin/bash"]
        assert job.ork_job.image == 'ubuntu:18.04'
        assert job.name == 'child-job-0'
        assert utcmock.call_count == 2
        assert job.is_acked()
        assert job.has_changed('state')
        assert job.has_changed('id')
        assert not job.has_changed('createdBy')

        # No change
        job.update_from(OrkJob.from_dict(ojdict))
        assert not job.has_changed('state')

    def test_equality(self):

        # index based
        j1 = Job.from_spec(1, 'user', 'blah', spec=make_spec())
        j2 = Job.from_spec(2, 'user', 'blah', spec=make_spec())
        assert j1 != j2

        j1 = Job.from_spec(1, 'user', 'blah', spec=make_spec())
        j2 = Job.from_spec(1, 'user', 'blah', spec=make_spec())
        assert j1 == j2

        # id based
        jid = uuid.uuid4()
        j1 = Job.from_spec(1, 'user', 'blah', spec=make_spec(id=jid))
        j2 = Job.from_spec(3, 'user', 'blah', spec=make_spec(id=jid))
        assert j1 == j2

        j1 = Job.from_spec(1, 'user', 'blah', spec=make_spec(id=jid))
        j2 = Job.from_spec(1, 'user', 'blah', spec=make_spec(id=uuid.uuid4()))
        assert j1 != j2

    def test_copy(self):
        j1 = Job.from_spec(1, 'user', 'blah', spec=make_spec())
        j2 = j1.copy()

        assert j1.index == j2.index
        assert j1.name == j2.name
        assert j1.created == j2.created
        assert j1.user == j2.user
        assert j1.parent_id == j2.parent_id
        # Equivalent but not same object,
        # protects against shallow copy
        # mistakes.
        assert id(j1.ork_job) != id(j2.ork_job)

    def test_methods(self, fixture_loader):

        job = Job.from_spec(1, 'user', 'pa_id', spec=make_spec())
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

        ojdict = fixture_loader('ork_job.json')
        job.update_from(OrkJob.from_dict(ojdict))
        assert job.is_submitted() is False
        assert job.is_acked()
        assert job.has_changed('state')

        ojdict['state'] = State.SUCCEEDED.value
        job.update_from(OrkJob.from_dict(ojdict))
        assert job.is_acked() is False
        assert job.is_finished()
        assert job.has_changed('state')

        runs = job.get_runs()
        assert len(runs) == 1
        assert runs[0].job_id is not None and runs[0].job_id == job.id
        assert job.has_changed('state')

        job.kill()
        assert job.state == State.KILLED

    def test_to_spec(self):
        spec = make_spec(preemptable=True, req_cores=1)
        job = Job.from_spec(1, 'user', uuid.uuid4(), spec=spec)
        exp = job.to_spec()

        assert exp.command == ['/bin/bash']
        assert exp.image == 'ubuntu:18.04'
        assert exp.environment_vars
        # Makes sure we output OrkSpec and not OrkJob.
        assert not hasattr(exp, 'runs')

    @patch('borgy_process_agent.job2.get_now', return_value=fixed_dt)
    def test_to_dict(self, utcmock):
        spec = make_spec()
        job = Job.from_spec(1, 'user', 'blah', spec=spec)
        jd = job.to_dict()

        assert jd['id'] is None
        assert jd['index'] == 1
        assert jd['user'] == 'user'
        assert jd['parent_id'] == 'blah'
        assert jd['state'] == State.PENDING.value
        assert jd['created'] == 1577880000
        assert jd['updated'] is None
        assert jd['ork_job'] == job.ork_job.to_json()
        assert jd['ork_job']['createdBy'] == 'user'
