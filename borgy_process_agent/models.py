from collections import UserDict

from borgy_process_agent_api_server.models import Job, JobSpec, JobRuns
from borgy_process_agent_api_server.models.base_model_ import Model  # noqa

from borgy_process_agent.typedefs import Dict
from borgy_process_agent.enums import Restart


class JsonSerializable:

    def to_json(self) -> Dict:
        mdict = self.to_dict()
        out = {}
        for k, v in mdict.items():
            out[self.attribute_map[k]] = v
        return out

    # Not strictly necessary but it's a clearer API
    # that to guess that from_dict() actually takes
    # the JSON version of the model. The get the same
    # result as implied by the from_dict() name, we
    # can use Model(**mdata).
    @classmethod
    def from_json(cls, data):  # pragma: no cover
        return cls.from_dict(data)


class OrkSpec(JobSpec, JsonSerializable):
    pass


class OrkJobsOps(JobSpec, JsonSerializable):
    pass


class OrkJobRuns(JobRuns, JsonSerializable):
    pass


class OrkJob(Job, JsonSerializable):

    def to_spec(self) -> OrkSpec:
        spec = {}
        for k in OrkSpec().attribute_map:
            spec[k] = getattr(self, k)
        return OrkSpec(**spec)


class EnvList(UserDict):

    def __init__(self, env):
        super().__init__(self._parse_env(env or []))

    def _parse_env(self, var_list):
        res = {}
        for var in var_list:
            try:
                k, v = var.split('=', 1)
            except ValueError:
                k = var
                v = None
            res[k] = v
        return res

    def to_list(self):
        return [f'{k}={v if v is not None else ""}' for k, v in self.items()]


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
