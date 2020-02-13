import copy
from datetime import datetime
from collections import namedtuple
from typing import Optional, Union, MutableMapping, List, Mapping

from dictdiffer import diff  # type: ignore

from borgy_process_agent_api_server.models import Job as OrkJob, JobSpec, JobRuns  # type: ignore
from borgy_process_agent.enums import State, Restart

JOB_SPEC_DEFAULTS = {
    'command': [],
    # 'createdBy': self.user,
    # 'name': self._get_job_name(),
    'environmentVars': [],
    'interactive': False,
    'labels': [],
    'maxRunTimeSecs': 0,
    'data': {},
    'options': {},
    'preemptable': False,
    'reqCores': 1,
    'reqGpus': 0,
    'reqRamGbytes': 1,
    'restart': Restart.NO.value,
    'stdin': False,
    'volumes': [],
    # 'workdir': ""
}

DiffOp = namedtuple('diffop', ('op', 'prop', 'values'))

JobSpecDict = MutableMapping
OrkJobDict = MutableMapping


class Job:

    def __init__(self,
                 index: int,
                 user: str,
                 pa_id: str,
                 spec: Optional[JobSpecDict] = None,
                 jid: Optional[str] = None,
                 name_prefix: str = 'pa_child_job',
                 ork_job: Optional[OrkJob] = None):
        self.jid = None
        self.index: int = index
        self.user: str = user
        self.created: datetime = datetime.utcnow()
        self.updated: Optional[datetime] = None if self.jid is None else datetime.utcnow()
        self.state: State = State.PENDING
        self._name_prefix: str = name_prefix
        self.pa_id: str = pa_id
        self.ork_job: OrkJob = ork_job if ork_job is not None else OrkJob()
        self.spec: JobSpec = self._init_spec(spec=spec, ork_job=ork_job)
        self.name: str = self.spec.name
        self._diff: List[DiffOp] = []

    def _init_spec(self,
                   spec: Optional[Union[JobSpec, Mapping]] = None,
                   ork_job: Optional[OrkJob] = None) -> Optional[JobSpec]:
        if spec is not None:
            return self._make_spec(spec if isinstance(spec, dict) else spec.to_dict())
        if ork_job is not None:
            return Job.spec_from_ork_job(ork_job)
        raise Exception('A spec or OrkJob is required to initialize a job.')

    def to_dict(self):
        return {
            'index': self.index,
            'jid': self.jid,
            'user': self.user,
            'state': self.state.value,
            'created': int(self.created.timestamp()),
            'updated': int(self.updated.timestamp()) if self.updated is not None else None,
            'pa_id': self.pa_id,
            'spec': self.spec.to_dict()
        }

    @classmethod
    def get_index(cls, job: OrkJob) -> int:
        evars = job.environment_vars
        if not evars:
            raise Exception(f'{job.id}: No environment vars present on '
                            'job. Most likely doesn\'t belong to this PA.')
        try:
            index_var = [v for v in evars if v.startswith('EAI_PROCESS_AGENT_INDEX=')].pop()
            index = int(index_var.split('=')[-1])
        except IndexError:
            raise Exception(f'{job.id}: No environment var matching AGENT_INDEX.')
        except ValueError:
            raise Exception(f'{job.id}: index `{index_var}` could not be parsed as integer.')

        return index

    @classmethod
    def spec_from_ork_job(cls, oj: OrkJob) -> JobSpec:
        spec = {k: getattr(oj, k) for k in JobSpec().attribute_map}
        return JobSpec.from_dict(spec)

    @property
    def diff(self) -> List[DiffOp]:
        return self._diff

    def _get_job_name(self):
        return f'{self._name_prefix}_{str(self.index)}'

    def _make_spec(self, spec: JobSpecDict) -> JobSpec:
        base_spec = copy.deepcopy(JOB_SPEC_DEFAULTS)
        base_spec.update(spec)
        if not base_spec.get('name'):
            base_spec['name'] = self._get_job_name()
        # Non-overridable.
        base_spec['createdBy'] = self.user

        if base_spec['restart'] == Restart.ON_INTERRUPTION.value:
            raise ValueError(
                'Process agent job can\'t have automatic restart. Use '
                'autorerun_interrupted_jobs parameter or handle rerun on job udpate by yourself.')

        evars = base_spec.get('environmentVars', [])
        evars += [
            f"EAI_PROCESS_AGENT={self.pa_id}",
            f"EAI_PROCESS_AGENT_INDEX={self.index}",
        ]
        base_spec['environmentVars'] = evars

        return JobSpec.from_dict(base_spec)

    def to_spec(self) -> Optional[JobSpecDict]:
        # The JSONEncoder subclass in borgy-process-agent-api
        # already does this operation for Connexion apps,
        # but we do it manually here since we're not using
        # the BPAA.
        res = {}
        for k, v in self.spec.to_dict().items():
            out_attr = self.spec.attribute_map[k]
            res[out_attr] = v
        return res

    def update_from_ork(self, oj: Union[OrkJob, OrkJobDict]):
        if isinstance(oj, dict):
            oj = OrkJob.from_dict(oj)

        jid = oj.id
        if not self.jid:
            self.jid = jid
        self.updated = datetime.utcnow()
        self.state = State(oj.state)
        self._diff = [DiffOp(*e) for e in list(diff(oj.to_dict(), self.ork_job.to_dict()))]
        self.ork_job = copy.deepcopy(oj)

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

    def get_runs(self) -> List[JobRuns]:
        runs = self.ork_job.runs
        return runs if runs is not None else []

    def submit(self):
        self.state = State.SUBMITTED

    def kill(self):
        self.state = State.KILLED

    def has_changed(self, prop: str) -> bool:
        for d in self._diff:
            if d.prop == prop:
                return True
        return False

    def __repr__(self) -> str:
        return f'<Job index={self.index}, created={self.created}, '
        f'updated={self.updated}, state={self.state.value}, jid={self.jid}>'

    def __eq__(self, job) -> bool:
        # Job IDs should supercede index comparisons.
        if self.jid is not None and job.jid is not None:
            return self.jid == job.jid
        return self.index == job.index

    def copy(self) -> 'Job':
        return copy.deepcopy(self)
