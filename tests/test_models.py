import pytest

from borgy_process_agent.models import OrkJob, OrkSpec, OrkJobRuns, OrkJobsOps, EnvList


def make_spec(**kwargs):
    spec = {
        'command': ["/bin/bash"],
        'image': 'ubuntu:18.04',
    }
    spec.update(kwargs)
    return spec


class TestModels:

    @pytest.mark.parametrize('klass', [OrkJob, OrkSpec, OrkJobRuns, OrkJobsOps])
    def test_json_serialize(self, klass):
        inst = klass()
        js = inst.to_json()
        json_keys = list(inst.attribute_map.values())

        for k in js:
            assert k in json_keys

    def test_env_list(self):
        evars = [
            'VAR1=blah',
            'VAR2=blahblah',
            'VAR3',
            'VAR4=blah=blah',
        ]

        env = EnvList(evars)

        assert 'VAR1' in env
        assert 'VAR2' in env
        assert 'VAR3' in env
        assert 'VAR4' in env

        assert env.get('VAR1') == 'blah'
        assert env.get('VAR2') == 'blahblah'
        assert env.get('VAR3') is None
        assert env.get('VAR4') == 'blah=blah'

        env['VAR1'] = 'val'
        assert env['VAR1'] == 'val'

        env.pop('VAR1')
        assert 'VAR1' not in env

        assert env.to_list() == ['VAR2=blahblah', 'VAR3=', 'VAR4=blah=blah']
