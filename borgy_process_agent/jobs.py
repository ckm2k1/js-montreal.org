from typing import Optional, List, Mapping, Any, Set

from borgy_process_agent_api_server.models import Job as OrkJob, JobSpec

from borgy_process_agent.job import Job
from borgy_process_agent.enums import State
from borgy_process_agent.utils import Indexer, DeepChainMap, taketimes

JobMap = Mapping[int, Job]
JobIndex = int


class Jobs:

    def __init__(self, user: str, pa_id: str, job_name_prefix='pa_child_job', auto_rerun=True):
        self._user = user
        self._pa_id = pa_id

        # Sequential job index, always increasing.
        self._idx = Indexer()
        # Child jobs will be prefixed with this string.
        self._job_name_prefix: str = job_name_prefix
        # If true, PA will automatically resubmit INTERRUPTED
        # jobs to the governor.
        self._auto_rerun: bool = auto_rerun
        # No new jobs will be generated by
        # user code. Once everything running
        # completes, done will be set.
        self._has_more_new_jobs: bool = True

        # New jobs and jobs that have been submitted to the governor
        # but have not yet been acknoledged by the governor.
        self.pending_jobs: JobMap = {}
        # Jobs that have been acked but have not finished running.
        self.acked_jobs: JobMap = {}
        # Jobs that finished their run for either of the
        # following reasons: success, failure, interrupted, cancelled.
        self.finished_jobs: JobMap = {}
        # Jobs that should be killed on the next
        # round of job creation.
        self.kill_jobs: Set[JobIndex] = set()
        # If auto_rerun is set, this will contain rerunable jobs.
        self.rerun_jobs: Set[JobIndex] = set()
        # ChainMap that allows access to jobs via their index.
        self.all_jobs = DeepChainMap(self.pending_jobs, self.acked_jobs, self.finished_jobs)

    def get_stats(self):
        obj = {
            'pending': [j.to_dict() for j in self.get_pending()],
            'submitted': [j.to_dict() for j in self.get_submitted()],
            'acked': [j.to_dict() for j in self.get_acked()],
            'succeeded': [j.to_dict() for j in self.get_by_state(State.SUCCEEDED)],
            'failed': [j.to_dict() for j in self.get_by_state(State.FAILED)],
            'cancelled': [j.to_dict() for j in self.get_by_state(State.CANCELLED)],
        }

        return obj

    def get_counts(self):
        obj = {
            'pending': len(self.pending_jobs),
            'submitted': len(self.pending_jobs),
            'acked': len(self.acked_jobs),
            'succeeded': len([j for j in self.get_by_state(State.SUCCEEDED)]),
            'failed': len([j for j in self.get_by_state(State.FAILED)]),
            'cancelled': len([j for j in self.get_by_state(State.CANCELLED)]),
        }
        obj['total'] = obj['submitted'] + obj['acked'] + obj['succeeded'] + obj['failed'] + obj[
            'cancelled']
        return obj

    def create(self, new_jobs: Optional[List[JobSpec]]):
        if new_jobs is None:
            self._has_more_new_jobs = False
            return

        for j in new_jobs:
            job = Job(self._idx.next(),
                      self._user,
                      pa_id=self._pa_id,
                      spec=j,
                      name_prefix=self._job_name_prefix)
            self.pending_jobs[job.index] = job

    def kill_job(self, job: Job):
        # Pending jobs go straight to finished
        if job.index in self.pending_jobs:
            job.kill()
            self.finished_jobs[job.index] = self.all_jobs.pop(job.index)
        else:
            self.kill_jobs.add(job.index)

    def rerun_job(self, job: Job):
        self.rerun_jobs.add(job.index)

    def get_pending(self) -> List[Job]:
        return [j for j in self.pending_jobs.values() if j.is_pending()]

    def get_submitted(self) -> List[Job]:
        return [j for j in self.pending_jobs.values() if j.is_submitted()]

    def get_acked(self) -> List[Job]:
        return list(self.acked_jobs.values())

    def get_kill(self) -> List[Job]:
        return [self.all_jobs[i] for i in self.kill_jobs]

    def get_rerun(self) -> List[Job]:
        return [self.all_jobs[i] for i in self.rerun_jobs]

    def get_finished(self) -> List[Job]:
        return list(self.finished_jobs.values())

    def get_by_state(self, state: State) -> List[Job]:
        return [j for j in self.all_jobs.values() if j.state == state]

    def has_pending(self) -> bool:
        return bool(self.pending_jobs)

    def submit_reruns(self) -> List[Job]:
        return [self.all_jobs[idx] for idx in self.rerun_jobs]

    def submit_kills(self) -> List[Job]:
        return [self.all_jobs[idx] for idx in self.kill_jobs]

    def submit_pending(self, count: Optional[int] = None) -> List[Job]:
        count = len(self.pending_jobs) if count is None else count
        to_submit = [v for _, v in taketimes(self.pending_jobs, times=count)]
        for s in to_submit:
            s.submit()
        return to_submit

    def _update_job(self, oj: OrkJob) -> Job:
        index: int = Job.get_index(oj)
        job: Optional[Job] = self.all_jobs.get(index)

        # The PA was restarted most likely (or governor) and we're
        # receiving updates for running jobs that are running in
        # the cluster but don't exist in our internal state yet.
        if job is None:
            job = Job(index,
                      self._user,
                      self._pa_id,
                      jid=oj.id,
                      name_prefix=self._job_name_prefix,
                      ork_job=oj)
            self.acked_jobs[index] = job

        job.update_from_ork(oj)
        if job.has_changed('state'):
            self.all_jobs.pop(index)

            # Getting an update for a rerun job
            # means the gov is dealing with it
            # and we don't have to resubmit it.
            if index in self.rerun_jobs:
                self.rerun_jobs.remove(index)

            if job.is_acked():
                self.acked_jobs[index] = job

            elif job.is_interrupted():
                if self._auto_rerun:
                    self.rerun_job(job)
                    self.acked_jobs[index] = job
                else:
                    self.finished_jobs[index] = job

            elif job.is_finished():
                self.finished_jobs[index] = job

        # Updates for kill jobs with any acked or finished
        # states can be safely removed from the kill queue.
        if index in self.kill_jobs and job.is_finished() is job.is_acked():
            self.kill_jobs.remove(index)

        return job

    def all_done(self) -> bool:
        return not self.has_more() and len(self.finished_jobs) == len(self.all_jobs)

    def has_more(self):
        return self._has_more_new_jobs

    def update_jobs(self, jobs: List[Mapping]) -> List[Mapping[str, Any]]:
        updated = []
        for oj in jobs:
            job = self._update_job(OrkJob.from_dict(oj))
            if job.diff:
                updated.append({'job': job.to_dict(), 'update': job.diff})

        return updated

    def __repr__(self):
        from pprint import pprint
        return pprint(self.get_counts(), indent=4)
