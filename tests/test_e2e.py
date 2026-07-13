import json
import os
from urllib import error, request
from uuid import uuid4

import pytest


def _http_json(method, base_url, path, payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    req = request.Request(
        url=f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=req_headers,
        method=method,
    )

    try:
        with request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, json.loads(body) if body else {}

@pytest.fixture
def base_url():
    base_url = os.getenv("INTEGRATION_BASE_URL", "http://localhost:8080")
    try:
        status, _ = _http_json("GET", base_url, "/health")
    except Exception:
        pytest.skip(f"Live app is not reachable at {base_url}")

    if status != 200:
        pytest.skip(f"Live app health check failed at {base_url}")

    return base_url

def test_e2e_flow(base_url):
    # create fields
    fields = [
        {"key": "firmware_version", "type": "string", "options": None},
        {"key": "risk_score", "type": "float", "options": None},
        {"key": "environment", "type": "list", "options": ["production", "staging", "lab"]},
    ]
    
    for field in fields:
        status, resp = _http_json("POST", base_url, "/fields", field)
        assert status == 201, f"Failed to create field: {resp}"
        assert resp["key"] == field["key"]
    
    # get fields
    status, resp = _http_json("GET", base_url, "/fields")
    assert status == 200
    assert len(resp) >= 3
    
    # create records
    records = [
        {"values": {"firmware_version": "1.2.3-rc1", "risk_score": 8.5, "environment": "production"}},
        {"values": {"firmware_version": "2.0.0", "risk_score": 9.0, "environment": "staging"}},
        {"values": {"firmware_version": "1.0.0", "risk_score": 6.5, "environment": "production"}},
    ]
    
    for record in records:
        status, resp = _http_json("POST", base_url, "/records", record)
        assert status == 201, f"Failed to create record: {resp}"
        assert "record_id" in resp
    
    # get records
    status, resp = _http_json("GET", base_url, "/records?sort=-risk_score")
    assert status == 200
    assert resp["total"] == 3
    scores = [r["values"]["risk_score"] for r in resp["items"]]
    assert scores == [9.0, 8.5, 6.5]
    
    status, resp = _http_json("GET", base_url, "/records?filter=risk_score:gte:7.0&filter=environment:in:production,staging")
    assert status == 200
    assert resp["total"] == 2
    
    status, resp = _http_json("GET", base_url, "/records?limit=2&offset=0")
    assert status == 200
    assert len(resp["items"]) == 2
    assert resp["total"] == 3