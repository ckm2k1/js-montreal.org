import asyncio
from typing import Any, Tuple
from unittest.mock import patch, Mock

import pytest

from borgy_process_agent.simple_server import server
from borgy_process_agent.typedefs import EventLoop
from borgy_process_agent.action import Action

from aiohttp.test_utils import TestClient


class Agent:

    def __init__(self):
        self.user = 'agent_user'
        self.id = 'agent_id'


@pytest.fixture
def agent():
    return Agent()


@pytest.fixture
async def client(agent, aiohttp_client: TestClient):
    app = server.init(agent)
    return aiohttp_client(app)


class TestSimpleServer:

    async def test_init(
        self,
        agent,
        aiohttp_client: TestClient,
        loop: EventLoop,
    ):
        with patch.object(agent, 'get_stats', return_value={}, create=True):
            app = server.init(agent)
            client = await aiohttp_client(app)
            res = await client.get('/')
            assert res.status == 200
            assert res.content_type == 'text/html'

    async def test_health(self, agent, loop: EventLoop, aiohttp_client: TestClient):
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
            assert body == {'isReady': True, 'isShutdown': False}

    async def test_get_jobs(self, agent, client: TestClient, loop: EventLoop):
        action = Action(1, 'create')
        action.complete()
        client = await client
        assert agent == client.app['agent']
        with patch.object(agent, 'create_jobs', return_value=([], action), create=True):
            with patch.dict(client.app, values={
                    'events': Mock(wraps=client.app['events']),
            }):
                res = await client.get('v1/jobs')
                assert res.status == 200
                agent.create_jobs.assert_called_once()
                body = await res.json()
                assert body == []
                client.app['events'].send.assert_called_once()
