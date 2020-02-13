import copy
from typing import List, Any
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
    def from_json(self, data):
        return self.from_dict(data)


class OrkSpec(JobSpec, JsonSerializable):
    pass


class JobRuns(JobRuns, JsonSerializable):
    pass


class OrkJob(Job, JsonSerializable):

    def to_spec(self):
        spec = {}
        for k in spec.attribute_map:
            spec[k] = getattr(self, k)
        return OrkSpec(**spec)


class EnvVarNotFound(Exception):
    pass


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
        return [f'{k}={v}' for k, v in self.items()]


# raise EnvVarNotFound(f'{name} was not found.')


def ork_to_spec(oj: OrkJob) -> OrkSpec:
    spec = {}
    for k in spec.attribute_map:
        spec[k] = getattr(oj, k)
    return OrkSpec(**spec)


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
