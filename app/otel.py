"""
OpenTelemetry instrumentation for the HTTP layer.

Distinct from app/tracing.py: that module traces individual agent install/invoke calls to
LangSmith (LLM/agent-specific). This module instruments the FastAPI service itself — every HTTP
request becomes an OTel span — and exports via OTLP to whatever vendor-neutral backend the
observability agent (or any other OTel-compatible tool) reads from: Jaeger, Tempo, Honeycomb,
Datadog, an OTel Collector, etc.

Degrades gracefully: if the `opentelemetry-*` packages aren't installed, setup() is a no-op and
the app runs exactly as before.

To enable it:
    pip install -r requirements.txt -r requirements-otel.txt
    export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318   # optional, this is the default
    export OTEL_SERVICE_NAME=agent-marketplace                 # optional, this is the default

Then every HTTP request produces a span exported to the OTLP endpoint above.
"""
from __future__ import annotations

import os
from typing import Any

_import_error: str | None = None
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError as e:  # pragma: no cover - exercised only when otel packages aren't installed
    trace = None
    _import_error = str(e)

OTEL_ENABLED = trace is not None
_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
_service_name = os.getenv("OTEL_SERVICE_NAME", "agent-marketplace")


def setup(app: Any) -> None:
    """Wire up the tracer provider and instrument the given FastAPI app. No-op if disabled."""
    if not OTEL_ENABLED:
        return
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: _service_name}))
    exporter = OTLPSpanExporter(endpoint=f"{_endpoint.rstrip('/')}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)


def otel_status() -> dict:
    if OTEL_ENABLED:
        reason = "enabled"
    else:
        reason = "opentelemetry packages not installed"
    return {
        "otel_tracing_enabled": OTEL_ENABLED,
        "reason": reason,
        "service_name": _service_name if OTEL_ENABLED else None,
        "otlp_endpoint": _endpoint if OTEL_ENABLED else None,
    }
