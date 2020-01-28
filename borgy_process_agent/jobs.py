from typing import Optional, List, Mapping, Any

from borgy_process_agent_api_server.models import Job as OrkJob, JobSpec

from borgy_process_agent.job import Job
from borgy_process_agent.enums import State
from borgy_process_agent.utils import Indexer, DeepChainMap


class Jobs:

    def __init__(self, user: str, pa_id: str, job_name_prefix='pa_child_job', auto_rerun=True):
        self._user = user
        self._pa_id = pa_id

        # Sequential job index, always increasing.
        self._idx = Indexer()
        # New jobs that haven't been submitted to
        # governor yet.
        self.pending_jobs = {}
        # Jobs that have been submitted to the governor
        # but have not yet received an update. We
        # are not aware of their state and wether the
        # governor was able to schedule them at all.
        self.submitted_jobs = {}
        # Jobs that have been acknowledged (at least one udpate)
        # and are being treated by the governor.
        self.acked_jobs = {}
        # Jobs that finished their run for either of the
        # following reasons: success, failure, interrupted, cancelled.
        self.finished_jobs = {}
        # Jobs that should be killed on the next
        # round of job creation.
        self.kill_jobs = {}
        # If auto_rerun is set, this will contain rerunable jobs.
        self.rerun_jobs = {}
        # ChainMap that allows access to jobs via their index.
        self.all_jobs = DeepChainMap(self.submitted_jobs, self.rerun_jobs, self.acked_jobs,
                                     self.kill_jobs, self.finished_jobs)
        # Child jobs will be prefixed with this string.
        self._job_name_prefix = job_name_prefix
        # If true, PA will automatically resubmit INTERRUPTED
        # jobs to the governor.
        self._auto_rerun = auto_rerun
        # No new jobs will be generated by
        # user code. Once everything running
        # completes, done will be set.
        self._no_new = False

    def get_stats(self):
        obj = {
            'pending': [j.to_dict() for j in self.pending_jobs.values()],
            'submitted': [j.to_dict() for j in self.submitted_jobs.values()],
            'acked': [j.to_dict() for j in self.acked_jobs.values()],
            'succeeded': [j.to_dict() for j in self.get_by_state(State.SUCCEEDED)],
            'failed': [j.to_dict() for j in self.get_by_state(State.FAILED)],
            'cancelled': [j.to_dict() for j in self.get_by_state(State.CANCELLED)()]
        }

        return obj

    def get_counts(self):
        obj = {
            'pending': len(self.pending_jobs),
            'submitted': len(self.submitted_jobs),
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
            self._no_new = True
            return

        for j in new_jobs:
            job = Job(self._idx.next(),
                      self._user,
                      pa_id=self._pa_id,
                      spec=j,
                      name_prefix=self._job_name_prefix)
            self.pending_jobs[job.index] = job

    def _transfer_between_queues(self, src, dest, count=None) -> List[Job]:
        jobs = []
        src = getattr(self, src)
        dest = getattr(self, dest)
        count = len(src) if count is None else count
        while src and count:
            index, job = src.popitem()
            jobs.append(job)
            dest[index] = job
            count -= 1
        return jobs

    def kill_job(self, job: Job):
        if not job.jid:
            return
        self.kill_jobs[job.index] = self.all_jobs.pop(job.index)

    def get_by_type(self, type: str) -> List[Job]:
        return [j.copy() for j in getattr(self, f'{type}_jobs').values()]

    def get_by_state(self, state) -> List[Job]:
        return [j for j in self.all_jobs.values() if j.state == state]

    def has_pending(self) -> bool:
        return bool(self.pending_jobs)

    def submit_jobs_to_rerun(self) -> List[Job]:
        return self._transfer_between_queues('rerun_jobs', 'acked_jobs')

    def submit_jobs_to_kill(self) -> List[Job]:
        return self._transfer_between_queues('kill_jobs', 'acked_jobs')

    def submit_pending(self, count=100) -> List[Job]:
        count = 100 if count > 100 or count is None else count
        return self._transfer_between_queues('pending_jobs', 'submitted_jobs', count=count)

    def _update_job(self, oj: OrkJob) -> Job:
        index: int = Job.get_index(oj)
        job: Optional[Job] = self.all_jobs.get(index)

        # The PA was restarted most likely (or governor) and we're
        # receiving updates for running jobs that are running in
        # the cluster but don't exist in our internal state yet.
        if job is None:
            job = Job.from_ork_job(index,
                                   self._user,
                                   self._pa_id,
                                   jid=oj.id,
                                   name_prefix=self._job_name_prefix,
                                   ork_job=oj)
            self.submitted_jobs[index] = job

        job.update_from_ork(oj)
        if job.has_changed('state'):
            self.all_jobs.pop(index)

            if job.state in [State.RUNNING, State.QUEUING, State.QUEUED, State.CANCELLING]:
                self.acked_jobs[index] = job

            elif job.state == State.INTERRUPTED:
                if self._auto_rerun:
                    self.rerun_jobs.add(job.jid)
                    self.acked_jobs[index] = job
                else:
                    self.finished_jobs[index] = job

            elif job.state in [State.CANCELLED, State.FAILED, State.SUCCEEDED]:
                self.finished_jobs[index] = job

        return job

    def all_done(self):
        return self._no_new and not (self.pending_jobs or self.submitted_jobs or self.acked_jobs
                                     or self.kill_jobs or self.rerun_jobs)

    def update_jobs(self, jobs: List[OrkJob]) -> List[Mapping[str, Any]]:
        updated = []
        for oj in jobs:
            job = self._update_job(OrkJob.from_dict(oj))
            if job.diff:
                updated.append({'job': job.to_dict(), 'update': job.diff})

        return updated
