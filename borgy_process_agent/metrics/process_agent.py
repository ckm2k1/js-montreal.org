# Copyright 2019 ElementAI. All rights reserved.
#
# Process agent state metrics.

from datetime import timedelta

import dateutil.parser
from prometheus_client import Gauge, Info
from borgy_process_agent_api_server.models.job_runs import JobRuns

from borgy_process_agent import ProcessAgent
from borgy_process_agent.job import State
from borgy_process_agent.utils import get_now
from borgy_process_agent.controllers.version_controller import borgy_process_agent_version


borgy_process_agent = Info(
    'borgy_process_agent',
    'Process agent info')

borgy_process_agent_created_timestamp_seconds = Gauge(
    'borgy_process_agent_created_timestamp_seconds',
    'Timestamp when the agent was created')

borgy_process_agent_ready = Gauge(
    'borgy_process_agent_ready',
    'Is the agent ready?')

borgy_process_agent_shutdown = Gauge(
    'borgy_process_agent_shutdown',
    'Is the agent shutdown?')

borgy_process_agent_last_update_timestamp_seconds = Gauge(
    'borgy_process_agent_last_update_timestamp_seconds',
    'Timestamp of last trial update seen')

borgy_process_agent_jobs_in_creation = Gauge(
    'borgy_process_agent_jobs_in_creation',
    'Jobs in creation by the process agent and waiting for a return from the governor')

borgy_process_agent_jobs = Gauge(
    'borgy_process_agent_jobs',
    'Jobs launched by the agent summed by state',
    ['state'])

borgy_process_agent_jobs_duration_seconds = Gauge(
    'borgy_process_agent_jobs_duration_seconds',
    'The aggregated duration (runtime) of all jobs',
    ['state'])


def collect_process_agent_metrics(pa: ProcessAgent, get_now_fn=None):
    borgy_process_agent.info({
        'version': borgy_process_agent_version,
    })
    borgy_process_agent_created_timestamp_seconds.set_to_current_time()

    if get_now_fn is None:
        get_now_fn = get_now

    def callback(event):
        jobs_update_callback(event, get_now_fn)

    pa.subscribe_jobs_update(callback=callback)


# FIXME: iterate over all process_agents and label by agent job ID?
def jobs_update_callback(event, get_now):
    """
    Update metrics by inspecting the agent state.
    """
    borgy_process_agent_last_update_timestamp_seconds.set_to_current_time()

    borgy_process_agent_ready.set(1 if event.pa.is_ready() else 0)
    borgy_process_agent_shutdown.set(1 if event.pa.is_shutdown() else 0)

    jobs_in_creation = event.pa.get_jobs_in_creation()
    borgy_process_agent_jobs_in_creation.set(len(jobs_in_creation))

    jobs = event.pa.get_jobs().values()
    now = get_now()

    count_by_state = {state.name: 0 for state in State}
    duration_by_state = {state.name: timedelta(0) for state in State}
    for job in jobs:
        count_by_state[job.state] += 1
        for run in job.runs:
            duration_by_state[run.state] += job_run_duration(run, now)

    for state in State:
        count = count_by_state[state.name]
        borgy_process_agent_jobs.labels(state=state.name).set(count)

        duration = duration_by_state[state.name].total_seconds()
        borgy_process_agent_jobs_duration_seconds.labels(state=state.name).set(duration)


def job_run_duration(run: JobRuns, now) -> timedelta:
    """
    Calculate the duration of the job run taking into account missing
    start and end dates.
    """
    if run.started_on is None:
        return timedelta(0)

    started = dateutil.parser.isoparse(run.started_on)
    if run.ended_on is None:
        return now - started

    ended = dateutil.parser.isoparse(run.ended_on)
    return ended - started
