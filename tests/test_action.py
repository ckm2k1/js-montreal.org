from random import shuffle
from unittest.mock import Mock

import pytest

from borgy_process_agent.action import Action, ActionType
from borgy_process_agent.typedefs import EventLoop


@pytest.mark.asyncio
class TestAction:

    async def test_basic_action(self, event_loop: EventLoop):
        act = Action(1, ActionType.create, data='123')
        done = Mock()
        act.on_done(done)
        event_loop.call_soon(act.complete)
        res = await act
        assert res == '123'
        assert act.done()
        assert not act.failed()
        done.assert_called_once()

    async def test_action_exc(self, event_loop: EventLoop):
        act = Action(1, 'create')
        assert not act.failed()
        event_loop.call_soon(act.fail, Exception('oh no!'))
        done = Mock()
        act.on_done(done)
        with pytest.raises(expected_exception=Exception, match='oh no!'):
            await act

        assert act.done()
        assert act.failed()
        done.assert_called_once()

    async def test_action_priority_and_ordering(self):
        acts = [Action(i, 'update') for i in range(10)]
        shuffle(acts)
        acts.sort()
        for i in range(10):
            assert acts[i].prio == i
