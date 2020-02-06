from datetime import timedelta
from typing import Callable
from unittest.mock import patch, MagicMock

import pytest

from borgy_process_agent_api_server.models import JobSpec, JobsOps, HealthCheck
from borgy_process_agent.enums import State
from borgy_process_agent.runners.docker_gov import DockerGovernor
from borgy_process_agent.utils import ObjDict, parse_iso_datetime

from tests.utils import DockerIter, DockerStatus


def make_ops(submit=None, rerun=None, kill=None, submit_parallel=False):
    submit = submit or []
    rerun = rerun or []
    kill = kill or []
    return JobsOps(submit_parallel=submit_parallel, submit=submit, rerun=rerun, kill=kill)


def mock_from_env():
    dockeriter = DockerIter([])
    mm = MagicMock(wraps=dockeriter)
    mm.__iter__ = dockeriter.__iter__
    return ObjDict({'containers': mm})


class MockJobsApi:

    def __init__(self, *args, **kwargs):
        pass

    def v1_jobs_get_with_http_info(self, *args, **kwargs):
        pass

    def v1_jobs_put(self, *args, **kwargs):
        pass


class TestDockerGov:

    @patch('borgy_process_agent_api_client.JobsApi', spec_new=MockJobsApi)
    @patch('borgy_process_agent.runners.docker_gov.docker.from_env', wraps=mock_from_env)
    def test_basic_path(self, envmock, jobsmock, fixture_loader: Callable):
        specs_json = fixture_loader('specs.json')

        gov = DockerGovernor()
        specs = [JobSpec.from_dict(spec) for spec in specs_json['submit']]

        gov._jobs_api.v1_jobs_get_with_http_info.side_effect = [
            (make_ops(submit=specs), 200, {}),
            (make_ops(), 200, {}),
            (make_ops(), 200, {}),
        ]
        gov._jobs_api.v1_jobs_put.return_value = None
        gov._running = True
        gov._run_iteration()
        assert len(gov._governor_jobs) == 5

        for _, desc in gov._governor_jobs.items():
            job = desc['job']
            assert job.state == State.RUNNING.value
            assert len(job.runs) == 1
            assert job.runs[-1].started_on == desc['container'].get_state('StartedAt')

        # No change iteration.
        gov._run_iteration()

        for cont in gov._docker.containers.list():
            cont.terminate()

        gov._run_iteration()
        assert len(gov._governor_jobs) == 5
        for desc in gov._governor_jobs.values():
            job = desc['job']
            assert job.state == State.SUCCEEDED.value
            assert len(job.runs) == 1
            assert job.runs[-1].ended_on == desc['container'].get_state('FinishedAt')

        gov.stop()
        assert not gov._running

    @patch('borgy_process_agent_api_client.JobsApi', spec_new=MockJobsApi)
    @patch('borgy_process_agent.runners.docker_gov.docker.from_env', wraps=mock_from_env)
    def test_failed_jobs(self, envmock, jobsmock, fixture_loader: Callable):
        specs_json = fixture_loader('specs.json')
        gov = DockerGovernor()
        specs = [JobSpec.from_dict(spec) for spec in specs_json['submit']]
        gov._jobs_api.v1_jobs_get_with_http_info.side_effect = [
            (make_ops(submit=specs), 200, {}),
            (make_ops(), 200, {}),
        ]
        gov._jobs_api.v1_jobs_put.return_value = None
        gov._running = True
        gov._run_iteration()

        assert len(gov._governor_jobs) == 5
        for _, desc in gov._governor_jobs.items():
            job = desc['job']
            assert job.state == State.RUNNING.value

        conts = gov._docker.containers.list()
        fail_conts = conts[:2]
        for c in fail_conts:
            c.fail(exit_code=1)
        for cont in conts[2:]:
            cont.terminate()

        gov._run_iteration()
        assert len(gov._governor_jobs) == 5
        for desc in gov._governor_jobs.values():
            job = desc['job']
            if desc['container'] in fail_conts:
                assert job.state == State.FAILED.value
            else:
                assert job.state == State.SUCCEEDED.value
            assert len(job.runs) == 1
            assert job.runs[-1].ended_on == desc['container'].get_state('FinishedAt')

    @patch('borgy_process_agent_api_client.JobsApi', spec_new=MockJobsApi)
    @patch('borgy_process_agent.runners.docker_gov.docker.from_env', wraps=mock_from_env)
    def test_kill_job(self, envmock, jobsmock, fixture_loader: Callable):
        specs_json = fixture_loader('specs.json')

        gov = DockerGovernor()
        specs = [JobSpec.from_dict(spec) for spec in specs_json['submit']]

        gov._jobs_api.v1_jobs_get_with_http_info.side_effect = [(make_ops(submit=specs), 200, {})]
        gov._jobs_api.v1_jobs_put.return_value = None
        gov._running = True
        gov._run_iteration()
        assert len(gov._governor_jobs) == 5
        for _, desc in gov._governor_jobs.items():
            job = desc['job']
            assert job.state == State.RUNNING.value

        kill_jid = list(gov._governor_jobs.keys())[0]
        res = [(make_ops(kill=[kill_jid]), 200, {}), (make_ops(), 200, {})]
        gov._jobs_api.v1_jobs_get_with_http_info.reset_mock(side_effect=True)
        gov._jobs_api.v1_jobs_get_with_http_info.side_effect = res

        gov._run_iteration()

        dead_job = gov._governor_jobs[kill_jid]['job']
        dead_cont = gov._governor_jobs[kill_jid]['container']
        assert dead_job.state == State.CANCELLED.value
        assert dead_job.runs[-1].cancelled_on == dead_cont.get_state('FinishedAt')
        assert dead_job.runs[-1].ended_on == dead_cont.get_state('FinishedAt')
        assert dead_cont.get_state('Status') == DockerStatus.exited.value
        assert dead_cont._stopped is True

        for cont in gov._docker.containers.list():
            cont.terminate()

        gov._run_iteration()
        assert len(gov._governor_jobs) == 5
        for jid, desc in gov._governor_jobs.items():
            job = desc['job']
            if jid == kill_jid:
                assert job.state == State.CANCELLED.value
            else:
                assert job.state == State.SUCCEEDED.value
            assert len(job.runs) == 1
            assert job.runs[-1].ended_on == desc['container'].get_state('FinishedAt')

    @patch('borgy_process_agent_api_client.JobsApi', spec_new=MockJobsApi)
    @patch('borgy_process_agent.runners.docker_gov.docker.from_env', wraps=mock_from_env)
    def test_rerun_job(self, envmock, jobsmock, fixture_loader: Callable):
        specs_json = fixture_loader('specs.json')
        gov = DockerGovernor()
        specs = [JobSpec.from_dict(spec) for spec in specs_json['submit']]

        gov._jobs_api.v1_jobs_get_with_http_info.side_effect = [
            (make_ops(submit=specs), 200, {}),
            (make_ops(), 200, {}),
            (make_ops(), 200, {}),
        ]
        gov._jobs_api.v1_jobs_put.return_value = None
        gov._running = True
        gov._run_iteration()
        assert len(gov._governor_jobs) == 5
        for _, desc in gov._governor_jobs.items():
            job = desc['job']
            assert job.state == State.RUNNING.value

        kill_jid = list(gov._governor_jobs.keys())[0]
        res = [(make_ops(kill=[kill_jid]), 200, {}), (make_ops(), 200, {})]
        gov._jobs_api.v1_jobs_get_with_http_info.reset_mock(side_effect=True)
        gov._jobs_api.v1_jobs_get_with_http_info.side_effect = res

        gov._run_iteration()

        dead_job = gov._governor_jobs[kill_jid]['job']
        dead_cont = gov._governor_jobs[kill_jid]['container']
        assert dead_job.state == State.CANCELLED.value
        assert dead_job.runs[-1].cancelled_on == dead_cont.get_state('FinishedAt')
        assert dead_job.runs[-1].ended_on == dead_cont.get_state('FinishedAt')
        assert dead_cont.get_state('Status') == DockerStatus.exited.value
        assert dead_cont._stopped is True

        for cont in gov._docker.containers.list():
            cont.terminate()

        gov._run_iteration()
        assert len(gov._governor_jobs) == 5
        for jid, desc in gov._governor_jobs.items():
            job = desc['job']
            if jid == kill_jid:
                assert job.state == State.CANCELLED.value
            else:
                assert job.state == State.SUCCEEDED.value
            assert len(job.runs) == 1
            assert job.runs[-1].ended_on == desc['container'].get_state('FinishedAt')

    @patch('borgy_process_agent_api_client.JobsApi', spec_new=MockJobsApi)
    @patch('borgy_process_agent.runners.docker_gov.docker.from_env', wraps=mock_from_env)
    def test_max_runtime_exceeded(self, envmock, jobsmock, fixture_loader: Callable):
        specs_json = fixture_loader('specs.json')
        gov = DockerGovernor()
        specs = [JobSpec.from_dict(spec) for spec in specs_json['submit']]

        gov._jobs_api.v1_jobs_get_with_http_info.side_effect = [
            (make_ops(submit=specs), 200, {}),
            (make_ops(), 200, {}),
            (make_ops(), 200, {}),
        ]
        gov._jobs_api.v1_jobs_put.return_value = None
        gov._running = True
        gov._run_iteration()
        assert len(gov._governor_jobs) == 5
        for _, desc in gov._governor_jobs.items():
            job = desc['job']
            assert job.state == State.RUNNING.value

        timed_out = list(gov._governor_jobs.values())[0]
        crun = timed_out['job'].runs[-1]
        # Move the jobs started date back 110secs. The fixtures
        # have max_run_time_secs set to 100 which should timeout
        # the job.
        crun.started_on = (parse_iso_datetime(crun.started_on) -
                           timedelta(seconds=110)).isoformat()

        gov._run_iteration()
        assert not timed_out['container'].get_state('Running')
        assert timed_out['container']._stopped
        assert timed_out['container'].get_state('FinishedAt') is not None

        for cont in gov._docker.containers.list():
            cont.terminate()

        gov._run_iteration()
        assert len(gov._governor_jobs) == 5
        for jid, desc in gov._governor_jobs.items():
            job = desc['job']
            if job == timed_out['job']:
                assert job.state == State.FAILED.value
            else:
                assert job.state == State.SUCCEEDED.value
            assert len(job.runs) == 1
            assert job.runs[-1].ended_on == desc['container'].get_state('FinishedAt')

    @patch('time.sleep', return_value=0)
    @patch('borgy_process_agent.runners.docker_gov.docker.from_env', wraps=mock_from_env)
    def test_wait_ready(self, envmock, sleepmock):
        gov = DockerGovernor()
        gov._running = True
        with patch.object(gov._health_api,
                          'v1_health_get',
                          side_effect=[
                              HealthCheck(is_ready=False),
                              HealthCheck(is_ready=False),
                              HealthCheck(is_ready=False),
                              HealthCheck(is_ready=True),
                          ]) as health:
            gov._wait_till_ready()
            assert gov._health_api.v1_health_get.call_count == 4

            # Complete fail the ready check
            health.reset_mock(side_effect=True)
            health.side_effect = [HealthCheck(is_ready=False) for i in range(21)]
            with pytest.raises(TimeoutError, match='PA was not ready after 20 attempts.'):
                gov._wait_till_ready()

            # health throws exception.
            health.reset_mock(side_effect=True)
            health.side_effect = [
                Exception('oh noes'),
                Exception('still no'),
                HealthCheck(is_ready=False),
                HealthCheck(is_ready=True)
            ]
            with pytest.raises(TimeoutError, match='PA was not ready after 3 attempts.'):
                gov._wait_till_ready(attempts=3)
            assert gov._health_api.v1_health_get.call_count == 3
