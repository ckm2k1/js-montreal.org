from random import shuffle
from unittest.mock import Mock

import pytest

from borgy_process_agent.action import Action, ActionType


@pytest.mark.asyncio
class TestAction:

    async def test_basic_action(self):
        act = Action(1, ActionType.create, data='123')
        act.complete()
        done = Mock()
        act.on_done(done)
        res = await act
        assert res == '123'
        assert act.done()
        assert not act.failed()
        assert done.called_once()

    async def test_action_exc(self):
        act = Action(1, 'create')
        assert not act.failed()
        act.fail(Exception('oh no!'))
        done = Mock()
        act.on_done(done)
        with pytest.raises(expected_exception=Exception, match='oh no!'):
            await act

        assert act.done()
        assert act.failed()
        assert done.called_once()

    async def test_action_priority_and_ordering(self):
        acts = [Action(i, 'update') for i in range(10)]
        shuffle(acts)
        acts.sort()
        assert acts[0].prio == 0 and acts[-1].prio == 9
