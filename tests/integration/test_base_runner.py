import os
import asyncio
from unittest.mock import patch

import pytest
from aiohttp.test_utils import TestClient

from borgy_process_agent.runners.base import BaseRunner
from borgy_process_agent.runners.ork import Runner
from borgy_process_agent.runners import docker
from borgy_process_agent.typedefs import EventLoop


class MockGov:

    def start(self):
        pass


class TestBaseRunner:

    def test_start(self, loop: EventLoop, aiohttp_client: TestClient):
        runner = BaseRunner('pa_job_id', 'user')
        runner.register_callback('create', lambda x: x)
        runner.register_callback('update', lambda x: x)

        async def quit():
            client = await aiohttp_client(runner._app)
            res = await client.get('/kill')
            assert res.status == 200

        fut = loop.create_task(quit())
        runner.start()
        assert fut.done()

    def test_ork_start(self, loop: EventLoop, aiohttp_client: TestClient):
        os.environ['EAI_USER'] = 'user'
        os.environ['EAI_JOB_ID'] = 'pa_abc_123'
        runner = Runner()
        runner.register_callback('create', lambda x: x)
        runner.register_callback('update', lambda x: x)

        async def quit():
            client = await aiohttp_client(runner._app)
            res = await client.get('/kill')
            assert res.status == 200

        fut = loop.create_task(quit())
        runner.start()
        assert fut.done()

    def test_ork_start_fail(self):
        with pytest.raises(expected_exception=RuntimeError):
            Runner()

    # @patch('borgy_process_agent.runners.docker.DockerGovernor', create=True)
    def test_docker_start(self, loop: EventLoop):
        runner = docker.Runner()
        runner.register_callback('create', lambda agent: [])
        runner.register_callback('update', lambda agent, jobs: None)
        loop.call_later(.5, runner.kill)
        runner.start()
