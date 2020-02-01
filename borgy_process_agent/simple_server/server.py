import json
import uuid
import asyncio
import logging
import pathlib
from typing import Callable
from functools import partial

import jinja2
import aiohttp_jinja2
from aiohttp import web, Signal, WSMsgType
from borgy_process_agent.utils import ComplexEncoder
from borgy_process_agent.controller import BaseAgent

# from borgy_process_agent_api_server.models import HealthCheck

logger = logging.getLogger(__name__)

app = None
routes = web.RouteTableDef()

customdumps = partial(json.dumps, cls=ComplexEncoder)


def get_loop() -> asyncio.AbstractEventLoop:
    return asyncio.get_event_loop()


@routes.get('/')
async def index(request: web.Request):
    stats = request.app['agent'].get_stats()
    context = {
        'id': request.app['pa_id'],
        'user': request.app['user'],
        'js_entrypoint': 'main.js',
        **stats,
    }
    return aiohttp_jinja2.render_template('index.html', request, context)


@routes.get('/ws')
async def websocket_handler(request: web.Request):
    socket = web.WebSocketResponse()
    sid = uuid.uuid4()
    request.app['sockets'][sid] = socket

    if not socket.prepared:
        await socket.prepare(request)

    async for msg in socket:
        if msg.type == WSMsgType.TEXT:
            if msg.data == 'close':
                await socket.close()
            else:
                await socket.send_json(request.app['agent'].get_stats(), dumps=customdumps)
        elif msg.type == WSMsgType.ERROR:
            logger.exception('socket connection closed with exception %s', socket.exception())

    if not socket.closed:
        await socket.close()
    del request.app['sockets'][sid]

    return socket


@routes.get('/jobs/{job_id}')
async def job_view(request: web.Request):
    jid = request.match_info['job_id']

    context = {
        'id': request.app['pa_id'],
        'user': request.app['user'],
        'js_entrypoint': 'job_view.js',
        'stylesheets': ['job_view.css'],
        'inline_js': f'window.__jid = "{jid}";'
    }

    return aiohttp_jinja2.render_template('index.html', request, context)


@routes.get('/v1/health')
async def health(request: web.Request):
    stats = request.app['agent'].get_health()
    logger.info('Agent health stats: %s', stats)

    return web.json_response({
        'isReady': stats['is_ready'],
        'isShutdown': stats['is_shutdown'],
    })


@routes.get('/v1/jobs')
async def get_jobs(request: web.Request):
    agent = request.app['agent']
    loop = request.loop
    jobs = agent.create_jobs()
    logger.debug('GET /v1/jobs -- %s', jobs)
    loop.create_task(request.app['events'].send())
    return web.json_response(jobs)


@routes.put('/v1/jobs')
async def update_jobs(request: web.Request):
    agent = request.app['agent']
    jobs = await request.json()
    logger.debug('PUT /v1/jobs -- %s', jobs)
    fut = agent.update_jobs(jobs)
    request.loop.create_task(request.app['events'].send(fut))
    return web.Response(text='Updated jobs')


@routes.get('/stats')
async def get_stats(request: web.Request):
    return web.json_response(text=customdumps(request.app['agent'].get_stats()))


@routes.get('/kill')
async def kill(request: web.Request):
    get_loop().call_soon(shutdown)
    return web.Response(text='Shutting down server.')


async def _send_update_to_clients(app: web.Application, fut: asyncio.Future = None):
    if fut is not None:
        await fut

    for sock in app['sockets'].values():
        if sock.prepared:
            await sock.send_json(app['agent'].get_stats(), dumps=customdumps)


async def cleanup_handler(app):
    for socket in app['sockets'].values():
        if socket.prepared:
            await socket.close()
    logger.debug('Closed all websockets.')


def init(agent: BaseAgent, on_cleanup: Callable[[web.Application], None] = None):
    global app
    static_path = pathlib.Path(__file__).parent / 'static'

    app = web.Application()
    tmpl_loader = jinja2.PackageLoader('borgy_process_agent.simple_server', 'static')
    aiohttp_jinja2.setup(app, loader=tmpl_loader)
    app.router.add_static('/static/', path=static_path, name='static')
    app['agent']: BaseAgent = agent
    app['events']: Signal = Signal(app)
    app['sockets']: dict = {}
    app['user'] = agent.user
    app['pa_id'] = agent.id
    app['shutdown'] = asyncio.Event()

    app['events'].append(partial(_send_update_to_clients, app))
    app['events'].freeze()
    app.add_routes(routes)

    app.on_cleanup.append(cleanup_handler)
    if on_cleanup is not None:
        app.on_cleanup.append(on_cleanup)

    return app


def shutdown():
    logger.debug('Running server shutdown()')
    app['shutdown'].set()


async def run(app, host='0.0.0.0', port=8666, *args, **kwargs):
    try:
        runner = web.AppRunner(app, handle_signals=False)
        await runner.setup()
        site = web.TCPSite(runner, host=host, port=port)
        await site.start()
        await app['shutdown'].wait()
    except asyncio.CancelledError:
        logger.info('Server coroutine was cancelled!')
    finally:
        await runner.cleanup()
        logger.info('Server done, exiting.')
