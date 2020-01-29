import pytest
import uuid
import asyncio

from borgy_process_agent_api_server.models import JobsOps

from borgy_process_agent.controller import init, BaseAgent
from tests.utils import make_spec


@pytest.mark.asyncio
class TestController:

    async def test_init(self, event_loop: asyncio.AbstractEventLoop):
        agent = init('user', uuid.uuid4(), event_loop, debug=True)
        assert isinstance(agent, BaseAgent)

    async def test_run(self, event_loop: asyncio.AbstractEventLoop):
        pa_id = uuid.uuid4()
        agent = init('user', pa_id, event_loop, debug=True)
        jobs = [make_spec().to_dict() for i in range(10)]

        async def update(agent, jobs=None):
            print('update')

        async def create(agent):
            out = []
            if not jobs:
                return None
            while jobs:
                out.append(jobs.pop())
            return out

        agent.register_callback('create', create)
        agent.register_callback('update', update)

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
