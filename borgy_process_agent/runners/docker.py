import uuid
import logging
from concurrent.futures import ThreadPoolExecutor

from borgy_process_agent.utils import Env
from borgy_process_agent.runners.base import BaseRunner
from borgy_process_agent.runners.docker_gov import DockerGovernor

env = Env()

logger = logging.getLogger(__name__)


class Runner(BaseRunner):

    def __init__(self,
                 jid=env.get('PA_DOCKER_JOB_ID', default=uuid.uuid4()),
                 user=env.get('PA_DOCKER_USER', default='local_pa_user'),
                 poll_interval=3,
                 **kwargs):
        super().__init__(jid, user, **kwargs)
        logger.info(f'Starting Docker PA for {user} -- {jid}')
        self._dockergov = DockerGovernor()
        self._poll_interval = poll_interval

    def _schedule(self):
        super()._schedule()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='DockerGovernor')
        self._governor_coro = self._loop.run_in_executor(self._pool, self._dockergov.start)
        self._tasks.append(self._governor_coro)

    def _stop_tasks(self):
        try:
            self._dockergov.stop()
            self._pool.shutdown()
        except Exception as ex:
            logger.exception('Failed shutting down dockergov', exc_info=ex)

        super()._stop_tasks()
