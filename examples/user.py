import copy
import logging
from collections import deque

logging.basicConfig(format='%(asctime)s] -- %(threadName)s: %(message)s', level=logging.DEBUG)
logger = logging.getLogger('user_logger')

base_job: dict = {
    'image': 'ubuntu:18.04',
    'command': [
        'bash', '-c', 'if [[ $EAI_PROCESS_AGENT_INDEX = 3 ]]; then exit 1; fi;'
        'if [[ `shuf -i 0-10 -n 1` -gt 2 ]]; then sleep 600; echo \'DONE\';'
        'else exit 1; fi;'
    ],
    'preemptable': True,
    'reqGpus': 1
}

jobs = deque([copy.deepcopy(base_job) for i in range(50)])


async def user_update(agent, jobs):
    for j in jobs:
        logger.debug('Updating job %s', j['job']['index'])


async def user_create(agent):
    global total
    result = []

    while jobs and len(result) < 5:
        result.append(copy.deepcopy(jobs.popleft()))

    if not result:
        return None

    return result
