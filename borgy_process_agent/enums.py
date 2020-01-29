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
    QUEUING = 'QUEUING'
    QUEUED = 'QUEUED'
    RUNNING = 'RUNNING'
    CANCELLING = 'CANCELLING'
    CANCELLED = 'CANCELLED'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'
    INTERRUPTED = 'INTERRUPTED'

    def is_finished(self, state):
        return state in [self.CANCELLED, self.FAILED, self.SUCCEEDED]

    def is_acked(self, state):
        return state not in [self.PENDING, self.SUBMITTED]
