import logging

from borgy_process_agent.utils import Env

from borgy_process_agent.runners.base import BaseRunner

env = Env()

logger = logging.getLogger(__name__)


class Runner(BaseRunner):

    def __init__(self, *args, **kwargs):
        jid = env.get('EAI_JOB_ID')
        user = env.get('EAI_USER')
        logger.info(f'Starting Ork PA for {user} -- {jid}')
        if not jid or not user:
            raise RuntimeError('Missing job id or user. The Ork runner '
                               'should generally be run in the Ork cluster.')
        super().__init__(jid, user, *args, **kwargs)
