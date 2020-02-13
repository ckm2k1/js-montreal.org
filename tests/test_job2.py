import uuid
from unittest.mock import patch
from typing import List
from datetime import datetime

import pytest

from borgy_process_agent.models import OrkJob
from borgy_process_agent.enums import State, Restart
from borgy_process_agent.job2 import Job


def make_spec(**kwargs):
    spec = {
        'command': ["/bin/bash"],
        'image': 'ubuntu:18.04',
    }
    spec.update(kwargs)
    return spec


@patch('borgy_process_agent.job2.get_now', return_value=datetime(2020, 1, 1, 12, 0, 0))
class TestJob2:

    # def test_init_fail(self):
    #     job = Job(1, 'parent')
    #     assert job.updated is None
    #     assert job.created is not None
    #     assert job.user is None
    #     assert job.parent_id == 'parent'
    #     assert job.state == State.PENDING

    def test_init_from_new_spec(self, utcmock):
        job = Job.from_spec(1, 'user', 'parent', spec=make_spec())

        assert job.user == 'user'
        assert job.parent_id == 'parent'
        assert job.index == 1
        assert isinstance(job.ork_job, OrkJob)
        assert job.state == State.PENDING
        assert not job.has_changed('state')
        assert job.id is None
        assert job.created == datetime(2020, 1, 1, 12, 0, 0)
        assert job.ork_job.command == ['/bin/bash']
        assert job.ork_job.image == 'ubuntu:18.04'
        assert job.ork_job.restart == Restart.NO.value
        assert job.name == 'child-job-1'
        assert utcmock.call_count == 1
        assert job.is_pending()

    def test_init_from_ork_job(self, utcmock, fixture_loader):
        ojdict = fixture_loader('ork_job.json')
        job = Job.from_ork(ojdict)

        assert isinstance(job.ork_job, OrkJob)
        assert job.user == 'user@elementai.com'
        assert job.parent_id == 'aaaabbbb-1234-1234-1234-aaabbbcccddd'
        assert job.state == State.RUNNING
        assert not job.has_changed('state')
        assert job.id == 'ddddffff-1234-1234-1234-cccdddeeefff'
        assert job.created == datetime(2020, 1, 1, 12, 0, 0)
        assert job.ork_job.command == ["/bin/bash"]
        assert job.ork_job.image == 'ubuntu:18.04'
        assert job.ork_job.restart == Restart.NO.value
        assert job.name == 'child-job-0'
        assert utcmock.call_count == 1
        assert job.is_acked()

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
        assert job.created == datetime(2020, 1, 1, 12, 0, 0)
        assert job.updated == datetime(2020, 1, 1, 12, 0, 0)
        assert job.ork_job.command == ["/bin/bash"]
        assert job.ork_job.image == 'ubuntu:18.04'
        assert job.name == 'child-job-0'
        assert utcmock.call_count == 2
        assert job.is_acked()
        assert job.has_changed('state')
        assert job.has_changed('id')
        assert not job.has_changed('createdBy')

    def test_equality(self, utcmock):

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

    def test_copy(self, utcmock):
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

    def test_methods(self, utcmock, fixture_loader):

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
