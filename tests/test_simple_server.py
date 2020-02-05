from unittest.mock import patch, Mock

import pytest
import aiohttp
from aiohttp.test_utils import TestClient

from borgy_process_agent.simple_server import server
from borgy_process_agent.typedefs import EventLoop
from borgy_process_agent.action import Action

from tests.utils import AsyncMock


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

    async def test_put_jobs(self, agent, client: TestClient, loop: EventLoop):
        client = await client
        jobs = [{'id': 'job1'}, {'id': 'job2'}]
        action = Action(1, 'update', data=jobs)

        with patch.object(agent, 'update_jobs', return_value=action, create=True):
            with patch.dict(client.app, values={
                    'events': Mock(wraps=client.app['events']),
            }):
                loop.call_soon(action.complete)
                res = await client.put('v1/jobs', json=jobs)
                assert res.status == 200
                agent.update_jobs.assert_called_once()
                assert await res.text() == 'Updated jobs'
                client.app['events'].send.assert_called_once_with(action)
                assert await action == jobs
                assert action.done()

    async def test_run_and_shutdown_server(self, agent, loop: EventLoop):
        with patch.multiple(server, cleanup_handler=AsyncMock(wraps=server.cleanup_handler)):
            cleanup_mock = AsyncMock()
            app = server.init(agent, on_cleanup=cleanup_mock)
            loop.call_soon(server.shutdown)
            await server.run(app)
            cleanup_mock.assert_called_once()
            server.cleanup_handler.assert_called_once()

    async def test_kill_endpoint(self, agent, client: TestClient, loop: EventLoop):
        client = await client
        res = await client.get('/kill')
        assert res.status == 200
        assert await res.text() == 'Server shutdown requested via kill.'
        assert client.app['shutdown'].is_set()

    async def test_get_job_view(agent, client: TestClient, loop: EventLoop):
        client = await client
        res = await client.get('jobs/abc-123')
        assert res.status == 200
        body = await res.text()
        assert body.find('window.__jid = "abc-123"') != -1

    async def test_get_stats(agent, client: TestClient, loop: EventLoop):
        client = await client
        payload = {
            'a': b'\x99',
            'b': 'c',
        }
        with patch.object(client.app['agent'], 'get_stats', return_value=payload, create=True):
            res = await client.get('/stats')
            assert res.status == 200
            body = await res.json()
            assert body == {'a': '\ufffd', 'b': 'c'}

    async def test_socket_handler(self, agent, client: TestClient, loop: EventLoop):
        client = await client
        with patch.object(client.app['agent'], 'get_stats', return_value={'a': 'b'}, create=True):
            async with client.ws_connect('/ws') as ws:
                await ws.send_str('gimme stats')
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        assert msg.json() == {"a": "b"}
                        # Try the close command
                        await ws.send_str('close')
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        assert False, msg.data
