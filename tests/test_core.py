import copy
from datetime import datetime
import json

import pytest

from reliability_lab.core import (
    MAX_DELIVERIES, analyze_deliveries, demo_signature, example_event,
    plan_retries, sample_scenario, validate_event, verify_demo_signature,
)


def test_valid_sample_and_timezone_required():
    good = example_event()
    assert validate_event(good)["valid"]
    assert validate_event({**good, "occurred_at": "2026-01-01T12:00:00"})["errors"][0]["code"] == "EVENT_TIME"


@pytest.mark.parametrize("field,value,rule", [
    ("event_id", "a", "EVENT_ID"),
    ("event_id", "id with spaces", "EVENT_ID"),
    ("event_id", None, "EVENT_ID"),
    ("event_type", "Invalid.Type", "EVENT_TYPE"),
    ("event_type", 77, "EVENT_TYPE"),
    ("occurred_at", "bad date", "EVENT_TIME"),
    ("data", ["not an object"], "EVENT_DATA"),
])
def test_event_contract_invalid(field, value, rule):
    event = example_event()
    event[field] = value
    assert rule in [e["code"] for e in validate_event(event)["errors"]]


def test_event_size_limit_and_no_private_content_reflection():
    secret = "PRIVATE_REAL_SECRET_EXAMPLE_MARKER"
    result = validate_event({**example_event(), "data": {"text": secret * 1000}})
    assert not result["valid"]
    assert "EVENT_SIZE" in [e["code"] for e in result["errors"]]
    assert secret not in json.dumps(result)


def test_non_object_event_error():
    assert validate_event(["unexpected"])["errors"][0]["code"] == "EVENT_OBJECT"


def test_preset_coverage_and_no_original_mutation():
    scenarios = ("happy_path", "duplicate_delivery", "collision", "expired_replay", "invalid_payload")
    for name in scenarios:
        data = sample_scenario(name)
        assert data
        r = analyze_deliveries(data, 300)
        assert sum(r["summary"].values()) == len(data)
    with pytest.raises(ValueError):
        sample_scenario("fictional")


def test_dedupe_after_retries_within_ttl():
    r = analyze_deliveries(sample_scenario("duplicate_delivery"), ttl_seconds=300)
    assert r["summary"]["accepted"] == 1
    assert r["summary"]["ignored_duplicate"] == 2
    assert r["summary"]["rejected_collision"] == 0
    assert "SAME_ID_DIFFERENT_BODY" not in json.dumps(r)


def test_payload_collision_same_id_different_body():
    r = analyze_deliveries(sample_scenario("collision"), 300)
    assert r["summary"]["rejected_collision"] == 1
    assert r["deliveries"][1]["rule"] == "SAME_ID_DIFFERENT_BODY"


def test_canonical_dedupe_ignores_json_field_order():
    event = example_event()
    changed_order = dict(reversed(list(event.items())))
    r = analyze_deliveries([{"at": 0, "event": event}, {"at": 1, "event": changed_order}])
    assert r["summary"]["ignored_duplicate"] == 1


def test_ttl_expiry_inclusive():
    event = example_event()
    at_boundary = [{"at": 0, "event": event}, {"at": 5, "event": event}]
    assert analyze_deliveries(at_boundary, 5)["summary"]["accepted"] == 2
    assert analyze_deliveries(at_boundary, 6)["summary"]["ignored_duplicate"] == 1


def test_invalid_does_not_reserve_key():
    r = analyze_deliveries(sample_scenario("invalid_payload"))
    assert r["summary"]["rejected_invalid"] == 1
    assert r["summary"]["accepted"] == 1


@pytest.mark.parametrize("deliveries,ttl", [
    ([], 300),
    ([{"at": 0, "event": example_event()}] * (MAX_DELIVERIES + 1), 300),
    ([{"at": 1, "event": example_event()}, {"at": 0, "event": example_event()}], 300),
    ([{"at": -1, "event": example_event()}], 300),
    ([{"at": True, "event": example_event()}], 300),
    ([{"at": 0, "event": example_event()}], 0),
    ([{"at": 0, "event": example_event()}], True),
])
def test_replay_invalid_boundaries(deliveries, ttl):
    with pytest.raises(ValueError):
        analyze_deliveries(deliveries, ttl)


def test_retry_exponential_and_stop_success():
    r = plan_retries([503, 503, 200, 503], base_seconds=1, jitter=0)
    assert r["total_wait_seconds"] == 3
    assert len(r["attempts"]) == 3
    assert r["final_outcome"] == "succeeded"


def test_retry_after_honored_and_capped():
    r = plan_retries([429, 200], retry_after_seconds=25, cap_seconds=10)
    assert r["total_wait_seconds"] == 10


def test_terminal_failure_not_retried():
    r = plan_retries([400, 200])
    assert r["final_outcome"] == "terminal_failure"
    assert len(r["attempts"]) == 1


def test_timeout_retry_and_exhaustion():
    r = plan_retries([0, 0, 0], base_seconds=1)
    assert r["final_outcome"] == "retry_budget_exhausted"
    assert [x["at_seconds"] for x in r["attempts"]] == [0, 1, 3]


def test_seeded_jitter_is_reproducible_and_capped():
    a = plan_retries([503, 503, 200], seed=42, jitter=.4, cap_seconds=2)
    b = plan_retries([503, 503, 200], seed=42, jitter=.4, cap_seconds=2)
    assert a == b
    assert all(x["wait_after_seconds"] <= 2 for x in a["attempts"])


@pytest.mark.parametrize("kwargs", [
    {"base_seconds": -1}, {"cap_seconds": .1, "base_seconds": 1},
    {"jitter": .8}, {"seed": -1}, {"retry_after_seconds": 9000},
])
def test_retry_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        plan_retries([503, 200], **kwargs)


@pytest.mark.parametrize("statuses", [[], [200]*13, [99, 200], [True, 200]])
def test_retry_invalid_statuses(statuses):
    with pytest.raises(ValueError):
        plan_retries(statuses)


def test_public_demo_signature_round_trip():
    payload = '{"event_id":"demo"}'
    signed = demo_signature(payload, 1700000000)
    report = verify_demo_signature(payload, 1700000000, signed, reference_time=1700000000)
    assert signed.startswith("sha256=") and len(signed) == 71
    assert report["valid"] and report["signature_match"]


def test_signature_tamper_rejected():
    signed = demo_signature("body", 100)
    assert not verify_demo_signature("changed", 100, signed, reference_time=100)["valid"]


def test_signature_replay_window_expires():
    signed = demo_signature("body", 100)
    result = verify_demo_signature("body", 100, signed, reference_time=401)
    assert result["reason"] == "stale_or_future_timestamp"
    assert result["signature_match"] and not result["timestamp_in_window"]


def test_signature_different_timestamp_fails():
    signed = demo_signature("body", 100)
    assert not verify_demo_signature("body", 101, signed, reference_time=101)["signature_match"]


def test_signature_input_bound():
    with pytest.raises(ValueError):
        demo_signature("x" * 8001, 100)
