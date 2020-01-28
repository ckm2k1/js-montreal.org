# -*- coding: utf-8 -*-
#
# jobs_controller.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import connexion
import operator
import functools
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
        jobs_kill = []
        pa_state = []
        for pa in process_agents:
            jobs_rerun += pa.get_jobs_to_rerun()
            jobs_kill += pa.get_jobs_to_kill()
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
            'kill': jobs_kill,
        }
    except Exception as e:
        print('|' + str(e) + '|')
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


job_reverse_attribute_map = {}
for k, v in Job().attribute_map.items():
    job_reverse_attribute_map[v] = k


def jobs_multikeysort(jobs, keys):
    comparers = [(operator.attrgetter(key[0]), key[1]) for key in keys]

    def cmp(a, b):
        return (a > b) - (a < b)

    def comparer(left, right):
        for fn, mult in comparers:
            result = cmp(fn(left), fn(right))
            if result:
                return mult * result
        else:
            return 0

    return sorted(jobs, key=functools.cmp_to_key(comparer))


def v1_status_get(offset=None, limit=None, sort=None):  # noqa: E501
    """Return status of jobs owned by process agent

     # noqa: E501

    :param offset: The number of items to skip before starting to collect the result set.
    :type offset: int
    :param limit: The numbers of items to return.
    :type limit: int
    :param sort: Key to sort: key:{asc,desc}. Can accept multiple time the query parameter.
    :type sort: List[str]

    :rtype: List[Job]
    """
    sort_list = []
    if sort:
        for s in sort:
            if s.strip():
                key_order = s.split(":")
                k = key_order[0].strip()
                if k not in job_reverse_attribute_map:
                    return "Bad key: '{}' doesn't exist".format(k), 400
                key = job_reverse_attribute_map[k]
                order = -1 if len(key_order) > 1 and key_order[1].strip() == "desc" else 1
                sort_list.append((key, order))
    else:
        sort_list.append(('created_on', 1))
        sort_list.append(('id', 1))

    jobs = []
    for pa in process_agents:
        jobs += pa.get_jobs().values()

    if sort_list:
        jobs = jobs_multikeysort(jobs, sort_list)

    if not offset:
        offset = 0

    if not limit:
        limit = 100

    end = limit
    # allow to use -1
    if offset > 0 and limit > 0:
        end = offset + limit
    if offset < 0 and limit > 0:
        end = len(jobs) + offset + limit

    return jobs[offset:end]
