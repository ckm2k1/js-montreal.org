from enum import Enum


class ActionType(Enum):
    create = 'create'
    update = 'update'
    shutdown = 'shutdown'


class Restart(Enum):
    NO = 'no'
    ON_INTERRUPTION = 'on-interruption'


class State(Enum):
    # The NEW state is unique to the process
    # agent and does not exist on the ork
    # side.
    PENDING = 'PENDING'
    SUBMITTED = 'SUBMITTED'
    QUEUING = 'QUEUING'
    QUEUED = 'QUEUED'
    RUNNING = 'RUNNING'
    CANCELLING = 'CANCELLING'
    CANCELLED = 'CANCELLED'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'
    INTERRUPTED = 'INTERRUPTED'
    # This state is reserved for jobs
    # that were killed before ever being
    # acknowledged by the governor.
    KILLED = 'KILLED'

    def is_finished(self):
        return self in [self.CANCELLED, self.FAILED, self.SUCCEEDED, self.KILLED]

    def is_acked(self):
        return self in [self.QUEUED, self.QUEUING, self.RUNNING, self.CANCELLING]

    def is_failed(self):
        return self in [self.QUEUED, self.QUEUING, self.RUNNING, self.CANCELLING]
