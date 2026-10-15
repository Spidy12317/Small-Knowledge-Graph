from __future__ import annotations

import asyncio
import functools
import inspect
import json
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from core.tracing.serialize import to_jsonable

_graph_id: ContextVar[str | None] = ContextVar("skg_graph_id", default=None)
_last_trace_id: ContextVar[str | None] = ContextVar("skg_last_trace_id", default=None)

_step_lock = threading.Lock()
_step_counters: dict[int, int] = {}

_TRACER_NAME = "skg"


def current_trace_id() -> str | None:
    """Trace id of the graph update that just ran on this task."""
    return _last_trace_id.get()


def traced(fn):
    """Records one span around a decision function, including its inputs and output."""
    if asyncio.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            with _span(fn, args, kwargs) as span:
                try:
                    result = await fn(*args, **kwargs)
                except Exception as exc:
                    _mark_error(span, exc)
                    raise
                _record_output(span, result)
                return result

        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(*args, **kwargs):
        with _span(fn, args, kwargs) as span:
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                _mark_error(span, exc)
                raise
            _record_output(span, result)
            return result

    return sync_wrapper


def _next_step_index(trace_id: int) -> int:
    with _step_lock:
        index = _step_counters.get(trace_id, 0)
        _step_counters[trace_id] = index + 1
        return index


def _clear_step_index(trace_id: int) -> None:
    with _step_lock:
        _step_counters.pop(trace_id, None)


def _arguments(fn, args, kwargs) -> dict[str, Any]:
    try:
        bound = inspect.signature(fn).bind_partial(*args, **kwargs)
    except TypeError:
        return {}
    return dict(bound.arguments)


@contextmanager
def _span(fn, args, kwargs) -> Iterator[trace.Span]:
    arguments = _arguments(fn, args, kwargs)
    extracted = arguments.get("graph_id")
    token = _graph_id.set(str(extracted)) if extracted is not None else None
    is_root = not trace.get_current_span().get_span_context().is_valid
    trace_id: int | None = None
    tracer = trace.get_tracer(_TRACER_NAME)
    try:
        with tracer.start_as_current_span(fn.__name__) as span:
            context = span.get_span_context()
            if context.is_valid:
                trace_id = context.trace_id
                trace_hex = format(context.trace_id, "032x")
                _last_trace_id.set(trace_hex)
                span.set_attribute("skg.step_index", _next_step_index(context.trace_id))
            graph_id = _graph_id.get()
            if graph_id:
                span.set_attribute("skg.graph_id", graph_id)
            span.set_attribute("skg.step", fn.__name__)
            span.add_event("decision.input", {"payload": _dump(arguments)})
            yield span
    finally:
        if is_root and trace_id is not None:
            _clear_step_index(trace_id)
        if token is not None:
            _graph_id.reset(token)


def _record_output(span: trace.Span, result: Any) -> None:
    span.add_event("decision.output", {"payload": _dump(result)})


def _mark_error(span: trace.Span, exc: Exception) -> None:
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, str(exc)))


def _dump(value: Any) -> str:
    return json.dumps(to_jsonable(value), default=str)
