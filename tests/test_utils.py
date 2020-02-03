import os
import json
import uuid
import inspect
from unittest.mock import Mock

import pytest

from datetime import datetime, timezone, timedelta
from borgy_process_agent import utils


class TestUtils:

    def test_taketimes(self):
        res = list(utils.taketimes(list(range(100)), 5))
        assert res == [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)]

    def test_deepchain(self):
        a = {'a': 1}
        b = {'b': 2}
        c = {'c': 3}

        dcm = utils.DeepChainMap(a, b, c)
        assert dcm['a'] == 1
        dcm.pop('b')
        assert not b
        item = dcm.pop('nope', default='yeah')
        assert item == 'yeah'

        dcm['c'] = 10
        assert dcm.get('c') == 10

        dcm['g'] = 20
        assert dcm['g'] == 20
        del dcm['g']
        assert 'g' not in dcm

        with pytest.raises(expected_exception=KeyError, match='bad'):
            dcm.pop('bad')

        with pytest.raises(expected_exception=KeyError, match='bad'):
            del dcm['bad']

    def test_fmt_datetime(self):
        assert utils.fmt_datetime(None) == ''
        assert utils.fmt_datetime(datetime(2020, 5, 10, 12, 30, 5, 0)) == '2020-05-10 12:30:05.000'

    def test_objdict(self):
        od = utils.ObjDict({'a': 'b', 'c': 'd', 'e': 'f'})
        assert od.a == 'b'
        assert od.c == 'd'
        assert od.e == 'f'

        od.a = 'cc'
        assert od.a == 'cc'
        assert od['a'] == 'cc'

        del od.a
        assert 'a' not in od
        assert hasattr(od, 'a') is False

        with pytest.raises(expected_exception=AttributeError):
            del od.nope
        with pytest.raises(expected_exception=KeyError):
            del od['nope']

    def test_indexer(self):
        idx = utils.Indexer()
        assert idx.next() == 0
        assert idx.last == 0
        assert idx.cur == 1

        assert idx() == 1
        assert idx.last == 1
        assert idx.cur == 2

        arr = [i for i in idx.cap(10)]
        assert arr == [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        assert idx._cap is None

        idx.reset(10)
        assert idx.cur == 10
        assert idx.last == 10
        assert idx() == 10
        assert idx.last == 10
        assert idx.cur == 11

        # Resets to previous initialization.
        idx.reset()
        assert [i for i in idx.cap(5)] == [10, 11, 12, 13, 14]
        assert idx.last == 14
        assert idx.cur == 15

    def test_load_module_from_path(self):
        from pathlib import Path
        mpath = Path(__file__).absolute().parent / 'fixtures/code.py'
        module = utils.load_module_from_path(mpath)
        assert module.some_var == 'value'

        with pytest.raises(expected_exception=AssertionError):
            utils.load_module_from_path('')

        with pytest.raises(expected_exception=AssertionError):
            utils.load_module_from_path('nope')

    def test_complex_encoder(self):
        uid = uuid.uuid4()
        obj = {
            'a': 'b',
            'e': [],
            'c': b'\x99',
            'uid': uid,
        }
        jstr = json.dumps(obj, cls=utils.ComplexEncoder, sort_keys=True)
        assert jstr == f'{{"a": "b", "c": "\\ufffd", "e": [], "uid": "{uid}"}}'

    def test_get_now(self):
        dt = utils.get_now()
        assert dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None
        assert dt.tzinfo == timezone.utc

    def test_memory_to_nbytes(self):
        assert utils.memory_str_to_nbytes('10Mi') == 10485760
        assert utils.memory_str_to_nbytes('1K') == 1000
        assert utils.memory_str_to_nbytes('1Ki') == 1024

        with pytest.raises(expected_exception=ValueError):
            utils.memory_str_to_nbytes('invalid')

        with pytest.raises(expected_exception=ValueError):
            utils.memory_str_to_nbytes('10MB')

    def test_cpu_str(self):
        assert utils.cpu_str_to_ncpu('3') == 3.0
        assert utils.cpu_str_to_ncpu('3m') == 0.003

        with pytest.raises(expected_exception=ValueError):
            utils.cpu_str_to_ncpu('invalid')

        with pytest.raises(expected_exception=ValueError):
            utils.cpu_str_to_ncpu('3sh')

    def test_td_format(self):
        delta = timedelta(days=1)
        assert utils.td_format(delta) == '24 hours'
        delta = timedelta(hours=1, minutes=10, seconds=5)
        assert utils.td_format(delta) == '1 hour, 10 minutes, 5 seconds'

    def test_datetime_stuff(self):
        st = '2020-02-02T18:13:05.000+00:00'
        assert utils.parse_iso_datetime(st) == datetime(2020, 2, 2, 18, 13, 5, tzinfo=timezone.utc)

        # No timezone. Generally not a good idea.
        st = '2020-02-02T18:13:05.000'
        assert utils.parse_iso_datetime(st) == datetime(2020, 2, 2, 18, 13, 5)

        now = utils.get_now()
        assert now.tzinfo == timezone.utc

    @pytest.mark.parametrize('fname,inp,exp', [
        ('get', 'ohyeah', 'ohyeah'),
        ('get_bool', 'true', True),
        ('get_bool', '1', True),
        ('get_bool', 'yes', True),
        ('get_bool', 'on', True),
        ('get_bool', 'false', False),
        ('get_bool', '0', False),
        ('get_bool', 'no', False),
        ('get_bool', 'hellno', False),
        ('get_int', '10', 10),
        ('get_int', '0', 0),
        ('get_float', '10.3331', 10.3331),
        ('get_float', '0.001', .001),
        ('get_float', '.002', .002),
    ])
    def test_env_types(self, fname, inp, exp):
        env = utils.Env()
        os.environ['VAR'] = inp
        assert getattr(env, fname)('VAR') == exp

    def test_env_misc(self):
        env = utils.Env()
        with pytest.raises(expected_exception=Exception):
            env.get_bool('NOPE')

        assert env.get_bool('NOPE', default=True) is True
        assert env.get_bool('NOPE', hardfail=False) is None

    @pytest.mark.asyncio
    async def test_ensure_coro(self):
        mfn = Mock()
        assert not inspect.iscoroutinefunction(mfn)
        cfn = utils.ensure_coroutine(mfn)
        assert inspect.iscoroutinefunction(cfn)
        await cfn()
        assert mfn.called_once()
