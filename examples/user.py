import copy
import logging
from collections import deque

logging.basicConfig(format='%(asctime)s] -- %(threadName)s: %(message)s', level=logging.DEBUG)
logger = logging.getLogger('user_logger')

base_job: dict = {
    'image': 'ubuntu:18.04',
    'command': [
        'bash', '-c', 'if [[ $EAI_PROCESS_AGENT_INDEX = 3 ]]; then exit 1; fi;'
        'if [[ `shuf -i 0-10 -n 1` -gt 2 ]]; then sleep 20; echo \'DONE\';'
        'else exit 1; fi;'
    ],
    'preemptable': True,
    'reqGpus': 1,
    # 'options': {
    #     'alphabits': {
    #         'interrupts': 3,
    #         'interrupt-after': 5
    #     }
    # }
}

jobs = deque([copy.deepcopy(base_job) for i in range(20)])


async def user_update(agent, jobs):
    for j in jobs:
        job = j['job']
        logger.debug('Updating job %s', job.index)
        if not job.index % 5:
            logger.debug('*********KILLING JOB***********: %s -- %s', job.index, job.jid)
            agent.kill_job(job)


async def user_create(agent):
    global total
    result = []

    while jobs and len(result) < 5:
        result.append(copy.deepcopy(jobs.popleft()))

    if not result:
        return None

    return result
