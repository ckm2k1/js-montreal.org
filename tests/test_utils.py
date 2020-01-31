import pytest

from datetime import datetime, timezone
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
        import json
        import uuid
        uid = uuid.uuid4()
        obj = {
            'a': 'b',
            'c': b'\x99',
            'uid': uid,
        }
        jstr = json.dumps(obj, cls=utils.ComplexEncoder)
        assert jstr == f'{{"a": "b", "c": "\\ufffd", "uid": "{uid}"}}'

    def test_get_now(self):
        dt = utils.get_now()
        assert dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None
        assert dt.tzinfo == timezone.utc
