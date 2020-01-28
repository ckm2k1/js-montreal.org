import asyncio
import logging
from uuid import UUID
from typing import List, Mapping, Callable, Optional, Awaitable
from functools import wraps, partial

from borgy_process_agent.jobs import Jobs
from borgy_process_agent.enums import ActionType
from borgy_process_agent.utils import Indexer
from borgy_process_agent.action import Action
from borgy_process_agent_api_server.models import Job as OrkJob, JobSpec, JobsOps

logger = logging.getLogger(__name__)


def raiser(fut: asyncio.Future):
    if fut.done() and fut.exception():
        raise fut.exception()


class BaseAgent():

    def __init__(self, loop, pa_id, user, debug=None, queue=None, job_name_prefix='pa_child_job'):
        self.user: str = user
        self.id: UUID = pa_id
        self.loop: asyncio.AbstractEventLoop = loop
        self.queue: asyncio.Queue = queue if queue is not None else asyncio.PriorityQueue(
            loop=loop)
        self._ready: bool = False
        self.update_callback: Callable[[BaseAgent, List[Mapping]], None] = None
        self.create_callback: Callable[[BaseAgent], List[JobSpec]] = None
        self.jobs: Jobs = Jobs(user, pa_id, job_name_prefix=job_name_prefix)
        self._finished: bool = False
        self._debug: bool = debug
        self._task_prio = Indexer(initial=1)
        self._jobs_lock: asyncio.Lock = asyncio.Lock()

    def _finish(self):
        self._finished = True

    @property
    def is_finished(self) -> bool:
        return self._finished

    def _ready_to_exit(self) -> bool:
        return self.is_finished and self.queue.empty() and self.jobs.all_done()

    async def _update(self, data: List[OrkJob]):
        async with self._jobs_lock:
            updated = self.jobs.update_jobs(data)
            await self.update_callback(self, updated)
            logger.info(self.jobs.get_counts())

    async def _create(self):
        async with self._jobs_lock:
            jobs = await self.create_callback(self)
            self.jobs.create(jobs)
            logger.info(self.jobs.get_counts())

    async def _process_action(self) -> Awaitable[bool]:
        logger.info('Waiting for next action...')
        action: Action = await self.queue.get()
        logger.info('Task received: %r', action)
        shutdown = False

        try:
            if action.type == ActionType.create:
                await self._create()
            elif action.type == ActionType.update:
                await self._update(action.data)
            elif action.type == ActionType.shutdown:
                self._finish()
                shutdown = True
            else:
                raise Exception('Invalid action type')

            self.queue.task_done()
            action.done()
            logger.info('Finished processing action.')
        except Exception as ex:
            action.fail(exc=ex)
            raise

        if self.jobs._no_new:
            logger.info('User code is finished producing jobs.')
            self._finish()

        logger.info(self.jobs.get_counts())

        return shutdown

    def _ensure_coro(self, fn):
        if asyncio.iscoroutinefunction(fn):
            return fn

        @wraps(fn)
        async def coro_wrapper(*args, **kwargs):
            return await self.loop.run_in_executor(None, partial(fn, *args, **kwargs))

        return coro_wrapper

    def _should_create(self):
        # Don't submit new create actions if we have user code running, PA is done or
        # we haven't finished flushing all pending jobs to the PA.
        return False if (self.is_finished or self._usercode_running()
                         or self.jobs.has_pending()) else True

    def _usercode_running(self):
        return self._jobs_lock.locked()

    def push_action(self, type: ActionType, data: Optional[List] = None) -> asyncio.Future:
        logger.info('Pushing new %s action', type.value)
        prio = self._task_prio.next() if type != ActionType.shutdown else 0
        action = Action(prio, type, data=data)

        # If user code says we're done producing jobs, don't push anymore
        # 'create' actions, or if we're done and caller asks for a shutdown.
        if ((type == ActionType.shutdown and self._ready_to_exit())
                or (type == ActionType.create and not self._should_create())):
            action.done()
            return action

        # Shutdown tasks jump immediately to the head of the queue,
        # allowing the current task to finish cleanly.
        self.queue.put_nowait(action)
        logger.info('Queued %s action.', type.value)
        logger.debug('Task payload: %s', data or '--')
        return action

    def submit_pending_jobs(self) -> Mapping:
        if self._usercode_running():
            return JobsOps(submit=[], rerun=[], kill=[]).to_dict()

        self.jobs.submit_pending()
        self.jobs.submit_jobs_to_rerun()
        self.jobs.submit_jobs_to_kill()

        ops = JobsOps(submit=[j.to_spec() for j in self.jobs.get_submitted()],
                      rerun=[j.jid for j in self.jobs.get_rerun()],
                      kill=[j.jid for j in self.jobs.get_kill()])
        return ops.to_dict()

    def create_jobs(self) -> asyncio.Future:
        res = self.submit_pending_jobs()
        self.push_action(ActionType.create).on_done(raiser)
        return res

    def update_jobs(self, jobs: List[OrkJob]) -> asyncio.Future:
        return self.push_action(ActionType.update, data=jobs)

    def shutdown(self) -> asyncio.Future:
        return self.push_action(ActionType.shutdown)

    def register_callback(self, type: str, callback: Callable):
        callback = self._ensure_coro(callback)
        if type == 'update':
            self.update_callback = callback
        elif type == 'create':
            self.create_callback = callback
        else:
            raise Exception(f'Invalid callback type: {type}')

    def get_health(self):
        return {
            'is_ready': self._ready,
            'is_shutdown': self._ready_to_exit(),
        }

    def get_stats(self):
        return {'jobs': self.jobs.get_stats(), 'queue': self.queue.qsize(), **self.get_health()}

    async def run(self):
        self._ready = True
        while True:
            try:
                shutdown = await self._process_action()
                if shutdown or self._ready_to_exit():
                    break
            except asyncio.CancelledError:
                break
            finally:
                self._ready = False

        logger.info('Agent done, exiting...')


def init(user: str,
         pa_id: str,
         loop: asyncio.AbstractEventLoop,
         queue: Optional[asyncio.Queue] = None,
         agent: Optional[BaseAgent] = None,
         debug: Optional[bool] = None) -> BaseAgent:

    if agent is None:
        agent = BaseAgent(loop, user, pa_id, queue=queue, debug=debug)

    return agent
