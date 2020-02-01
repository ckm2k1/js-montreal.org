import asyncio
import logging
from uuid import UUID
from typing import List, Mapping, Callable, Optional, Awaitable, Any

from borgy_process_agent_api_server.models import Job as OrkJob, JobSpec, JobsOps

from borgy_process_agent.jobs import Jobs
from borgy_process_agent.enums import ActionType
from borgy_process_agent.action import Action
from borgy_process_agent.utils import Indexer, ensure_coroutine

logger = logging.getLogger(__name__)


def raiser(fut: asyncio.Future):
    if fut.done() and fut.exception():
        raise fut.exception()


class BaseAgent():

    def __init__(self,
                 loop,
                 pa_id,
                 user,
                 debug=None,
                 queue=None,
                 job_name_prefix='pa_child_job',
                 auto_rerun=True):
        self.user: str = user
        self.id: UUID = pa_id
        self.loop: asyncio.AbstractEventLoop = loop
        self.queue: asyncio.Queue = queue if queue is not None else asyncio.PriorityQueue(
            loop=loop)
        self._ready: bool = False
        self.update_callback: Callable[[BaseAgent, List[Mapping]], None] = None
        self.create_callback: Callable[[BaseAgent], List[JobSpec]] = None
        self.done_callback: Callable[[BaseAgent], List[JobSpec]] = None
        self.jobs: Jobs = Jobs(user, pa_id, job_name_prefix=job_name_prefix, auto_rerun=auto_rerun)
        self._finished: bool = False
        self._debug: bool = debug
        self._task_prio = Indexer(initial=1)
        self._jobs_lock: asyncio.Lock = asyncio.Lock()

    def _finish(self):
        self._finished = True

    @property
    def finished(self) -> bool:
        return self._finished

    def _can_shutdown(self) -> bool:
        return self.finished and self.queue.empty() and self.jobs.all_done()

    async def _update(self, ork_jobs: List[OrkJob]):
        async with self._jobs_lock:
            updated = self.jobs.update(ork_jobs)
            await self.update_callback(self.jobs, updated)
            logger.info(self.jobs.get_counts())

    async def _create(self):
        async with self._jobs_lock:
            jobs = await self.create_callback(self.jobs)
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
            else:  # pragma: no-branch
                raise Exception('Invalid action type')

            self.queue.task_done()
            action.done()
            logger.info('Finished processing action.')
        except Exception as ex:
            action.fail(exc=ex)
            raise

        if not self.jobs.has_more():
            logger.info('User code is finished producing jobs.')
            self._finish()

        logger.info(self.jobs.get_counts())

        return shutdown

    def _should_create(self):
        # Don't submit new create actions if we have user code running, PA is done or
        # we haven't finished flushing all pending jobs to the PA.
        return False if (self.finished or self._usercode_running()
                         or self.jobs.has_pending()) else True

    def _usercode_running(self):
        return self._jobs_lock.locked()

    def push_action(self, type: ActionType, data: Optional[List] = None) -> Action:
        logger.info('Pushing new %s action', type.value)
        prio = self._task_prio.next() if type != ActionType.shutdown else 0
        action = Action(prio, type, data=data)

        # If user code says we're done producing jobs, don't push anymore
        # 'create' actions, or if we're done and caller asks for a shutdown.
        if ((type == ActionType.shutdown and self._can_shutdown())
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

        ops = JobsOps(submit=[j.to_spec() for j in self.jobs.submit_pending(count=100)],
                      rerun=[j.jid for j in self.jobs.submit_reruns()],
                      kill=[j.jid for j in self.jobs.submit_kills()])
        return ops.to_dict()

    def create_jobs(self) -> JobsOps:
        job_ops = self.submit_pending_jobs()
        self.push_action(ActionType.create).on_done(raiser)  # remove on_done?
        return job_ops

    def update_jobs(self, jobs: List[OrkJob]) -> Action:
        return self.push_action(ActionType.update, data=jobs)

    def shutdown(self) -> Action:
        return self.push_action(ActionType.shutdown)

    def register_callback(self, type: str, callback: Callable):
        callback = ensure_coroutine(callback, loop=self.loop)
        if type == 'update':
            self.update_callback = callback
        elif type == 'create':
            self.create_callback = callback
        elif type == 'done':
            self.done_callback = callback
        else:
            raise Exception(f'Invalid callback type: {type}')

    def get_health(self) -> Mapping[str, bool]:
        ready = self._ready
        return {
            'is_ready': ready,
            # This is only true when the controller exits
            # it's .run() loop completely.
            'is_shutdown': self._can_shutdown() and not ready,
        }

    def get_stats(self) -> Mapping[str, Any]:
        return {'jobs': self.jobs.get_stats(), 'queue': self.queue.qsize(), **self.get_health()}

    async def run(self):
        self._ready = True
        while True:
            try:
                shutdown = await self._process_action()
                if shutdown or self._can_shutdown():
                    break
            except asyncio.CancelledError:
                logger.debug('Exiting controller due to CancelledError.')
                break
            finally:
                if callable(self.done_callback):
                    try:
                        await self.done_callback(self.jobs)
                    except Exception as ex:
                        logger.exception(ex)
                self._ready = False

        logger.info('Agent done, exiting...')


def init(user: str,
         pa_id: str,
         loop: asyncio.AbstractEventLoop,
         queue: Optional[asyncio.Queue] = None,
         agent: Optional[BaseAgent] = None,
         debug: Optional[bool] = None,
         auto_rerun: Optional[bool] = True) -> BaseAgent:

    if agent is None:
        agent = BaseAgent(loop, user, pa_id, queue=queue, debug=debug, auto_rerun=auto_rerun)

    return agent
