"""Public-safe, stateless FastAPI teaching endpoint; no outbound network or storage."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from reliability_lab.core import (
    VERSION, analyze_deliveries, demo_signature, example_event,
    plan_retries, sample_scenario, validate_event, verify_demo_signature,
)

MAX_BODY_BYTES = 65536
app = FastAPI(
    title="Webhook Reliability Lab API",
    version=VERSION,
    description=(
        "Deterministic simulation of webhook validation, duplicate delivery, "
        "retry/backoff and a PUBLIC-KEY HMAC demonstration. No outgoing webhooks "
        "or stored state. Never supply private webhook payloads or credentials."
    ),
    contact={"name": "Ahmad Yar", "url": "https://www.ahmadyar.co/"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
)


@app.middleware("http")
async def bound_request_body(request: Request, call_next):
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > MAX_BODY_BYTES:
                return JSONResponse(status_code=413, content={"error": "body_too_large"})
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "invalid_content_length"})
    if request.method in {"POST", "PUT", "PATCH"}:
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"error": "body_too_large"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(RequestValidationError)
async def safe_validation_error(_request: Request, exc: RequestValidationError):
    # Do not echo values: Pydantic/FastAPI errors can include user-supplied input.
    return JSONResponse(status_code=422, content={
        "error": "invalid_request",
        "issues": [
            {"field": ".".join(str(x) for x in item.get("loc", []) if isinstance(x, (str, int))),
             "code": item.get("type", "invalid")}
            for item in exc.errors()[:15]
        ],
    })


@app.exception_handler(ValueError)
async def safe_core_error(_request: Request, _exc: ValueError):
    return JSONResponse(status_code=422, content={"error": "invalid_parameters"})


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidationRequest(StrictModel):
    event: dict


class ReplayRequest(StrictModel):
    deliveries: list[dict] = Field(min_length=1, max_length=60)
    ttl_seconds: int = Field(default=300, ge=1, le=3600)


class RetryRequest(StrictModel):
    statuses: list[int] = Field(min_length=1, max_length=12)
    base_seconds: float = Field(default=1.0, ge=0.1, le=120)
    cap_seconds: float = Field(default=60.0, ge=0.1, le=3600)
    jitter: float = Field(default=0.0, ge=0, le=0.5)
    seed: int = Field(default=7, ge=0, le=1_000_000)
    retry_after_seconds: float | None = Field(default=None, ge=0, le=3600)


class SignRequest(StrictModel):
    payload: str = Field(max_length=8000)
    timestamp: int = Field(ge=0)


class VerifyRequest(SignRequest):
    signature: str = Field(max_length=90)
    reference_time: int | None = Field(default=None, ge=0)
    tolerance_seconds: int = Field(default=300, ge=1, le=3600)


@app.get("/")
def welcome():
    return {
        "name": "Webhook Reliability Lab",
        "version": VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
        "project": "https://github.com/ahamdjin/webhook-reliability-lab",
        "portfolio": "https://www.ahmadyar.co/",
        "privacy": "Send synthetic data only. This public educational API is stateless.",
    }


@app.get("/api/v1/health")
def health():
    return {"ok": True, "version": VERSION, "mode": "stateless_no_network_no_storage"}


@app.get("/api/v1/scenarios")
def scenarios():
    return {
        "scenarios": {
            name: sample_scenario(name)
            for name in ("happy_path", "duplicate_delivery", "collision", "expired_replay", "invalid_payload")
        },
        "sample_event": example_event(),
    }


@app.post("/api/v1/validate")
def validate(body: ValidationRequest):
    return validate_event(body.event)


@app.post("/api/v1/replay")
def replay(body: ReplayRequest):
    return analyze_deliveries(body.deliveries, body.ttl_seconds)


@app.post("/api/v1/retry")
def retry(body: RetryRequest):
    return plan_retries(
        body.statuses, base_seconds=body.base_seconds, cap_seconds=body.cap_seconds,
        jitter=body.jitter, seed=body.seed, retry_after_seconds=body.retry_after_seconds
    )


@app.post("/api/v1/demo-sign")
def sign(body: SignRequest):
    return {
        "signature": demo_signature(body.payload, body.timestamp),
        "timestamp": body.timestamp,
        "warning": "Uses a publicly documented training key. Never use for production authentication.",
    }


@app.post("/api/v1/verify-sign")
def verify(body: VerifyRequest):
    return verify_demo_signature(
        body.payload, body.timestamp, body.signature,
        reference_time=body.reference_time, tolerance_seconds=body.tolerance_seconds,
    )
