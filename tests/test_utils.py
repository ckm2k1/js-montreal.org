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
