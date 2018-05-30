# -*- coding: utf-8 -*-
#
# job.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from enum import Enum


class Restart(Enum):
    NO = 'no'
    ON_INTERRUPTION = 'on-interruption'


class State(Enum):
    QUEUING = 'QUEUING'
    QUEUED = 'QUEUED'
    RUNNING = 'RUNNING'
    CANCELLING = 'CANCELLING'
    CANCELLED = 'CANCELLED'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'
    INTERRUPTED = 'INTERRUPTED'
