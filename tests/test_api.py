import time
from collections import OrderedDict

import pytest

from app import create_app
from app.models import db


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app.test_client()

@pytest.fixture
def sample_fields(client):
    fields = [
        {"key": "name", "type": "string", "options": None},
        {"key": "risk_score", "type": "float", "options": None},
        {"key": "count", "type": "integer", "options": None},
        {"key": "is_active", "type": "boolean", "options": None},
        {"key": "end_date", "type": "date", "options": None},
        {"key": "environment", "type": "list", "options": ["production", "staging", "lab"]},
    ]
    created = []
    for f in fields:
        resp = client.post("/fields", json=f)
        created.append({**f, **resp.json})
    return created

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}

# create_field test
def test_create_field_201(client):
    types = ["string", "text", "integer", "float", "boolean", "date"]
    for t in types:
        resp = client.post("/fields", json={"key": f"field_{t}", "type": t, "options": None})
        assert resp.status_code == 201
        assert resp.json["type"] == t
    
    resp = client.post("/fields", json={"key": "field_list", "type": "list", "options": ["a", "b"]})
    assert resp.status_code == 201
    assert resp.json["type"] == "list"

def test_create_field_409_duplicate_key(client):
    client.post("/fields", json={"key": "duplicate", "type": "string", "options": None})
    resp = client.post("/fields", json={"key": "duplicate", "type": "string", "options": None})
    assert resp.status_code == 409

def test_create_field_400_invalid_field(client):
    resp = client.post("/fields", json={"key": "test", "type": "unknown_type", "options": None})
    assert resp.status_code == 400
    
    resp = client.post("/fields", json={"type": "string", "options": None})
    assert resp.status_code == 400
    
    resp = client.post("/fields", json={"key": "", "type": "string", "options": None})
    assert resp.status_code == 400

def test_create_field_400_list_with_invalid_options(client):
    resp = client.post("/fields", json={"key": "env", "type": "list", "options": None})
    assert resp.status_code == 400
    
    resp = client.post("/fields", json={"key": "env", "type": "list", "options": []})
    assert resp.status_code == 400

def test_create_field_400_malformed_json(client):
    """malformed JSON → 400"""
    resp = client.post("/fields", data="{invalid json}", content_type="application/json")
    assert resp.status_code == 400

# get_fields test
def test_get_fields_200_after_create(client):
    client.post("/fields", json={"key": "field1", "type": "string", "options": None})
    client.post("/fields", json={"key": "field2", "type": "integer", "options": None})
    
    resp = client.get("/fields")
    assert resp.status_code == 200
    assert len(resp.json) == 2

def test_get_fields_200_empty(client):
    resp = client.get("/fields")
    assert resp.status_code == 200
    assert resp.json == []

# create_record test
def test_create_record_201(client, sample_fields):
    payload = {
        "values": {
            "name": "test",
            "risk_score": 8.5,
            "count": 42,
            "is_active": True,
            "end_date": "2026-12-31",
            "environment": "production"
        }
    }
    resp = client.post("/records", json=payload)
    assert resp.status_code == 201
    assert resp.json["values"]["count"] == 42
    assert resp.json["values"]["risk_score"] == 8.5

def test_create_record_201_with_null_values(client, sample_fields):
    resp = client.post("/records", json={"values": {"name": "partial"}})
    assert resp.status_code == 201
    assert "name" in resp.json["values"] 

def test_create_record_400_incompatible_value(client, sample_fields):
    resp = client.post("/records", json={"values": {"count": "not_a_number"}})
    assert resp.status_code == 400
    
    resp = client.post("/records", json={"values": {"risk_score": "high"}})
    assert resp.status_code == 400
    
    resp = client.post("/records", json={"values": {"end_date": "31/12/2026"}})
    assert resp.status_code == 400

def test_create_record_400_unknown_field(client, sample_fields):
    resp = client.post("/records", json={"values": {"unknown_field": "value"}})
    assert resp.status_code == 400

def test_create_record_400_list_with_invalid_options(client, sample_fields):
    resp = client.post("/records", json={"values": {"environment": "invalid_env"}})
    assert resp.status_code == 400

def test_create_record_400_malformed_json(client, sample_fields):
    resp = client.post("/records", data="{invalid}", content_type="application/json")
    assert resp.status_code == 400

# get_records test
def test_get_records_200_after_create(client, sample_fields):
    client.post("/records", json={"values": {"name": "test"}})
    resp = client.get("/records")
    assert resp.status_code == 200
    assert resp.json["total"] == 1

def test_get_records_200_empty(client, sample_fields):
    resp = client.get("/records")
    assert resp.status_code == 200
    assert resp.json["total"] == 0
    assert resp.json["items"] == []

