import json

from fastapi.testclient import TestClient

from app import app
from reliability_lab.core import example_event, sample_scenario, demo_signature

client = TestClient(app)


def test_root_and_health_contract():
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["portfolio"] == "https://www.ahmadyar.co/"
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["ok"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_health_and_openapi_discoverability():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    routes = response.json()["paths"]
    assert {"/api/v1/health", "/api/v1/scenarios", "/api/v1/validate",
            "/api/v1/replay", "/api/v1/retry", "/api/v1/demo-sign",
            "/api/v1/verify-sign"} <= set(routes)


def test_synthetic_catalog():
    response = client.get("/api/v1/scenarios")
    assert response.status_code == 200
    assert len(response.json()["scenarios"]) == 5


def test_valid_and_invalid_envelope_responses():
    good = client.post("/api/v1/validate", json={"event": example_event()})
    assert good.status_code == 200 and good.json()["valid"]
    bad = client.post("/api/v1/validate", json={"event": {}})
    assert bad.status_code == 200 and not bad.json()["valid"]
    assert len(bad.json()["errors"]) >= 3


def test_api_replay_matches_shared_engine():
    r = client.post("/api/v1/replay", json={"deliveries": sample_scenario("duplicate_delivery")})
    assert r.status_code == 200
    assert r.json()["summary"]["ignored_duplicate"] == 2
    assert r.json()["mode"] == "local_stateless_simulation"


def test_ttl_works_across_request_but_no_state_carried():
    scenario = sample_scenario("duplicate_delivery")
    a = client.post("/api/v1/replay", json={"deliveries": scenario}).json()
    b = client.post("/api/v1/replay", json={"deliveries": scenario}).json()
    assert a == b
    single = client.post("/api/v1/replay", json={"deliveries": [scenario[0]]}).json()
    assert single["summary"]["accepted"] == 1


def test_retry_policy_respects_retry_after():
    payload = {"statuses": [429, 200], "retry_after_seconds": 10,
               "base_seconds": 1, "cap_seconds": 60, "jitter": 0}
    r = client.post("/api/v1/retry", json=payload)
    assert r.status_code == 200
    assert r.json()["total_wait_seconds"] == 10.0


def test_public_demo_sign_verify_and_expiry():
    payload = "fictional"
    signed = client.post("/api/v1/demo-sign", json={"payload": payload, "timestamp": 100})
    assert signed.status_code == 200
    signature = signed.json()["signature"]
    verified = client.post("/api/v1/verify-sign", json={"payload": payload, "timestamp": 100,
        "reference_time": 100, "signature": signature})
    assert verified.json()["valid"]
    stale = client.post("/api/v1/verify-sign", json={"payload": payload, "timestamp": 100,
        "reference_time": 1000, "signature": signature})
    assert not stale.json()["valid"]


def test_malformed_json_sanitizes_errors():
    marker = "PRIVATE_FAKE_MARKER_1234"
    r = client.post("/api/v1/validate", content='{"event": "' + marker,
                    headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_request"
    assert marker not in r.text


def test_extra_keys_sanitized():
    marker = "MUST_NOT_ECHO_PRIVATE_TEXT"
    r = client.post("/api/v1/validate", json={"event": example_event(), marker: marker})
    assert r.status_code == 422
    assert marker not in r.text


def test_oversized_request_rejected():
    r = client.post("/api/v1/validate", json={"event": example_event(),
        "blob": "x" * 70_000})
    assert r.status_code == 413
    assert r.json() == {"error": "body_too_large"}


def test_malformed_model_return_422():
    r = client.post("/api/v1/retry", json={"statuses": [503]*13})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_request"


def test_replay_bad_offset_return_422():
    deliveries = [{"at": 5, "event": example_event()}, {"at": 1, "event": example_event()}]
    r = client.post("/api/v1/replay", json={"deliveries": deliveries})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_parameters"


def test_cors_disabled_for_demo_api():
    r = client.options("/api/v1/health", headers={
        "origin": "https://untrusted.example", "access-control-request-method": "POST",
    })
    assert "access-control-allow-origin" not in r.headers
