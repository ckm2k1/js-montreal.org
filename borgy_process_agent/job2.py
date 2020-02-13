import copy
from typing import List, Optional
from collections import namedtuple

from dictdiffer import diff  # type: ignore

from borgy_process_agent.utils import get_now
from borgy_process_agent.typedefs import Datetime
from borgy_process_agent.enums import State, Restart
from borgy_process_agent.models import OrkJob, OrkSpec, OrkJobRuns, EnvList, JOB_SPEC_DEFAULTS

DiffOp = namedtuple('diffop', ('op', 'prop', 'values'))


class Job:

    def __init__(self, index: int, parent_id: str, ork_job: OrkJob):
        self.index = index
        self.created = get_now()
        self.parent_id = parent_id
        self.state = State.PENDING
        self.updated: Optional[Datetime] = None
        self.diff: List[DiffOp] = []
        self.ork_job = None
        self.update_from(ork_job)

    @classmethod
    def get_job_name(cls, index: int, name_prefix: str) -> str:
        return f'{name_prefix}-{str(index)}'

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

        name_prefix = oj.name if oj.name else name_prefix
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
            raise Exception('OrkJob does not have a valid index or agent id in it\'s environment.')

        return cls(index, parent_id, ork_job=oj)

    @property
    def user(self) -> str:
        return self.ork_job.created_by

    @property
    def id(self) -> str:
        return self.ork_job.id

    @property
    def name(self) -> str:
        return self.ork_job.name

    def update_from(self, oj: OrkJob):
        if oj.state:
            self.state = State(oj.state)
        if self.ork_job:
            self.updated = get_now()
            self.diff = [DiffOp(*e) for e in list(diff(oj.to_dict(), self.ork_job.to_dict()))]
        self.ork_job = copy.deepcopy(oj)

    def has_changed(self, prop: str) -> bool:
        for d in self.diff:
            if d.prop == prop:
                return True
        return False

    def to_spec(self) -> OrkSpec:
        return self.ork_job.to_spec()

    def copy(self) -> 'Job':
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

    def get_runs(self) -> List[OrkJobRuns]:
        runs = self.ork_job.runs
        return runs if runs is not None else []

    def __repr__(self) -> str:
        return f'<Job index={self.index}, created={self.created}, ' \
            f'updated={self.updated}, state={self.state.value}, id={self.id}>'

    def __eq__(self, other_job) -> bool:
        if self.id and other_job.id:
            return self.id == other_job.id
        return self.index == other_job.index
