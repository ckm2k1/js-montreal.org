# -*- coding: utf-8 -*-
#
# jobs_controller.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#


import connexion
from borgy_process_agent import process_agents
from borgy_process_agent.exceptions import NotReadyError, EnvironmentVarError
from borgy_process_agent_api_server.models.job import Job


def v1_jobs_get():
    """Get jobs to create, rerun or kill

    :rtype: JobsOps
    """
    try:
        jobs = []
        jobs_rerun = []
        pa_state = []
        for pa in process_agents:
            jobs_rerun += pa.get_jobs_to_rerun()
            try:
                j = pa.get_job_to_create()
            except NotReadyError:
                return 'Process Agent is not ready yet ! Take a tea break.', 418
            except (EnvironmentVarError, TypeError, ValueError) as e:
                for p in process_agents:
                    p.stop(error=e)  # noqa F821
                raise e

            if j is None:
                pa_state.append(None)
                continue

            pa_state.append(True)
            jobs += j

        return {
            'submit': jobs,
            'rerun': jobs_rerun,
            'kill': [],
        }
    except Exception as e:
        print('|'+str(e)+'|')
        return str(e), 500


def v1_jobs_put(body):
    """Update job with current state

    :param body:
    :type body: list | bytes

    :rtype: str
    """
    input_jobs = connexion.request.get_json()
    if not all(isinstance(j, dict) for j in input_jobs):
        return 'Bad format: List[Job] needed', 400
    for pa in process_agents:
        pa._push_jobs([Job.from_dict(j) for j in input_jobs])

    return 'Do some magic and licorns!'


def v1_status_get():
    """Return status of jobs owned by process agent

    :rtype: List[Job]
    """
    jobs = []
    for pa in process_agents:
        jobs += pa.get_jobs().values()

    return jobs
