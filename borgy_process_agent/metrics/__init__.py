# Copyright 2019 ElementAI. All rights reserved.
#
# Metric entrypoint.

import logging

from prometheus_client import start_http_server

from borgy_process_agent import ProcessAgentMode
from borgy_process_agent.metrics.api import collect_flask_metrics
from borgy_process_agent.metrics.process_agent import collect_process_agent_metrics


logger = logging.getLogger(__name__)


def expose_metrics(pa, port=9080, get_now=None):
    """
    Register collection of metrics for the process agent.

    :rtype: NoReturn
    """
    collect_process_agent_metrics(pa, get_now_fn=get_now)

    if pa.get_mode() == ProcessAgentMode.EAI:
        app = pa.get_app()
        if app is not None:
            collect_flask_metrics(app.app)
        else:
            logger.error("API metrics not available since no Flask is attached")

    start_http_server(port=port)
