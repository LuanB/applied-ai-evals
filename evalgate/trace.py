"""OpenTelemetry tracing to a local JSONL file.

One trace per eval run: a root span per case, child spans per model/tool call, each
carrying model, tokens, cost, latency and whether it was replayed. The JSONL lands in
traces/ and the report is built from it, so "why did case 7 fail and what did it cost"
is answered from the trace rather than from print statements.

Swapping the exporter for OTLP (Azure Monitor, Langfuse, Honeycomb) is a one-line
change in `setup()`; nothing else in the harness knows where spans go.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

ROOT = Path(__file__).resolve().parent.parent
_provider: TracerProvider | None = None


class JsonlExporter(SpanExporter):
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with self.path.open("a") as f:
            for s in spans:
                f.write(json.dumps({
                    "name": s.name,
                    "trace_id": f"{s.context.trace_id:032x}",
                    "span_id": f"{s.context.span_id:016x}",
                    "parent_id": f"{s.parent.span_id:016x}" if s.parent else None,
                    "start_ns": s.start_time,
                    "end_ns": s.end_time,
                    "ms": round((s.end_time - s.start_time) / 1e6, 1),
                    "status": s.status.status_code.name,
                    "attrs": dict(s.attributes or {}),
                }, default=str) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def setup(run_id: str) -> Path:
    global _provider
    path = ROOT / "traces" / f"{run_id}.jsonl"
    if path.exists():
        path.unlink()
    # A provider per run rather than the global one, so two suites in one process
    # write to two files.
    _provider = TracerProvider(resource=Resource.create({"service.name": "evalgate",
                                                         "evalgate.run_id": run_id}))
    _provider.add_span_processor(SimpleSpanProcessor(JsonlExporter(path)))
    return path


def tracer() -> trace.Tracer:
    if _provider is None:
        setup("adhoc")
    return _provider.get_tracer("evalgate")  # type: ignore[union-attr]


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
