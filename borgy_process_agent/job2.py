import copy
from typing import List, Optional
from collections import namedtuple

from dictdiffer import diff  # type: ignore

from borgy_process_agent.utils import get_now
from borgy_process_agent.typedefs import Datetime
from borgy_process_agent.enums import State, Restart
from borgy_process_agent.models import OrkJob, OrkSpec, EnvList, JOB_SPEC_DEFAULTS

DiffOp = namedtuple('diffop', ('op', 'prop', 'values'))


class Job:

    def __init__(self, index: int, parent_id: str, ork_job: Optional[OrkJob] = None):
        self.index = index
        self.parent_id = parent_id
        self.state = State.PENDING
        self.updated: Optional[Datetime] = None
        self._diff: List[DiffOp] = []
        self.ork_job = OrkJob()
        if ork_job:
            self.update_from(ork_job)

    def update_from(self, oj: OrkJob):
        self.updated = get_now()
        if oj.state:
            self.state = State(oj.state)
        self._diff = [DiffOp(*e) for e in list(diff(oj.to_dict(), self.ork_job.to_dict()))]
        self.ork_job = copy.deepcopy(oj)

    @property
    def user(self) -> str:
        return self.ork_job.created_by

    @property
    def created(self) -> Datetime:
        return self.ork_job.created_on

    @property
    def id(self) -> str:
        return self.ork_job.id

    @classmethod
    def get_job_name(cls, index: int, name_prefix: str) -> str:
        return f'{name_prefix}_{str(index)}'

    @classmethod
    def from_spec(cls,
                  index,
                  user,
                  parent_id,
                  spec: OrkSpec,
                  name_prefix: str = 'child-job') -> 'Job':
        base_spec = copy.deepcopy(JOB_SPEC_DEFAULTS)
        base_spec.update(spec)
        oj = OrkJob.from_dict(base_spec)

        if not oj.name:
            oj.name = cls.get_job_name(index, name_prefix)

        oj.created_by = user

        if oj.restart == Restart.ON_INTERRUPTION.value:
            raise ValueError('Process agent jobs can\'t have automatic restart. '
                             'The agent will handle restarts automatically.')

        evars = EnvList(oj.environment_vars)
        evars['EAI_PROCESS_AGENT'] = parent_id
        evars['EAI_PROCESS_AGENT_INDEX'] = index
        oj.environment_vars = evars.to_list()
        return Job(index, parent_id, ork_job=oj)

    @classmethod
    def from_ork(cls, oj: OrkJob) -> 'Job':
        if not isinstance(oj, OrkJob):
            oj = OrkJob.from_dict(oj)

        env = EnvList(oj.environment_vars)
        index = env.get('EAI_PROCESS_AGENT_INDEX')
        parent_id = env.get('EAI_PROCESS_AGENT')
        if index is None or not parent_id:
            raise Exception('OrkJob does not have valid index and agent id in it\'s environment.')

        return cls(index, oj.created_by, parent_id, ork_job=oj)

    def __repr__(self) -> str:
        return f'<Job index={self.index}, created={self.created}, ' \
            f'updated={self.updated}, state={self.state.value}, id={self.id}>'

    def __eq__(self, other_job):
        if self.id and other_job.id:
            return self.id == other_job.id
        return self.index == other_job.index

    def to_spec(self):
        return self.ork_job.to_spec()

    def copy(self):
        return copy.deepcopy(self)

    def submit(self):
        self.state = State.SUBMITTED

    def kill(self):
        self.state = State.KILLED

    def is_pending(self) -> bool:
        return self.state == State.PENDING

    def is_submitted(self) -> bool:
        return self.state == State.SUBMITTED

    def is_successful(self) -> bool:
        return self.state == State.SUCCEEDED

    def is_finished(self) -> bool:
        return self.state.is_finished()

    def is_failed(self) -> bool:
        return self.state == State.FAILED

    def is_acked(self) -> bool:
        return self.state.is_acked()

    def is_interrupted(self) -> bool:
        return self.state == State.INTERRUPTED
