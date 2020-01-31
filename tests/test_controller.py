import uuid
import pytest
import asyncio
from typing import List, Mapping

from borgy_process_agent_api_server.models import JobsOps
from borgy_process_agent.controller import init, BaseAgent

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


@pytest.mark.asyncio
@pytest.mark.usefixtures('specs')
class TestController:

    async def test_init(self, event_loop: asyncio.AbstractEventLoop):
        agent = init('user', uuid.uuid4(), event_loop, debug=True)
        assert isinstance(agent, BaseAgent)

    async def test_create_action(self, event_loop: asyncio.AbstractEventLoop, agent: BaseAgent):
        ops = agent.create_jobs()
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

        ops = JobsOps.from_dict(agent.create_jobs())
        assert len(ops.submit) == 10
        assert len(agent.jobs.get_submitted()) == 10
        assert agent.queue.empty()
        assert agent._finished is False

    async def test_update_action(self, event_loop: asyncio.AbstractEventLoop, agent: BaseAgent,
                                 existing_jobs: List[Mapping]):
        update_fut = agent.update_jobs(existing_jobs)
        shutdown = await agent._process_action()
        assert shutdown is False
        res = await update_fut
        assert res
        assert len(agent.jobs.get_acked()) == 3
        assert len(agent.jobs.get_finished()) == 3

    async def test_usercode_exception(self, event_loop: asyncio.AbstractEventLoop,
                                      agent: BaseAgent):

        def user_create_raise(agent):
            raise Exception('oh noes!')

        agent.register_callback('create', user_create_raise)
        ops = agent.create_jobs()
        assert ops == {
            'submit': [],
            'kill': [],
            'rerun': [],
            'submit_parallel': False,
        }

        with pytest.raises(expected_exception=Exception):
            await agent._process_action()
