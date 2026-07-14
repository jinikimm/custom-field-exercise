import json
import os
from urllib import error, request

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
        assert status == 201, f"Failed to create field '{field['key']}': status={status}, response={resp}"
        assert resp["key"] == field["key"], f"Field key mismatch: expected={field['key']}, actual={resp.get('key')}"
    
    # get fields
    status, resp = _http_json("GET", base_url, "/fields")
    assert status == 200, f"Failed to get fields: status={status}, response={resp}"
    assert len(resp) >= 3, f"Field count mismatch: expected_at_least=3, actual={len(resp)}, response={resp}"
    
    # create records
    records = [
        {"values": {"firmware_version": "1.2.3-rc1", "risk_score": 8.5, "environment": "production"}},
        {"values": {"firmware_version": "2.0.0", "risk_score": 9.0, "environment": "staging"}},
        {"values": {"firmware_version": "1.0.0", "risk_score": 6.5, "environment": "production"}},
    ]
    
    for record in records:
        status, resp = _http_json("POST", base_url, "/records", record)
        assert status == 201, f"Failed to create record with values={record['values']}: status={status}, response={resp}"
        assert "record_id" in resp, f"Missing record_id in response: values={record['values']}, response={resp}"
    
    # get records
    status, resp = _http_json("GET", base_url, "/records?sort=-risk_score")
    assert status == 200, f"Failed to get sorted records: status={status}, response={resp}"
    assert resp["total"] == 3, f"Record total mismatch: expected=3, actual={resp.get('total')}, response={resp}"
    scores = [r["values"]["risk_score"] for r in resp["items"]]
    assert scores == [9.0, 8.5, 6.5], f"Score order mismatch: expected=[9.0, 8.5, 6.5], actual={scores}"
    
    status, resp = _http_json("GET", base_url, "/records?filter=risk_score:gte:7.0&filter=environment:in:production,staging")
    assert status == 200, f"Failed to get filtered records: status={status}, response={resp}"
    assert resp["total"] == 2, f"Filtered record total mismatch: expected=2, actual={resp.get('total')}, response={resp}"
    
    status, resp = _http_json("GET", base_url, "/records?limit=2&offset=0")
    assert status == 200, f"Failed to get paginated records: status={status}, response={resp}"
    assert len(resp["items"]) == 2, f"Paginated item count mismatch: expected=2, actual={len(resp['items'])}, response={resp}"
    assert resp["total"] == 3, f"Paginated record total mismatch: expected=3, actual={resp.get('total')}, response={resp}"
