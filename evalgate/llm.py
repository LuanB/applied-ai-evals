"""Every billed call goes through `billed()`: cassette → spend cap → live call →
ledger → trace span. Provider clients are thin wrappers over it.

Nothing in a project calls a provider SDK directly. That is what makes CI free and
deterministic (replay), keeps spend under the cap (live), and puts every call in the
trace with its cost.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from . import cassette, spend
from .trace import tracer

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


import contextvars

_case_usd: contextvars.ContextVar[list[float]] = contextvars.ContextVar("case_usd")


class _Ctx:
    project: str = "adhoc"


def reset_case_cost() -> None:
    _case_usd.set([0.0])


def case_cost() -> float:
    """Cost of the case currently running (per thread) — replayed calls count at their
    recorded price, so a replayed report shows what the run WOULD cost live."""
    return _case_usd.get([0.0])[0]


def set_project(name: str) -> None:
    _Ctx.project = name


def project() -> str:
    return _Ctx.project


def _cassette() -> cassette.Cassette:
    return cassette.Cassette(ROOT / "projects" / _Ctx.project / "cassettes")


def billed(kind: str, provider: str, model: str, request: dict[str, Any],
           live: Callable[[], dict[str, Any]],
           cost: Callable[[dict[str, Any]], float],
           estimate: float = 0.0) -> dict[str, Any]:
    """Run one billed call through cassette, cap, ledger and trace.

    `cost(response) -> usd` prices the real response; `estimate` is a pre-call guess
    used only for the cap check.
    """
    with tracer().start_as_current_span(kind) as span:
        span.set_attribute("gen_ai.system", provider)
        span.set_attribute("gen_ai.request.model", model)
        t0 = time.perf_counter()

        def guarded_live() -> dict[str, Any]:
            spend.check(provider, estimate)
            return live()

        resp, was_live = _cassette().call(kind, {"model": model, **request}, guarded_live)
        usd = cost(resp)
        acc = _case_usd.get(None)
        if acc is not None:
            acc[0] += usd
        if was_live:
            spend.record(provider, model, usd, _Ctx.project, kind)
        span.set_attribute("evalgate.replayed", not was_live)
        span.set_attribute("evalgate.cost_usd", round(usd, 6))
        span.set_attribute("evalgate.wall_ms", round((time.perf_counter() - t0) * 1000, 1))
        u = resp.get("usage") or {}
        if u:
            span.set_attribute("gen_ai.usage.input_tokens", u.get("prompt_tokens", 0))
            span.set_attribute("gen_ai.usage.output_tokens", u.get("completion_tokens", 0))
        return resp


# --------------------------------------------------------------------------
# Azure OpenAI
# --------------------------------------------------------------------------

_azure_client = None


def _azure():
    global _azure_client
    if _azure_client is None:
        from openai import AzureOpenAI
        _azure_client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )
    return _azure_client


def _usage_cost(model: str):
    def f(resp: dict[str, Any]) -> float:
        u = resp.get("usage") or {}
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
        return spend.token_cost(model, u.get("prompt_tokens", 0),
                                u.get("completion_tokens", 0), cached)
    return f


def chat(model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
         salt: str = "", cassette_key: dict[str, Any] | None = None, **params: Any) -> dict[str, Any]:
    """Azure OpenAI chat completion. Returns the raw response as a dict.

    `salt` goes into the cassette key only, never to the API: repeated trials of the
    same prompt are recorded separately, so variance survives replay.
    """
    request: dict[str, Any] = {"messages": messages, **params}
    if tools:
        request["tools"] = tools
    key_request = {**request, "_salt": salt} if salt else request
    if cassette_key is not None:
        # Requests carrying images key on a stable id instead of megabytes of base64,
        # so CI can replay without the images and cassettes stay small.
        key_request = {**cassette_key, "_salt": salt, "_params": {k: v for k, v in params.items()}}

    def live() -> dict[str, Any]:
        r = _azure().chat.completions.create(model=model, **request)
        return r.model_dump(exclude_none=True)

    return billed("chat", "azure", model, key_request, live, _usage_cost(model), estimate=0.02)


def embed(texts: list[str], model: str = "text-embedding-3-small",
          dimensions: int | None = None) -> list[list[float]]:
    request: dict[str, Any] = {"input": texts}
    if dimensions:
        request["dimensions"] = dimensions

    def live() -> dict[str, Any]:
        r = _azure().embeddings.create(model=model, **request)
        # 5 decimals is far below the noise floor of cosine ranking and shrinks the
        # cassette ~3x.
        return {"data": [[round(x, 5) for x in d.embedding] for d in r.data],
                "usage": {"prompt_tokens": r.usage.prompt_tokens, "completion_tokens": 0}}

    resp = billed("embed", "azure", model, request, live, _usage_cost(model), estimate=0.01)
    return resp["data"]


def message(resp: dict[str, Any]) -> dict[str, Any]:
    return resp["choices"][0]["message"]


def tool_args(call: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(call["function"].get("arguments") or "{}")
    except json.JSONDecodeError:
        return {}


# --------------------------------------------------------------------------
# Azure AI Document Intelligence (same multi-service resource and key)
# --------------------------------------------------------------------------

_di_client = None


def _di():
    global _di_client
    if _di_client is None:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
        _di_client = DocumentIntelligenceClient(
            os.environ["AZURE_AI_SERVICES_ENDPOINT"],
            AzureKeyCredential(os.environ["AZURE_OPENAI_API_KEY"]))
    return _di_client


def _field_value(f: dict[str, Any]) -> Any:
    for k in ("valueString", "valueDate", "valueNumber", "valueInteger", "valuePhoneNumber",
              "valueCountryRegion"):
        if k in f:
            return f[k]
    if "valueCurrency" in f:
        return f["valueCurrency"].get("amount")
    if "valueAddress" in f:
        return f.get("content")
    return f.get("content")


def di_analyze(model_id: str, path: Path, doc_id: str, markdown: bool = False,
               locale: str | None = None) -> dict[str, Any]:
    """Analyze one page image. Returns {content, pages, fields} — trimmed so the
    cassette holds what the eval reads, not the full polygon dump."""
    request: dict[str, Any] = {"doc": doc_id, "markdown": markdown}
    if locale:
        request["locale"] = locale

    def live() -> dict[str, Any]:
        kw: dict[str, Any] = {}
        if markdown:
            kw["output_content_format"] = "markdown"
        if locale:
            kw["locale"] = locale
        poller = _di().begin_analyze_document(model_id, body=path.read_bytes(),
                                              content_type="application/octet-stream", **kw)
        res = poller.result().as_dict()
        fields = {}
        for doc in res.get("documents") or []:
            for k, f in (doc.get("fields") or {}).items():
                fields[k] = {"value": _field_value(f), "confidence": f.get("confidence")}
        return {"content": res.get("content", ""), "pages": len(res.get("pages") or []) or 1,
                "fields": fields}

    def cost(resp: dict[str, Any]) -> float:
        return spend.page_cost(model_id, resp.get("pages", 1))

    return billed("di", "azure", model_id, request, live, cost, estimate=0.02)


def image_part(path: Path, detail: str = "high") -> dict[str, Any]:
    """Data-URI image part. Re-encodes anything that is not real PNG/JPEG (scan datasets
    often ship TIFF bytes under a .png name, which the endpoint rejects)."""
    import base64
    import io
    raw = path.read_bytes()
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif raw[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    else:
        from PIL import Image
        buf = io.BytesIO()
        Image.open(io.BytesIO(raw)).convert("L").save(buf, "PNG")
        raw, mime = buf.getvalue(), "image/png"
    b64 = base64.b64encode(raw).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": detail}}
