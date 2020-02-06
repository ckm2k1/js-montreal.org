import asyncio
import logging
from uuid import UUID
from typing import List, Mapping, Callable, Optional, Awaitable, Any, Tuple

from borgy_process_agent_api_server.models import Job as OrkJob, JobSpec, JobsOps

from borgy_process_agent.jobs import Jobs
from borgy_process_agent.enums import ActionType
from borgy_process_agent.action import Action
from borgy_process_agent.utils import Indexer, ensure_coroutine
from borgy_process_agent.typedefs import EventLoop

logger = logging.getLogger(__name__)


class BaseAgent():

    def __init__(self,
                 pa_id: str,
                 user: str,
                 loop: Optional[EventLoop] = None,
                 debug: Optional[bool] = None,
                 queue: Optional[asyncio.Queue] = None,
                 job_name_prefix: str = 'pa_child_job',
                 auto_rerun: bool = True):
        self.id: UUID = pa_id
        self.user: str = user
        self._loop: EventLoop = loop
        self._queue: asyncio.Queue = queue if queue else asyncio.PriorityQueue(loop=loop)
        self._update_callback: Callable[[BaseAgent, List[Mapping]], None] = None
        self._create_callback: Callable[[BaseAgent], List[JobSpec]] = None
        self._done_callback: Callable[[BaseAgent], List[JobSpec]] = None
        self._debug: bool = debug
        self._task_prio = Indexer(initial=1)
        self._jobs_lock: asyncio.Lock = asyncio.Lock()
        self.jobs: Jobs = Jobs(user, pa_id, job_name_prefix=job_name_prefix, auto_rerun=auto_rerun)

        self._finished: bool = False
        self._shutdown: bool = False
        self._ready: bool = True

    def finish(self):
        self.finished = True

    @property
    def finished(self) -> bool:
        return self._finished

    @finished.setter
    def finished(self, val):
        self._finished = val

    def make_ready(self):
        self.ready = True
        self.shutdown = False

    @property
    def ready(self) -> bool:
        return self._ready

    @ready.setter
    def ready(self, val):
        self._ready = val

    def make_shutdown(self):
        self.shutdown = True

    @property
    def shutdown(self) -> bool:
        return self._shutdown

    @shutdown.setter
    def shutdown(self, val):
        self._shutdown = val

    def _can_shutdown(self) -> bool:
        # We also check for queue.empty() because
        # we want to be sure all update() actions have been
        # processed before deciding we're really done.
        # CREATE actions are prevented from being queue'd
        # once usercode reports .has_more() == false.
        return self.finished and self.jobs.all_done() and self._queue.empty()

    async def _update(self, ork_jobs: List[OrkJob]):
        async with self._jobs_lock:
            updated = self.jobs.update(ork_jobs)
            await self._update_callback(self.jobs, updated)
            logger.info(self.jobs.get_counts())

    async def _create(self):
        async with self._jobs_lock:
            jobs = await self._create_callback(self.jobs)
            self.jobs.create(jobs)
            logger.info(self.jobs.get_counts())

    async def _process_action(self) -> Awaitable[bool]:
        logger.info('Waiting for next action...')
        action: Action = await self._queue.get()
        logger.info('Task received: %r', action)

        try:
            if action.type == ActionType.create:
                await self._create()
            elif action.type == ActionType.update:
                await self._update(action.data)
            elif action.type == ActionType.shutdown:  # pragma: no branch
                self.make_shutdown()

            if not self.jobs.has_more():
                logger.info('User code is finished producing jobs.')
                self.finish()

            action.complete()
            logger.info('Finished processing action.')
        except Exception as ex:
            action.fail(ex)
            raise
        finally:
            self._queue.task_done()
            logger.info(self.jobs.get_counts())

    def _should_create(self):
        # Don't submit new create actions if we have user code running, PA is done or
        # we haven't finished flushing all pending jobs to the PA.
        return False if (self.finished or self._usercode_running()
                         or self.jobs.has_pending()) else True

    def _usercode_running(self):
        return self._jobs_lock.locked()

    def _next_prio(self, atype: ActionType) -> int:
        if atype == ActionType.shutdown:
            return 0
        return self._task_prio.next()

    def push_action(self, type: ActionType, data: Optional[List] = None) -> Action:
        logger.info('Pushing new %s action', type.value)
        action = Action(self._next_prio(type), type, data=data)

        # If user code says we're done producing jobs, don't push anymore
        # 'create' actions, or if we're already shutdown and caller asks for a shutdown.
        if type == ActionType.create and not self._should_create():
            action.complete()
            return action

        # Shutdown tasks jump immediately to the head of the queue,
        # allowing the current task to finish cleanly.
        self._queue.put_nowait(action)
        logger.info('Queued %s action.', type.value)
        logger.debug('Task payload: %s', data or '--')
        return action

    def submit_pending_jobs(self) -> Mapping:
        if self._usercode_running():
            return JobsOps(submit=[], rerun=[], kill=[]).to_dict()

        ops = JobsOps(submit=[j.to_spec() for j in self.jobs.submit_pending(count=100)],
                      rerun=[j.jid for j in self.jobs.submit_reruns()],
                      kill=[j.jid for j in self.jobs.submit_kills()])
        return ops.to_dict()

    def create_jobs(self) -> Tuple[JobsOps, Action]:
        job_ops = self.submit_pending_jobs()
        action = self.push_action(ActionType.create)
        return job_ops, action

    def update_jobs(self, jobs: List[OrkJob]) -> Action:
        return self.push_action(ActionType.update, data=jobs)

    def terminate(self) -> Action:
        return self.push_action(ActionType.shutdown)

    def register_callback(self, type: str, callback: Callable):
        callback = ensure_coroutine(callback, loop=self._loop)
        if type == 'update':
            self._update_callback = callback
        elif type == 'create':
            self._create_callback = callback
        elif type == 'done':
            self._done_callback = callback
        else:
            raise Exception(f'Invalid callback type: {type}')

    def get_health(self) -> Mapping[str, bool]:
        return {
            'is_ready': self.ready,
            # This is only true when the agent exits
            # it's .run() loop completely.
            'is_shutdown': self.shutdown and not self.ready,
        }

    def get_stats(self) -> Mapping[str, Any]:
        return {
            'jobs': self.jobs.get_stats(),
            'queue': self._queue.qsize(),
            'total': len(self.jobs.get_all()),
            **self.get_health(),
        }

    async def run(self):
        try:
            self.make_ready()
            while True:
                try:
                    await self._process_action()
                    # self.shutdown is a hard shutdown normally
                    # triggered by a caller using the terminate()
                    # method. _can_shutdown() is the more natural
                    # course where all jobs finishing and usercode
                    # reporting there are no more new jobs to submit.
                    if self.shutdown or self._can_shutdown():
                        break
                except asyncio.CancelledError:
                    logger.debug('Exiting agent due to CancelledError.')
                    break
        finally:
            if callable(self._done_callback):
                try:
                    await self._done_callback(self.jobs)
                except Exception as ex:
                    logger.exception(ex)

            self.ready = False
            self.make_shutdown()

        logger.info('Agent done, exiting...')


def init(user: str,
         pa_id: str,
         loop: Optional[EventLoop] = None,
         queue: Optional[asyncio.Queue] = None,
         agent: Optional[BaseAgent] = None,
         debug: Optional[bool] = None,
         auto_rerun: Optional[bool] = True) -> BaseAgent:

    return BaseAgent(user, pa_id, loop=loop, queue=queue, debug=debug, auto_rerun=auto_rerun)
