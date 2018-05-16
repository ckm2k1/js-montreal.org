# -*- coding: utf-8 -*-
#
# jobs_controller.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#


from borgy_process_agent import process_agents
from borgy_process_agent_api_server.models.health_check import HealthCheck


def v1_health_get():
    """Return health check

    :rtype: HealthCheck
    """
    return HealthCheck.from_dict({
        'isReady': all([pa.is_ready() for pa in process_agents])
    })
