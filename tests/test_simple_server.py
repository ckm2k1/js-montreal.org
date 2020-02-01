from unittest.mock import patch, Mock

import pytest

from borgy_process_agent.simple_server import server

from aiohttp.test_utils import TestClient


@pytest.fixture
def agent():
    agent = Mock()
    return agent


@pytest.mark.asyncio
class TestSimpleServer:

    async def test_init(self, aiohttp_client: TestClient):
        agent = Mock()
        app = server.init(agent)
        client = await aiohttp_client(app)
        res = await client.get('/')
        assert res.status == 200
        assert res.content_type == 'text/html'

    async def test_shutdown(self):
        pass

    async def test_run(self):
        pass
