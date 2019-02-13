from borgy_process_agent import ProcessAgent, ProcessAgentMode
import json
import logging
import os

logging.basicConfig(datefmt='%Y-%m-%d %H:%M:%S',
                    format=('%(asctime)s.%(msecs)03d %(name)15s '
                            '[%(levelname)s] %(message)s'))

logger = logging.getLogger("main")
logger.setLevel(logging.INFO)


def main():
    try:
        iteration_max = int(os.getenv('PA_TESTER_ITERATION', '30'))
        iteration = 0

        n_children = int(os.getenv('PA_TESTER_CHILDREN', '0'))

        def get_json(name, default_value, types):
            json_str = os.getenv(name, default_value)
            try:
                data = json.loads(json_str)
            except Exception:
                assert False, '{} should be valid JSON. Was:\n{}'.format(name, json_str)
            assert type(data) in types, "name {} must be in [{}]".format(name, types)
            return data

        # content of PA_TESTER_JOBS must be a single job_spec (dict) or a list of job_specs
        job_specs = get_json('PA_TESTER_JOBS',
                             '{"reqCores": "1", "reqGpus": "0", "image": "ubuntu:18.04", "command": ["sleep", "60"]}',
                             [type(dict()), type(list())])

        if isinstance(job_specs, dict):
            job_specs = [job_specs]

        logger.info("Job Specs:")
        for i, job_spec in enumerate(job_specs):
            assert isinstance(job_spec, dict), 'job_specs entry {} should be a dict. Was {}'.format(i, type(job_spec))
            logger.info("{}: {}".format(i, job_spec))

        # content of PA_TESTER_JOBS must be a list of job_specs
        jobs_provider_data = get_json('PA_TESTER_JOBS_PROVIDER',
                                      '[]',
                                      [type(list())])

        jobs_provider = []

        # XOR - only one of the two must be set
        assert (n_children > 0) != (len(jobs_provider_data) > 0), "One and only one of PA_TESTER_CHILDREN or PA_TESTER_JOBS_PROVIDER must be set"  # noqa

        if n_children:
            jobs_provider_data = [[0 for i in range(n_children)]]

        logger.info("Jobs Provider returns:")
        for i, new_jobs in enumerate(jobs_provider_data):
            assert isinstance(new_jobs, list), 'new_jobs entry {} should be a list. Was {}'.format(i, type(new_jobs))

            if i == 1 and len(new_jobs) == 0:
                new_jobs = [0 for i in range(n_children)]

            jobs_provider.append([])
            ids = []
            for j, new_job in enumerate(new_jobs):
                assert new_job < len(job_specs), 'jobs_provider data entry {}, offset {} out of range (max: {})'.format(i, j, len(job_specs))  # noqa
                jobs_provider[-1].append(job_specs[new_job])
                ids.append(new_job)

            logger.info("{}: {}".format(i, ids))

        jobs_provider_iter = iter(jobs_provider)

        def return_new_jobs(pa=None):
            nonlocal iteration, iteration_max
            iteration += 1

            if iteration == iteration_max:
                return None

            try:
                rc = next(jobs_provider_iter)
                logger.info("{}: job request - Returning {} jobs".format(iteration, len(rc)))
                return rc
            except StopIteration:
                logger.info("{}: job request - Done".format(iteration))
            except Exception as e:
                logger.info("{}: job request - Unhandled exception".format(iteration))
                logger.exception(e)
            return None

        def jobs_update(event):
            nonlocal iteration
            iteration += 1

            logger.info("{}: job update".format(iteration))
            for job in event['jobs']:
                logger.info("{}: {} {}".format(iteration, job['job'].id, job['job'].state))

        process_agent = ProcessAgent(mode=ProcessAgentMode.AUTO)
        process_agent.set_callback_jobs_provider(return_new_jobs)
        process_agent.subscribe_jobs_update(jobs_update)
        logger.info("Starting")
        process_agent.start()

    except Exception as e:
        logger.exception(e)


main()
