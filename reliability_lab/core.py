"""Deterministic, read-only teaching models for webhook delivery reliability.

No network, database, background workers or real event delivery. All supplied
payloads stay in process. Never treat this simulation as a production receiver.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import hmac
import json
import random
import re
import time
from typing import Any

VERSION = "0.1.0"
MAX_DELIVERIES = 60
DEMO_SECRET = "public-webhook-demo-key-not-for-real-integrations"
IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{2,95}$")


def example_event(event_id: str = "evt_lead_001", kind: str = "lead.created") -> dict:
    return {
        "event_id": event_id,
        "event_type": kind,
        "occurred_at": "2026-01-01T12:00:00Z",
        "data": {"lead_id": "lead_demo_001", "source": "documentation", "amount": 125},
    }


def sample_scenario(name: str) -> list[dict]:
    """Return synthetic deliveries with offsets in seconds and independent event copies."""
    base = example_event()
    if name == "happy_path":
        return [{"at": 0, "event": base}, {"at": 2, "event": example_event("evt_lead_002")}]
    if name == "duplicate_delivery":
        return [{"at": 0, "event": base}, {"at": 2, "event": base}, {"at": 8, "event": base}]
    if name == "collision":
        modified = example_event()
        modified["data"]["amount"] = 999
        return [{"at": 0, "event": base}, {"at": 2, "event": modified}]
    if name == "expired_replay":
        return [{"at": 0, "event": base}, {"at": 3, "event": base}, {"at": 310, "event": base}]
    if name == "invalid_payload":
        invalid = example_event("invalid id with spaces")
        return [{"at": 0, "event": invalid}, {"at": 2, "event": base}]
    raise ValueError("Unknown synthetic scenario")


def _canonical_bytes(event: dict) -> bytes:
    return json.dumps(event, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def validate_event(event: Any) -> dict:
    """Validate a minimal, intentionally opinionated event envelope.

    Reports locations and rule codes but does not reflect event values in errors.
    """
    errors: list[dict] = []
    if not isinstance(event, dict):
        return {"valid": False, "errors": [{"code": "EVENT_OBJECT", "field": "event",
                    "message": "Event must be a JSON object."}]}
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or IDENTIFIER_RE.fullmatch(event_id) is None:
        errors.append({"code": "EVENT_ID", "field": "event_id",
                       "message": "Use 3–96 alphanumeric, dot, underscore, colon or hyphen characters."})
    event_type = event.get("event_type")
    if not isinstance(event_type, str) or len(event_type) not in range(3, 81) or not re.fullmatch(r"[a-z][a-z0-9_.-]*", event_type):
        errors.append({"code": "EVENT_TYPE", "field": "event_type",
                       "message": "Use a lowercase event type of 3–80 allowed characters."})
    raw_time = event.get("occurred_at")
    if not isinstance(raw_time, str) or len(raw_time) > 40:
        errors.append({"code": "EVENT_TIME", "field": "occurred_at",
                       "message": "Provide an ISO 8601 timestamp with timezone."})
    else:
        try:
            instant = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            if instant.tzinfo is None or instant.utcoffset() is None:
                raise ValueError("Missing timezone")
        except (ValueError, OverflowError):
            errors.append({"code": "EVENT_TIME", "field": "occurred_at",
                           "message": "Timestamp must be ISO 8601 with an explicit timezone."})
    if not isinstance(event.get("data"), dict):
        errors.append({"code": "EVENT_DATA", "field": "data",
                       "message": "Event data must be a JSON object."})
    try:
        if len(_canonical_bytes(event)) > 16000:
            errors.append({"code": "EVENT_SIZE", "field": "event",
                           "message": "One event must not exceed 16,000 encoded bytes."})
    except (TypeError, ValueError, OverflowError, RecursionError):
        errors.append({"code": "EVENT_JSON", "field": "event",
                       "message": "Event contains non-JSON data."})
    return {"valid": not errors, "errors": errors}


def analyze_deliveries(deliveries: list[dict], ttl_seconds: int = 300) -> dict:
    """Simulate TTL-scoped deduplication; collision check is within active window.

    Deliberately single-process deterministic simulation. A production receiver needs
    an atomic durable uniqueness constraint, concurrent safety, expiry, and recovery.
    """
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 3600:
        raise ValueError("ttl_seconds must be an integer between 1 and 3600")
    if not isinstance(deliveries, list) or not 1 <= len(deliveries) <= MAX_DELIVERIES:
        raise ValueError("Provide 1–60 deliveries")
    seen: dict[str, tuple[int, str]] = {}
    outcomes: list[dict] = []
    previous_at = -1
    for index, delivery in enumerate(deliveries):
        if not isinstance(delivery, dict):
            raise ValueError("Each delivery must be an object")
        at = delivery.get("at")
        if isinstance(at, bool) or not isinstance(at, int) or not 0 <= at <= 100_000 or at < previous_at:
            raise ValueError("Delivery offsets must be nondecreasing integer seconds (0–100000)")
        previous_at = at
        # Expired entries no longer protect this event_id. Exact expiry is inclusive.
        seen = {k: (t, digest) for k, (t, digest) in seen.items() if at - t < ttl_seconds}
        event = delivery.get("event")
        inspection = validate_event(event)
        if not inspection["valid"]:
            outcomes.append({"index": index + 1, "at": at, "action": "rejected_invalid",
                             "rule": inspection["errors"][0]["code"],
                             "active_keys": len(seen)})
            continue
        key = event["event_id"]
        digest = hashlib.sha256(_canonical_bytes(event)).hexdigest()
        prior = seen.get(key)
        if prior is None:
            seen[key] = (at, digest)
            outcomes.append({"index": index + 1, "at": at, "action": "accepted",
                             "rule": "NEW_OR_EXPIRED", "active_keys": len(seen)})
        elif prior[1] != digest:
            outcomes.append({"index": index + 1, "at": at, "action": "rejected_collision",
                             "rule": "SAME_ID_DIFFERENT_BODY", "active_keys": len(seen)})
        else:
            outcomes.append({"index": index + 1, "at": at, "action": "ignored_duplicate",
                             "rule": "ALREADY_PROCESSED", "active_keys": len(seen)})
    counts = Counter(x["action"] for x in outcomes)
    return {
        "mode": "local_stateless_simulation",
        "ttl_seconds": ttl_seconds,
        "summary": {name: counts[name] for name in
                    ("accepted", "ignored_duplicate", "rejected_collision", "rejected_invalid")},
        "deliveries": outcomes,
        "limitations": [
            "State is simulated only for this request; it is not stored between calls.",
            "Concurrent or multi-region consumers require shared atomic durable storage.",
            "After TTL expires, the same event may be processed again.",
        ],
    }


RETRYABLE_STATUSES = {0, 408, 425, 429, 500, 502, 503, 504}


def plan_retries(statuses: list[int], *, base_seconds: float = 1.0,
                 cap_seconds: float = 60.0, jitter: float = 0.0,
                 seed: int = 7, retry_after_seconds: float | None = None) -> dict:
    """Compute a schedule for provided simulated status codes. Never sends HTTP."""
    if not isinstance(statuses, list) or not 1 <= len(statuses) <= 12:
        raise ValueError("Provide between 1 and 12 HTTP status codes")
    if any(isinstance(s, bool) or not isinstance(s, int) or (s != 0 and not 100 <= s <= 599) for s in statuses):
        raise ValueError("Statuses must be HTTP codes from 100–599 or 0 for timeout")
    if not (0.1 <= float(base_seconds) <= 120 and
            float(base_seconds) <= float(cap_seconds) <= 3600):
        raise ValueError("Backoff base/cap range is invalid")
    if not 0 <= float(jitter) <= 0.5:
        raise ValueError("Jitter must be between 0 and 0.5")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 1_000_000:
        raise ValueError("Seed must be 0–1000000")
    if retry_after_seconds is not None and not 0 <= float(retry_after_seconds) <= 3600:
        raise ValueError("Retry-After must be between 0 and 3600 seconds")
    rng = random.Random(seed)
    attempts = []
    elapsed = 0.0
    for index, status in enumerate(statuses):
        number = index + 1
        outcome = ("succeeded" if 200 <= status < 300 else
                   "retryable_failure" if status in RETRYABLE_STATUSES else "terminal_failure")
        record = {"attempt": number, "at_seconds": round(elapsed, 3),
                  "status": status, "outcome": outcome, "wait_after_seconds": 0.0}
        attempts.append(record)
        if outcome != "retryable_failure":
            break
        if index + 1 >= len(statuses):
            record["outcome"] = "retry_budget_exhausted"
            break
        delay = min(float(cap_seconds), float(base_seconds) * (2 ** index))
        if status in (429, 503) and retry_after_seconds is not None:
            delay = min(float(cap_seconds), max(delay, float(retry_after_seconds)))
        if jitter:
            delay = max(0.0, min(float(cap_seconds), delay * rng.uniform(1-jitter, 1+jitter)))
        delay = round(delay, 3)
        record["wait_after_seconds"] = delay
        elapsed += delay
    return {
        "mode": "schedule_only_no_http",
        "attempts": attempts,
        "total_wait_seconds": round(elapsed, 3),
        "final_outcome": attempts[-1]["outcome"],
        "note": "0 means simulated timeout. Retries are modeled; no requests are made. Real clients must cap attempts and use request deadlines.",
    }


def demo_signature(payload: str, timestamp: int) -> str:
    """HMAC with a PUBLIC, intentionally insecure training key."""
    if not isinstance(payload, str) or len(payload.encode("utf-8")) > 8000:
        raise ValueError("Payload must be at most 8 KB")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < 0:
        raise ValueError("Timestamp must be an integer Unix epoch")
    message = f"{timestamp}.".encode("ascii") + payload.encode("utf-8")
    return "sha256=" + hmac.new(DEMO_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_demo_signature(payload: str, timestamp: int, signature: str,
                          *, reference_time: int | None = None,
                          tolerance_seconds: int = 300) -> dict:
    """Show signature + clock-window checks, NOT robust webhook authentication.

    Same signature can be replayed within time window; enforce idempotency too.
    """
    expected = demo_signature(payload, timestamp)
    if not isinstance(signature, str) or len(signature) > 90:
        raise ValueError("Signature must be a short string")
    if not isinstance(tolerance_seconds, int) or isinstance(tolerance_seconds, bool) or not 1 <= tolerance_seconds <= 3600:
        raise ValueError("Tolerance must be 1–3600 seconds")
    now = int(time.time()) if reference_time is None else reference_time
    if isinstance(now, bool) or not isinstance(now, int) or now < 0:
        raise ValueError("Reference time must be an integer Unix epoch")
    matched = hmac.compare_digest(expected, signature.lower())
    fresh = abs(now - timestamp) <= tolerance_seconds
    return {
        "valid": bool(matched and fresh),
        "signature_match": matched,
        "timestamp_in_window": fresh,
        "reason": "verified_demo" if matched and fresh else
                  ("stale_or_future_timestamp" if matched else "signature_mismatch"),
        "warning": "PUBLIC demo key, not production authentication. A valid signature can still replay within the timestamp window.",
    }
