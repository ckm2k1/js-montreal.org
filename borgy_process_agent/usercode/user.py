import copy
import logging
from collections import deque

logging.basicConfig(format='%(asctime)s] -- %(threadName)s: %(message)s', level=logging.DEBUG)
logger = logging.getLogger('user_logger')

base_job: dict = {
    'image': 'ubuntu:18.04',
    'command': [
        'bash', '-c', 'rand=`shuf -i 0-10 -n 1`; if [[ $rand -gt 0 ]]; then echo '
        '"oh yeah $rand"; sleep 15; echo "DONE"; else echo "FAILED with $rand"; exit 1; fi;'
    ],
    'preemptable': True,
    'reqGpus': 1,
    'options': {
        'alphabits': {
            'interrupts': 1,
            'interrupt-after': 5
        }
    }
}

jobs = deque([copy.deepcopy(base_job) for i in range(50)])


async def user_update(agent, jobs):
    for job in jobs:
        logger.debug('Updating job %s -- %s', job.index, job.state)


async def user_create(agent):
    global total
    result = []

    while jobs:
        result.append(copy.deepcopy(jobs.popleft()))

    if not result:
        return None

    return result