def test_get_records_200_with_sort_asc(client, sample_fields):
    client.post("/records", json={"values": {"count": 10}})
    client.post("/records", json={"values": {"count": 2}})
    client.post("/records", json={"values": {"count": 9}})
    client.post("/records", json={"values": {"name": "no_count"}})
    
    resp = client.get("/records?sort=count")
    assert resp.status_code == 200
    counts = [r["values"].get("count") for r in resp.json["items"]]
    assert counts[:3] == [2, 9, 10]
    assert counts[3] is None

def test_get_records_200_with_sort_desc(client, sample_fields):
    client.post("/records", json={"values": {"risk_score": 2.0}})
    client.post("/records", json={"values": {"risk_score": 10.5}})
    client.post("/records", json={"values": {"risk_score": 9.3}})
    
    resp = client.get("/records?sort=-risk_score")
    assert resp.status_code == 200
    scores = [r["values"]["risk_score"] for r in resp.json["items"]]
    assert scores == [10.5, 9.3, 2.0]

def test_get_records_400_nonexistent_field_in_sort(client, sample_fields):
    resp = client.get("/records?sort=nonexistent_field")
    assert resp.status_code == 400

def test_get_records_200_with_filter_numeric(client, sample_fields):
    client.post("/records", json={"values": {"risk_score": 5.0}})
    client.post("/records", json={"values": {"risk_score": 8.0}})
    client.post("/records", json={"values": {"risk_score": 10.0}})
    
    resp = client.get("/records?filter=risk_score:gte:7.0")
    assert resp.status_code == 200
    assert resp.json["total"] == 2

def test_get_records_200_with_filter_string(client, sample_fields):
    client.post("/records", json={"values": {"name": "version-1.0-rc1"}})
    client.post("/records", json={"values": {"name": "version-2.0"}})
    client.post("/records", json={"values": {"name": "rc2-beta"}})
    
    resp = client.get("/records?filter=name:contains:rc")
    assert resp.status_code == 200
    assert resp.json["total"] == 2

def test_get_records_200_with_filter_boolean(client, sample_fields):
    client.post("/records", json={"values": {"is_active": True}})
    client.post("/records", json={"values": {"is_active": False}})
    
    resp = client.get("/records?filter=is_active:eq:true")
    assert resp.status_code == 200
    assert resp.json["total"] == 1

def test_get_records_200_with_filter_list(client, sample_fields):
    client.post("/records", json={"values": {"environment": "production"}})
    client.post("/records", json={"values": {"environment": "staging"}})
    client.post("/records", json={"values": {"environment": "lab"}})
    
    resp = client.get("/records?filter=environment:in:production,staging")
    assert resp.status_code == 200
    assert resp.json["total"] == 2

def test_get_records_200_with_multiple_filters(client, sample_fields):
    client.post("/records", json={"values": {"risk_score": 8.0, "environment": "production"}})
    client.post("/records", json={"values": {"risk_score": 9.0, "environment": "lab"}})
    client.post("/records", json={"values": {"risk_score": 5.0, "environment": "production"}})
    
    resp = client.get("/records?filter=risk_score:gte:7.0&filter=environment:in:production,staging")
    assert resp.status_code == 200
    assert resp.json["total"] == 1

def test_get_records_200_with_pagination(client, sample_fields):
    for i in range(5):
        client.post("/records", json={"values": {"count": i}})
    
    resp = client.get("/records?limit=2&offset=0")
    assert resp.status_code == 200
    assert len(resp.json["items"]) == 2
    assert resp.json["total"] == 5
    assert resp.json["limit"] == 2
    assert resp.json["offset"] == 0

def test_get_records_400_invalid_limit_offset(client, sample_fields):
    resp = client.get("/records?limit=-1")
    assert resp.status_code == 400
    
    resp = client.get("/records?offset=-5")
    assert resp.status_code == 400
    
    resp = client.get("/records?limit=abc")
    assert resp.status_code == 400
    
    resp = client.get("/records?offset=xyz")
    assert resp.status_code == 400
    
    resp = client.get("/records?limit=101")
    assert resp.status_code == 400

def test_get_records_400_nonexistent_field_in_filter(client, sample_fields):
    resp = client.get("/records?filter=nonexistent_field:eq:value")
    assert resp.status_code == 400

def test_get_records_400_invalid_type_in_filter(client, sample_fields):
    resp = client.get("/records?filter=risk_score:contains:5")
    assert resp.status_code == 400

def test_get_records_400_invalid_operator_in_filter(client, sample_fields):
    resp = client.get("/records?filter=name:unknown_op:value")
    assert resp.status_code == 400

def test_get_records_200_with_sort_and_filter(client, sample_fields):
    client.post("/records", json={"values": {"risk_score": 8.0, "environment": "production"}})
    client.post("/records", json={"values": {"risk_score": 9.0, "environment": "production"}})
    client.post("/records", json={"values": {"risk_score": 7.0, "environment": "lab"}})
    
    resp = client.get("/records?sort=-risk_score&filter=environment:eq:production")
    assert resp.status_code == 200
    assert resp.json["total"] == 2
    scores = [r["values"]["risk_score"] for r in resp.json["items"]]
    assert scores == [9.0, 8.0]
