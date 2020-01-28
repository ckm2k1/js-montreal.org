import copy
from datetime import datetime
from typing import Optional, Union, Mapping
from collections import namedtuple

from dictdiffer import diff

from borgy_process_agent_api_server.models.job import Job as OrkJob
from borgy_process_agent_api_server.models.job_spec import JobSpec

from borgy_process_agent.enums import State, Restart

JOB_SPEC_DEFAULTS = {
    # 'command': [],
    # 'createdBy': self.user,
    'environmentVars': [],
    'interactive': False,
    'labels': [],
    'maxRunTimeSecs': 0,
    # 'name': self._get_job_name(),
    'options': {},
    'preemptable': True,
    'reqCores': 1,
    'reqGpus': 0,
    'reqRamGbytes': 1,
    'restart': Restart.NO.value,
    'stdin': False,
    'volumes': [],
    # 'workdir': ""
}

diffop = namedtuple('diffop', ('op', 'prop', 'values'))


class Job:

    def __init__(self,
                 index: int,
                 user: str,
                 pa_id: str,
                 spec: JobSpec = None,
                 jid: str = None,
                 name_prefix='pa_child_job',
                 ork_job=None):
        self.jid = None
        self.index: int = index
        self.user: str = user
        self.created: datetime = datetime.utcnow()
        self.updated: Optional[datetime] = None if self.jid is None else datetime.utcnow()
        self.state: State = State.PENDING
        self._name_prefix: str = name_prefix
        self.pa_id: str = pa_id
        self.ork_job: OrkJob = OrkJob.from_dict(ork_job) if ork_job is not None else OrkJob()
        if spec:
            self.spec: JobSpec = self._make_spec(spec)
        else:
            if ork_job:
                self.spec: JobSpec = Job.spec_from_ork_job(ork_job)
            else:
                raise Exception('A spec or OrkJob is required to initialize a job.')
        self.name = self.spec.name
        self._diff = []

    def to_dict(self):
        return {
            'index': self.index,
            'jid': self.jid,
            'user': self.user,
            'state': self.state.value,
            'created': int(self.created.timestamp()),
            'updated': int(self.updated.timestamp()) if self.updated is not None else None,
            'pa_id': self.pa_id,
            # 'ork_job': self.ork_job.to_dict() if self.ork_job is not None else {},
            'spec': self.spec.to_dict()
        }

    @classmethod
    def get_index(cls, job: OrkJob) -> int:
        evars = job.environment_vars
        if not isinstance(evars, list):
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
        spec = {k: getattr(oj, k) for k in JobSpec.attribute_map}
        return JobSpec.from_dict(spec)

    def _get_job_name(self):
        return f'{self._name_prefix}-{str(self.index)}'

    def _make_base_spec(self):
        spec = copy.deepcopy(JOB_SPEC_DEFAULTS)
        spec.update({
            'createdBy': self.user,
            'name': self._get_job_name(),
        })
        return spec

    def _make_spec(self, spec):
        base_spec = self._make_base_spec()
        base_spec.update(spec)

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

    def to_spec(self):
        # The JSONEncoder subclass in borgy-process-agent-api
        # already does this operation for Connexion apps,
        # but we do it manually here since we're not using
        # the BPAA.
        if self.spec is not None:
            res = {}
            for k, v in self.spec.to_dict().items():
                out_attr = self.spec.attribute_map[k]
                res[out_attr] = v
            return res
        return None

    def update_from_ork(self, oj: Union[OrkJob, Mapping]):
        if isinstance(oj, dict):
            oj = OrkJob.from_dict(oj)

        jid = oj.id
        if not self.jid:
            self.jid = jid
        self.updated = datetime.utcnow()
        self.state = State(oj.state)
        self._diff = [diffop(*e) for e in list(diff(oj.to_dict(), self.ork_job.to_dict()))]
        self.ork_job = copy.deepcopy(oj)

    def has_changed(self, prop: str) -> bool:
        for d in self._diff:
            if d.prop == prop:
                return True
        return False

    @property
    def diff(self):
        return self._diff

    def __repr__(self):
        return f'<Job index={self.index}, created={self.created}, '
        f'updated={self.updated}, state={self.state.value}, jid={self.jid}>'

    def __eq__(self, job):
        if self.jid is not None and job.jid is not None and self.jid == job.jid:
            return True
        return self.index == job.index

    def copy(self):
        return copy.deepcopy(self)
