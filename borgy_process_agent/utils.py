#
# utils.py
# Sylvain Witmeyer, 2017-08-07
# Mich, 2017-10-23
# Copyright 2017 ElementAI. All rights reserved.
#
from datetime import datetime
from dateutil.tz import tzutc


def get_now():
    """Facilitates testing."""
    return datetime.now(tzutc())


def get_now_isoformat():
    """Facilitates testing."""
    return get_now().isoformat()
