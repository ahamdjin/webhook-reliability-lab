import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_postman_v21_schema_and_no_secrets():
    path = ROOT / "postman" / "Webhook-Reliability-Lab.postman_collection.json"
    collection = json.loads(path.read_text())
    assert collection["info"]["schema"].endswith("/v2.1.0/collection.json")
    assert "www.ahmadyar.co" in collection["info"]["description"]
    assert collection["auth"]["type"] == "noauth"
    assert next(v for v in collection["variable"] if v["key"] == "base_url")["value"] == "https://webhook-reliability-api.vercel.app"
    assert len(collection["item"]) == 5
    requests = [req for folder in collection["item"] for req in folder["item"]]
    assert len(requests) >= 14
    assert all(req.get("event") and req["event"][0]["script"]["exec"] for req in requests)
    assert all(req["request"]["url"]["raw"].startswith("{{base_url}}/") for req in requests)
    content = path.read_text().lower()
    assert "bearer sk_" not in content
    assert "authorization: bearer" not in content
    assert "{{api_key}}" not in content


def test_environment_only_sets_local_endpoint():
    env = json.loads((ROOT / "postman" / "Local.postman_environment.json").read_text())
    assert env["values"] == [{
        "key": "base_url", "value": "http://127.0.0.1:8000",
        "type": "default", "enabled": True,
    }]
