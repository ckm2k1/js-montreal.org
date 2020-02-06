import os
import asyncio
from unittest.mock import patch, Mock

import pytest
from aiohttp.test_utils import TestClient

from borgy_process_agent.runners.base import BaseRunner
from borgy_process_agent.runners.ork import Runner as OrkRunner
from borgy_process_agent.runners.docker import Runner as DockerRunner
from borgy_process_agent.typedefs import EventLoop

from tests.utils import AsyncMock


class MockGov:

    def start(self):
        pass


class TestBaseRunner:

    def test_start(self, loop: EventLoop):
        runner = BaseRunner('pa_job_id', 'user')
        runner.register_callback('create', lambda x: x)
        runner.register_callback('update', lambda x: x)

        loop.call_soon(runner.kill)
        runner.start()

    def test_exit_cancellation(self, loop: EventLoop):
        runner = BaseRunner('pa_job_id', 'user')
        runner.register_callback('create', lambda x: x)
        runner.register_callback('update', lambda x: x)

        async def cancel_all():
            [t.cancel() for t in asyncio.all_tasks(loop) if t != asyncio.current_task(loop)]

        loop.create_task(cancel_all())
        with patch.multiple(runner,
                            _stop_tasks=Mock(wraps=runner._stop_tasks),
                            _cancel_all_pending=Mock(wraps=runner._cancel_all_pending)):
            runner.start()
            runner._stop_tasks.assert_called_once()
            runner._cancel_all_pending.assert_called_once()

    def test_exit_exception(self, loop: EventLoop):
        runner = BaseRunner('pa_job_id', 'user')
        runner.register_callback('create', lambda x: x)
        runner.register_callback('update', lambda x: x)

        async def agent_exc():
            raise Exception('agent excepted')

        with patch.object(runner._agent, 'run', AsyncMock(wraps=agent_exc)):
            with pytest.raises(Exception, match='agent excepted'):
                runner.start()

    @patch.dict(os.environ, values={'EAI_USER': 'user', 'EAI_JOB_ID': 'pa_abc_123'})
    def test_ork_start(self, loop: EventLoop):
        runner = OrkRunner()
        runner.register_callback('create', lambda x: x)
        runner.register_callback('update', lambda x: x)
        loop.call_soon(runner.kill)
        runner.start()

    @patch.dict(os.environ, values={'EAI_USER': '', 'EAI_JOB_ID': ''})
    def test_ork_start_fail(self):
        with pytest.raises(expected_exception=RuntimeError,
                           match='Missing job id or user. The Ork runner '
                           'should generally be run in the Ork cluster.'):
            OrkRunner()

    @patch('borgy_process_agent.runners.docker.DockerGovernor', create=True)
    def test_docker_start(self, gov, loop: EventLoop):
        runner = DockerRunner()
        runner.register_callback('create', lambda agent: [])
        runner.register_callback('update', lambda agent, jobs: None)

        loop.call_later(.5, runner.kill)
        runner.start()
