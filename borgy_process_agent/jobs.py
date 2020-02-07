from pprint import pformat
from typing import Optional, List, Mapping, Set, MutableMapping

from borgy_process_agent_api_server.models import Job as OrkJob, JobSpec  # type: ignore

from borgy_process_agent.job import Job
from borgy_process_agent.enums import State
from borgy_process_agent.utils import Indexer, DeepChainMap, taketimes

JobMap = MutableMapping[int, Job]
JobIndex = int

# ----------- DO NOT CHANGE ------------
# We can never submit more than 100 jobs
# at the same to the Governor or we'll
# be killed. This constant is completely
# invariant.
MAX_SUBMIT: int = 100
# Maximum number of jobs to allow running
# in parallel in the cluster. The default
# value is quite high and should be usable
# for most users, but can be increased
# (or decreased) via the --max-running flag
# to the cli.
DEFAULT_MAX_RUNNING: int = 500


class Jobs:

    def __init__(self,
                 user: str,
                 pa_id: str,
                 job_name_prefix='pa_child_job',
                 auto_rerun=True,
                 max_running=None):
        # String user id, could be unix name or
        # a UUID in some toolkit scenarios.
        self._user: str = user
        # The UUID of the process agent job.
        self._pa_id: str = pa_id
        # Maximum amount of jobs to submit in one batch.
        self._max_running: Optional[int] = (max_running
                                            if max_running is not None else DEFAULT_MAX_RUNNING)

        # Sequential job index, always increasing.
        self._idx: Indexer = Indexer()
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
        self._pending_jobs: JobMap = {}
        # Jobs that have been acked but have not finished running.
        self._acked_jobs: JobMap = {}
        # Jobs that finished their run for either of the
        # following reasons: success, failure, interrupted, cancelled.
        self._finished_jobs: JobMap = {}
        # Jobs that should be killed on the next
        # round of job creation.
        self._kill_jobs: Set[JobIndex] = set()
        # If auto_rerun is set, this will contain rerunable jobs.
        self._rerun_jobs: Set[JobIndex] = set()
        # ChainMap that allows access to jobs via their index.
        self._all_jobs = DeepChainMap(self._pending_jobs, self._acked_jobs, self._finished_jobs)

    def get_pending(self) -> List[Job]:
        return [j for j in self._pending_jobs.values() if j.is_pending()]

    def get_submitted(self) -> List[Job]:
        return [j for j in self._pending_jobs.values() if j.is_submitted()]

    def get_failed(self):
        return [j for j in self._finished_jobs.values() if j.is_failed()]

    def get_acked(self) -> List[Job]:
        return list(self._acked_jobs.values())

    def get_finished(self) -> List[Job]:
        return list(self._finished_jobs.values())

    def get_kill(self) -> List[Job]:
        return [self._all_jobs[i] for i in self._kill_jobs]

    def get_rerun(self) -> List[Job]:
        return [self._all_jobs[i] for i in self._rerun_jobs]

    def get_by_state(self, state: State) -> List[Job]:
        return [j for j in self._all_jobs.values() if j.state == state]

    def get_all(self) -> List[Job]:
        return list(self._all_jobs.values())

    def get_by_index(self, idx) -> Optional[Job]:
        return self._all_jobs.get(idx)

    def has_pending(self) -> bool:
        return bool(self._pending_jobs)

    def submit_reruns(self) -> List[Job]:
        return self.get_rerun()

    def submit_kills(self) -> List[Job]:
        return self.get_kill()

    def submit_pending(self, count: Optional[int] = None):
        submitted = len(self.get_submitted())
        running = len(self.get_acked())
        room_for_running_jobs = max(self._max_running, running) - running

        # Restrict the submission slice by 'count' if needed.
        if count is not None and count < room_for_running_jobs:
            room_for_running_jobs = count

        # If we have more room for running jobs than jobs to submit,
        # fill up the submission queue from pending jobs.
        if submitted < room_for_running_jobs:
            backfill = room_for_running_jobs - submitted
            for _, p in taketimes(self.get_pending(), times=min(backfill, MAX_SUBMIT)):
                p.submit()

        return [s for _, s in taketimes(self.get_submitted(), times=room_for_running_jobs)]

    def kill_job(self, job: Job):
        if job.is_finished():
            return
        # Pending jobs go straight to finished
        if job.is_pending():
            # The .kill() is unique to pending jobs
            # because they never had a state from the
            # governor so we give them an internal PA
            # state. This is handy in the UI for the user
            # to see that a pending job was kill'd before
            # ever running.
            job.kill()
            self._finished_jobs[job.index] = self._all_jobs.pop(job.index)
            return

        self._kill_jobs.add(job.index)

    def rerun_job(self, job: Job):
        # Doesn't make sense to rerun something
        # that hasn't finished yet.
        if not (job.is_finished() or job.is_interrupted()):
            return
        self._rerun_jobs.add(job.index)

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
        stats = self.get_stats()
        stats['pending'] = len(stats['pending'])
        stats['submitted'] = len(stats['submitted'])
        stats['acked'] = len(stats['acked'])
        stats['succeeded'] = len(stats['succeeded'])
        stats['failed'] = len(stats['failed'])
        stats['cancelled'] = len(stats['cancelled'])
        stats['total'] = (stats['submitted'] + stats['acked'] + stats['succeeded'] +
                          stats['failed'] + stats['cancelled'])
        return stats

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
            if job.index in self._all_jobs:
                continue
            else:
                self._pending_jobs[job.index] = job

    def _update_job(self, oj: OrkJob) -> Job:
        index: int = Job.get_index(oj)
        job: Optional[Job] = self._all_jobs.get(index)

        # The PA was restarted most likely (or governor) and we're
        # receiving updates for running jobs that are running in
        # the cluster but don't exist in our internal state yet.
        if job is None:
            job = Job(index,
                      self._user,
                      self._pa_id,
                      jid=oj.id,
                      name_prefix=self._job_name_prefix,
                      spec=Job.spec_from_ork_job(oj))
            self._acked_jobs[index] = job

        job.update_from_ork(oj)
        if job.has_changed('state'):
            self._all_jobs.pop(index)

            # Getting an update for a rerun job
            # means the gov is dealing with it
            # and we don't have to resubmit it.
            if index in self._rerun_jobs:
                self._rerun_jobs.remove(index)

            if job.is_acked():
                self._acked_jobs[index] = job

            elif job.is_interrupted():
                if self._auto_rerun:
                    self.rerun_job(job)
                    self._acked_jobs[index] = job
                else:
                    self._finished_jobs[index] = job

            elif job.is_finished():  # pragma: no branch
                self._finished_jobs[index] = job

        # Updates for kill jobs with any acked or finished
        # states can be safely removed from the kill queue.
        if index in self._kill_jobs and (job.is_finished() or job.is_acked()):
            self._kill_jobs.remove(index)

        return job

    def update(self, jobs: List[Mapping]) -> List[Job]:
        updated = []
        for oj in jobs:
            job = self._update_job(OrkJob.from_dict(oj))
            # Is there no case where we don't have diff?
            # It's likely because why send updates for something
            # that didn't change?
            if job.diff:  # pragma: no branch
                updated.append(job)

        return updated

    def all_done(self) -> bool:
        no_more = not self.has_more()
        no_rerun = not self.get_rerun()
        no_kill = not self.get_kill()
        all_done = len(self._finished_jobs) == len(self._all_jobs)
        return no_more and no_rerun and no_kill and all_done

    def has_more(self):
        return self._has_more_new_jobs

    def __repr__(self):
        return pformat(self.get_counts(), indent=4)
