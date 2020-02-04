import uuid
import pytest
import inspect
import asyncio
from unittest.mock import patch, Mock
from typing import List, Mapping

from borgy_process_agent_api_server.models import JobsOps
from borgy_process_agent.agent import init, BaseAgent

from tests.utils import make_spec


@pytest.fixture
def agent():
    pa_id = uuid.uuid4()
    agent = init('user', pa_id, asyncio.get_event_loop(), debug=True)
    jobs = [make_spec().to_dict() for i in range(10)]

    async def update(agent, jobs=None):
        assert jobs is not None

    async def create(agent):
        out = []
        if not jobs:
            return None
        while jobs:
            out.append(jobs.pop())
        return out

    agent.register_callback('create', create)
    agent.register_callback('update', update)
    return agent


@pytest.mark.usefixtures('specs')
class TestAgent:

    @pytest.mark.asyncio
    async def test_init(self, event_loop: asyncio.AbstractEventLoop):
        agent = init('user', uuid.uuid4(), event_loop, debug=True)
        assert isinstance(agent, BaseAgent)

    @pytest.mark.asyncio
    async def test_create_action(self, agent: BaseAgent):
        ops, _ = agent.create_jobs()
        assert ops == {
            'submit': [],
            'kill': [],
            'rerun': [],
            'submit_parallel': False,
        }

        shutdown = await agent._process_action()
        assert shutdown is not True

        assert len(agent.jobs.get_pending()) == 10
        assert agent._finished is False
        assert agent.jobs.has_pending()

        ops = JobsOps.from_dict(agent.create_jobs()[0])
        assert len(ops.submit) == 10
        assert len(agent.jobs.get_submitted()) == 10
        assert agent.queue.empty()
        assert agent._finished is False

    @pytest.mark.asyncio
    async def test_update_action(self, agent: BaseAgent, existing_jobs: List[Mapping]):
        update_fut = agent.update_jobs(existing_jobs)
        shutdown = await agent._process_action()
        assert shutdown is False
        res = await update_fut
        assert res
        assert len(agent.jobs.get_acked()) == 3
        assert len(agent.jobs.get_finished()) == 3

    @pytest.mark.asyncio
    async def test_usercode_exception(self, agent: BaseAgent):

        def user_create_raise(agent):
            raise Exception('create exc')

        def user_update_raise(agent, jobs):
            raise Exception('update exc')

        agent.register_callback('create', user_create_raise)
        agent.register_callback('update', user_update_raise)

        ops, _ = agent.create_jobs()
        assert ops == {
            'submit': [],
            'kill': [],
            'rerun': [],
            'submit_parallel': False,
        }

        with pytest.raises(expected_exception=Exception):
            await agent._process_action()

        fut = agent.update_jobs([])
        with pytest.raises(expected_exception=Exception):
            await agent._process_action()
        # The returned action is Awaitable and should raise
        # as well so that callers await'ing on it will fail.
        with pytest.raises(expected_exception=Exception):
            await fut

    @pytest.mark.asyncio
    async def test_no_more_jobs(self, event_loop: asyncio.AbstractEventLoop, agent: BaseAgent):

        def user_create(agent):
            return None

        agent.register_callback('create', user_create)
        agent.create_jobs()
        await agent._process_action()
        assert agent.finished
        assert not agent.jobs.has_more()

    @pytest.mark.asyncio
    async def test_shutdown(self, event_loop: asyncio.AbstractEventLoop, agent: BaseAgent):
        agent.shutdown()
        shutdown = await agent._process_action()
        assert shutdown is True
        assert agent.finished

    @pytest.mark.asyncio
    async def test_no_actions_while_usercode_running(self, event_loop: asyncio.AbstractEventLoop,
                                                     agent: BaseAgent):

        ops, _ = agent.create_jobs()
        await agent._process_action()
        # Emulate user code in progress.
        async with agent._jobs_lock:
            assert ops == {'kill': [], 'rerun': [], 'submit': [], 'submit_parallel': False}
            # When user code is running create actions
            # are not queued.
            ops, action = agent.create_jobs()
            assert agent.queue.empty()
            assert action.done()
            assert not action.failed()

    @pytest.mark.asyncio
    async def test_sync_user_fns(self, event_loop: asyncio.AbstractEventLoop, agent: BaseAgent):

        user_create = Mock(return_value=None)
        user_update = Mock()
        user_done = Mock()

        agent.register_callback('create', user_create)
        agent.register_callback('update', user_update)
        agent.register_callback('done', user_done)

        assert inspect.iscoroutinefunction(agent.create_callback)
        assert inspect.iscoroutinefunction(agent.update_callback)
        assert inspect.iscoroutinefunction(agent.done_callback)

        agent.create_jobs()
        agent.update_jobs([])
        await agent.run()
        user_create.assert_called_once()
        user_update.assert_called_once()
        user_done.assert_called_once()
        assert agent.finished
        assert agent.get_health()['is_shutdown']

    def test_invalid_register(self, agent: BaseAgent):
        with pytest.raises(expected_exception=Exception):
            agent.register_callback('invalid', lambda _: _)

    def test_get_health(self, agent: BaseAgent):
        health = agent.get_health()
        assert not health['is_ready']
        assert not health['is_shutdown']

        agent._ready = True
        health = agent.get_health()
        assert health['is_ready']
        assert not health['is_shutdown']

        agent._finish()
        with patch.object(agent.jobs, 'all_done', return_value=[True]):
            agent._ready = False
            health = agent.get_health()
            assert not health['is_ready']
            assert health['is_shutdown']

    def test_get_stats(self, agent: BaseAgent):
        with patch.object(agent.jobs, 'get_stats', return_value={}):
            stats = agent.get_stats()
            assert stats['jobs'] == {}
            assert stats['queue'] == 0
            assert 'is_ready' in stats
            assert 'is_shutdown' in stats
