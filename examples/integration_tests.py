import json
import logging

from borgy_process_agent.enums import State
from borgy_process_agent.utils import Env

logging.basicConfig(datefmt='%Y-%m-%d %H:%M:%S',
                    format=('%(asctime)s.%(msecs)03d %(name)15s '
                            '[%(levelname)s] %(message)s'))

logger = logging.getLogger("main")
logger.setLevel(logging.INFO)

jobs = []
iteration = 0
iteration_max = None
n_children = None
job_idx_to_kill = None
job_id_to_kill = None


def user_create(agent):
    global iteration, iteration_max
    iteration += 1

    if iteration == iteration_max:
        return None

    try:
        rc = next(jobs)
        logger.info("{}: job request - Returning {} jobs".format(iteration, len(rc)))
        return rc
    except StopIteration:
        logger.info("{}: job request - Done".format(iteration))
    except Exception as e:
        logger.info("{}: job request - Unhandled exception".format(iteration))
        logger.exception(e)
    return None


def user_update(agent, jobs):
    global iteration, job_idx_to_kill, job_id_to_kill
    iteration += 1

    logger.info("{}: job update".format(iteration))
    for job in jobs:
        logger.info("{}: {} {}".format(iteration, job['job'].id, job['job'].state))

    jobs = list(agent.get_jobs().values())
    if (job_idx_to_kill > -1 and job_idx_to_kill < len(jobs)
            and jobs[job_idx_to_kill].state == State.RUNNING.value):
        job_id_to_kill = jobs[job_idx_to_kill].id
        logger.info("{}: job update - Kill job {}".format(iteration, job_id_to_kill))
        agent.kill_job(job_id_to_kill)
        job_idx_to_kill = -1


def init(env):
    global jobs, iteration_max, iteration, n_children, job_idx_to_kill, job_id_to_kill

    try:
        iteration_max = env.get_int('PA_TESTER_ITERATION', default=30)
        n_children = env.get_int('PA_TESTER_CHILDREN', default=0)
        job_idx_to_kill = env.get_int('PA_TESTER_CHILD_IDX_TO_KILL', -1)

        if job_idx_to_kill > -1:
            assert job_idx_to_kill < n_children, \
                "PA_TESTER_CHILD_IDX_TO_KILL needs a value between 0 and (PA_TESTER_CHILDREN - 1)"

        def get_json(name, default_value, types):
            json_str = env.get(name, default=default_value)
            try:
                data = json.loads(json_str)
            except Exception:
                assert False, '{} should be valid JSON. Was:\n{}'.format(name, json_str)
            assert type(data) in types, "name {} must be in [{}]".format(name, types)
            return data

        # content of PA_TESTER_JOBS must be a single job_spec (dict) or a list of job_specs
        job_specs = get_json(
            'PA_TESTER_JOBS',
            '{"reqCores": "1", "reqGpus": "0", "image": "ubuntu:18.04", "command": ["sleep", "5"]}',  # noqa
            [type(dict()), type(list())])

        if isinstance(job_specs, dict):
            job_specs = [job_specs]

        logger.info("Job Specs:")
        for i, job_spec in enumerate(job_specs):
            assert isinstance(job_spec, dict), \
                f'job_specs entry {i} should be a dict. Was {type(job_spec)}'
            logger.info("{}: {}".format(i, job_spec))

        # content of PA_TESTER_JOBS must be a list of job_specs
        jobs_provider_data = get_json('PA_TESTER_JOBS_PROVIDER', '[]', [type(list())])

        jobs_provider = []

        # XOR - only one of the two must be set
        assert (n_children > 0) != (len(jobs_provider_data) > 0), \
            'One and only one of PA_TESTER_CHILDREN or PA_TESTER_JOBS_PROVIDER must be set'

        if n_children:
            jobs_provider_data = [[0 for i in range(n_children)]]

        logger.info("Jobs Provider returns:")
        for i, new_jobs in enumerate(jobs_provider_data):
            assert isinstance(new_jobs, list), 'new_jobs entry {} should be a list. Was {}'.format(
                i, type(new_jobs))

            if i == 1 and len(new_jobs) == 0:
                new_jobs = [0 for i in range(n_children)]

            jobs_provider.append([])
            ids = []
            for j, new_job in enumerate(new_jobs):
                assert new_job < len(
                    job_specs
                ), 'jobs_provider data entry {}, offset {} out of range (max: {})'.format(
                    i, j, len(job_specs))  # noqa
                jobs_provider[-1].append(job_specs[new_job])
                ids.append(new_job)

            logger.info("{}: {}".format(i, ids))

        jobs = iter(jobs_provider)

        # if job_id_to_kill:
        #     assert process_agent.get_job_by_id(job_id_to_kill).state in [
        #         State.CANCELLING.value, State.CANCELLED.value
        #     ], "This job {} should be cancelled or in cancelling state".format(
        #         job_id_to_kill)  # noqa

    except Exception as e:
        logger.exception(e)


init(Env())
