# Copyright 2019 ElementAI. All rights reserved.
#
# Process agent API metrics collection.

import flask
from prometheus_client import Counter, Gauge, Histogram

from borgy_process_agent.metrics.utils import type_name, sanitize_exception_message


http_request_inprogress = Gauge(
    "http_request_inprogress",
    "In-progress HTTP requests")

http_request_total = Counter(
    "http_request_total",
    "Number of HTTP requests",
    ['method', 'endpoint', 'status'])

http_request_errors_total = Counter(
    "http_request_error_total",
    "Number of HTTP errors",
    ["method", "endpoint", "error_type", "error_message"])

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration (seconds)",
    ["method", "endpoint"])


def collect_flask_metrics(app):
    # Register Prometheus metric collectors by hooking into
    # Flask's request signals.
    flask.request_started.connect(request_started_handler, app)
    flask.request_finished.connect(request_finished_handler, app)
    flask.got_request_exception.connect(got_request_exception_handler, app)


def request_endpoint(request) -> str:
    """
    Use the URL rule template if available else the path.
    """
    if request.url_rule:
        return request.url_rule.rule
    return request.path


def request_started_handler(_, **extra):
    http_request_inprogress.inc()
    http_request_duration = getattr(flask.g, "http_request_duration", None)
    if http_request_duration is None:
        flask.g.http_request_duration = http_request_duration_seconds.labels(
            method=flask.request.method,
            endpoint=request_endpoint(flask.request),
        ).time()
        flask.g.http_request_duration.__enter__()


def request_finished_handler(_, response, **extra):
    http_request_duration = getattr(flask.g, "http_request_duration", None)
    if http_request_duration:
        http_request_duration.__exit__(None, None, None)
        del flask.g.http_request_duration

        http_request_inprogress.dec()
        http_request_total.labels(
            method=flask.request.method,
            endpoint=request_endpoint(flask.request),
            status=response.status_code
        ).inc()


def got_request_exception_handler(_, exception, **extra):
    http_request_errors_total.labels(
        method=flask.request.method,
        endpoint=request_endpoint(flask.request),
        error_type=type_name(exception),
        error_message=sanitize_exception_message(exception)
    ).inc()
