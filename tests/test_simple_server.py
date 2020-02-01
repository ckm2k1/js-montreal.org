import asyncio
from unittest.mock import patch, Mock

import pytest

from borgy_process_agent.simple_server import server

from aiohttp.test_utils import TestClient


class Agent:

    def __init__(self):
        self.user = 'agent_user'
        self.id = 'agent_id'


@pytest.fixture
def agent():
    return Agent()


class TestSimpleServer:

    async def test_init(self, agent, loop: asyncio.AbstractEventLoop, aiohttp_client: TestClient):
        with patch.object(agent, 'get_stats', return_value={}, create=True):
            app = server.init(agent)
            client = await aiohttp_client(app)
            res = await client.get('/')
            assert res.status == 200
            assert res.content_type == 'text/html'

    async def test_health(self, agent, loop, aiohttp_client):
        health_response = {
            'is_ready': True,
            'is_shutdown': False,
        }

        with patch.object(agent, 'get_health', return_value=health_response, create=True):
            app = server.init(agent)
            client = await aiohttp_client(app)
            res = await client.get('v1/health')
            assert res.status == 200
            body = await res.json()
            assert body == {
                'isReady': True,
                'isShutdown': False
            }
