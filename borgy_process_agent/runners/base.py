import asyncio
import logging

from borgy_process_agent import controller
from borgy_process_agent.simple_server import server

logger = logging.getLogger(__name__)


class BaseRunner():

    def __init__(self,
                 pa_jid,
                 pa_user,
                 debug=None,
                 api_host='0.0.0.0',
                 api_port=8666,
                 keep_alive=False):
        self._pa_job_id = pa_jid
        self._pa_user = pa_user
        self._debug = debug
        self._api_host = api_host
        self._api_port = api_port
        self._loop = asyncio.get_event_loop()
        # self._loop.set_exception_handler(self._loop_exc_handler)
        self._agent = self.init_agent()
        self._app = server.init(self._agent, self._on_cleanup)
        self._tasks = []
        self._exc_exit = False
        if debug is not None:
            self._loop.set_debug(debug)

    def init_agent(self):
        return controller.init(self._pa_job_id, self._pa_user, self._loop, debug=self._debug)

    def _loop_exc_handler(self, loop: asyncio.AbstractEventLoop, context: dict):
        logger.debug('Running GLOBAL loop exception handler.')
        logger.exception(context.get('exception'))
        return loop.default_exception_handler(context)

    def _schedule(self):
        self._agent_task: asyncio.Task = self._loop.create_task(self._agent.run())
        self._server_task: asyncio.Task = self._loop.create_task(
            server.run(self._app, host=self._api_host, port=self._api_port))
        self._tasks = [self._agent_task, self._server_task]

    async def _run(self):
        self._schedule()
        done, pending = await asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)
        for d in done:
            if d.exception():
                raise d.exception()
        return done, pending

    def start(self):
        try:
            self._loop.run_until_complete(self._run())
            self.stop()
        except KeyboardInterrupt:
            logger.debug('Handling KeyboardInterrupt.')
            self.stop()
        except asyncio.CancelledError:
            logger.info('Handling CancelledError.')
            self.stop()
        except Exception as ex:
            logger.info('Handling unknown exception.')
            logger.exception(ex)
            self._exc_exit = ex
            self.stop()
        finally:
            if not self._loop.is_closed():
                self._loop.close()
            if self._exc_exit:
                raise self._exc_exit

    def _stop_tasks(self):
        pass

    def _cancel_all_pending(self):
        to_cancel: set = {t for t in asyncio.all_tasks(self._loop)}
        # Why? because if a task failed before we arrive here, we
        # won't be able to collect the exception from that task.
        to_cancel.update(set(self._tasks))
        if not to_cancel:
            return

        for task in to_cancel:
            if not task.done():
                task.cancel()

        self._loop.run_until_complete(
            asyncio.gather(*to_cancel, loop=self._loop, return_exceptions=True))

        for task in to_cancel:
            if task.cancelled():
                continue
            if task.done():
                exc = task.exception()
                if exc:
                    logger.exception(exc, exc_info=exc)

    def stop(self):
        logger.debug('Running stop()')
        self._stop_tasks()
        self._cancel_all_pending()

    async def _on_cleanup(self, app):
        logger.debug('Running server on_cleanup.')

    def register_callback(self, type, callback):
        self._agent.register_callback(type, callback)
