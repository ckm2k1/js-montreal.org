import uuid
import pytest
import inspect
import asyncio
from unittest.mock import patch, Mock
from typing import List, Mapping

from borgy_process_agent.agent import Agent
from borgy_process_agent.typedefs import EventLoop
from borgy_process_agent.models import OrkJobsOps

from tests.utils import make_spec, AsyncMock, MockJob


@pytest.fixture
def agent(event_loop: EventLoop):
    cb_mocks = None

    def init(**kwargs):
        nonlocal cb_mocks

        pa_id = uuid.uuid4()
        init_params = {
            'debug': True,
        }
        init_params.update(kwargs)
        agent = Agent('user', pa_id, event_loop, **init_params)
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

        async def done():
            pass

        agent.register_callback('create', create)
        agent.register_callback('update', update)
        agent.register_callback('done', done)

        cb_mocks = patch.multiple(agent,
                                  _create_callback=AsyncMock(wraps=agent._create_callback),
                                  _update_callback=AsyncMock(wraps=agent._update_callback),
                                  _done_callback=AsyncMock(wraps=agent._done_callback))
        cb_mocks.start()
        return agent

    yield init
    cb_mocks.stop()


class TestAgent:

    @pytest.mark.asyncio
    async def test_init(self, event_loop: asyncio.AbstractEventLoop):
        jid = uuid.uuid4()
        agent = Agent(jid, 'user', event_loop, debug=True)
        assert agent.user == 'user'
        assert agent.id == jid
        assert isinstance(agent._queue, asyncio.PriorityQueue)

    @pytest.mark.asyncio
    async def test_create_action(self, agent: Agent):
        agent = agent()
        ops, _ = agent.create_jobs()
        assert ops == {
            'submit': [],
            'kill': [],
            'rerun': [],
            'submit_parallel': False,
        }

        await agent._process_action()
        assert not agent.shutdown

        assert len(agent.jobs.get_pending()) == 10
        assert agent.finished is False
        assert agent.jobs.has_pending()

        ops = OrkJobsOps.from_dict(agent.create_jobs()[0])
        assert len(ops.submit) == 10
        assert len(agent.jobs.get_submitted()) == 10
        assert agent._queue.empty()
        assert agent.finished is False

    @pytest.mark.asyncio
    async def test_create_max_running(self, agent: Agent, existing_jobs: List[Mapping]):
        agent = agent(max_running=3)
        ops, _ = agent.create_jobs()
        assert ops == {
            'submit': [],
            'kill': [],
            'rerun': [],
            'submit_parallel': False,
        }

        await agent._process_action()
        assert not agent.shutdown

        assert len(agent.jobs.get_pending()) == 10
        assert agent.finished is False
        assert agent.jobs.has_pending()
        assert len(agent.jobs.get_pending()) == 10

        opsdict, _ = agent.create_jobs()
        ops = OrkJobsOps.from_dict(opsdict)
        assert len(ops.submit) == 3
        assert len(agent.jobs.get_submitted()) == 3

        # ACK jobs 0-2
        ojs = [MockJob(index=i, state='RUNNING').get() for i in range(3)]
        agent.update_jobs(ojs)
        await agent._process_action()

        opsdict, _ = agent.create_jobs()
        ops = OrkJobsOps.from_dict(opsdict)
        # Since we have 3 running jobs, ops
        # will not have any new submissions.
        assert len(ops.submit) == 0
        assert len(agent.jobs.get_pending()) == 7
        assert len(agent.jobs.get_submitted()) == 0
        assert len(agent.jobs.get_acked()) == 3

        # Finish jobs 0 and 1.
        ojs = ojs = [MockJob(index=i, state='SUCCEEDED').get() for i in range(2)]
        agent.update_jobs(ojs)
        await agent._process_action()

        opsdict, _ = agent.create_jobs()
        ops = OrkJobsOps.from_dict(opsdict)
        assert len(ops.submit) == 2
        assert len(agent.jobs.get_pending()) == 5
        assert len(agent.jobs.get_submitted()) == 2
        assert len(agent.jobs.get_acked()) == 1
        assert len(agent.jobs.get_finished()) == 2

        assert agent._queue.empty()
        assert agent.finished is False

    @pytest.mark.asyncio
    async def test_update_action(self, agent: Agent, existing_jobs: List[Mapping]):
        agent = agent()
        update_fut = agent.update_jobs(existing_jobs)
        await agent._process_action()
        assert agent.shutdown is False
        res = await update_fut
        assert res
        assert len(agent.jobs.get_acked()) == 3
        assert len(agent.jobs.get_finished()) == 3

    @pytest.mark.asyncio
    async def test_usercode_exception(self, agent: Agent):
        agent = agent()

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
    async def test_no_more_jobs(self, event_loop: asyncio.AbstractEventLoop, agent: Agent):
        agent = agent()

        def user_create(agent):
            return None

        agent.register_callback('create', user_create)
        agent.create_jobs()
        await agent._process_action()
        assert agent.finished
        assert not agent.jobs.has_more()
        assert agent.ready
        assert agent._can_shutdown()

    @pytest.mark.asyncio
    async def test_shutdown(self, agent: Agent):
        agent = agent()
        assert not agent.shutdown
        assert not agent.finished
        agent.create_jobs()
        agent.create_jobs()
        agent.terminate()
        # Termination disregards any pending
        # actions, effectively a hard shutdown.
        await agent.run()
        assert agent.shutdown
        assert not agent.finished
        agent._done_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_actions_while_usercode_running(self, agent: Agent):
        agent = agent()
        ops, _ = agent.create_jobs()
        await agent._process_action()
        # Emulate user code in progress.
        async with agent._jobs_lock:
            assert ops == {'kill': [], 'rerun': [], 'submit': [], 'submit_parallel': False}
            # When user code is running create actions
            # are not queued.
            ops, action = agent.create_jobs()
            assert agent._queue.empty()
            assert action.done()
            assert not action.failed()

    @pytest.mark.asyncio
    async def test_sync_user_fns(self, agent: Agent):
        agent = agent()
        user_create = Mock(return_value=None)
        user_update = Mock()
        user_done = Mock()

        agent.register_callback('create', user_create)
        agent.register_callback('update', user_update)
        agent.register_callback('done', user_done)

        assert inspect.iscoroutinefunction(agent._create_callback)
        assert inspect.iscoroutinefunction(agent._update_callback)
        assert inspect.iscoroutinefunction(agent._done_callback)

        agent.create_jobs()
        agent.update_jobs([])
        await agent.run()
        user_create.assert_called_once()
        user_update.assert_called_once()
        user_done.assert_called_once()
        assert agent.finished
        assert agent.shutdown

    def test_invalid_register(self, agent: Agent):
        agent = agent()
        with pytest.raises(expected_exception=Exception, match='Invalid callback type: invalid'):
            agent.register_callback('invalid', lambda _: _)

    @pytest.mark.asyncio
    async def test_get_health(self, agent: Agent):
        agent = agent()
        health = agent.get_health()
        assert health['is_ready']
        assert not health['is_shutdown']
        agent.register_callback('create', lambda agent: None)
        agent.create_jobs()
        await agent.run()
        health = agent.get_health()
        assert not health['is_ready']
        assert health['is_shutdown']

    def test_get_stats(self, agent: Agent):
        agent = agent()
        with patch.object(agent.jobs, 'get_stats', return_value={}):
            stats = agent.get_stats()
            assert stats['jobs'] == {}
            assert stats['queue'] == 0
            assert 'is_ready' in stats
            assert 'is_shutdown' in stats
