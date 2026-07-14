
from datetime import date

import pytest
from sqlalchemy.orm import aliased

from app import create_app
from app.error_handler import ConflictError, ValidationError
from app.models import Fields, RecordValues, db
from app.services import CustomFieldService


@pytest.fixture
def service():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})

    with app.app_context():
        db.create_all()
        yield CustomFieldService()

@pytest.fixture
def service_no_db():
    return CustomFieldService()


# create_field tests
@pytest.mark.parametrize(
    ("key", "type", "options"),
    [
        ("name", "string", None),
        ("description", "text", None),
        ("age", "integer", None),
        ("price", "float", None),
        ("is_active", "boolean", None),
        ("due_date", "date", None),
        ("environment", "list", ["prod", "dev"]),
    ],
)
def test_create_field_success(service, key, type, options):
    field = service.create_field({"key": key, "type": type, "options": options})

    assert field.key == key
    assert field.type == type
    assert field.options == options

@pytest.mark.parametrize(
    ("key", "type", "options"),
    [
        ("", "string", None),
        ("name", "unknown_type", None),
        ("environment", "list", []),
    ],
)
def test_create_field_invalid_type(service, key, type, options):
    with pytest.raises(ValidationError):
        service.create_field({"key": key, "type": type, "options": options})

def test_create_field_conflict(service):
    service.create_field({"key": "name", "type": "string"})

    with pytest.raises(ConflictError):
        service.create_field({"key": "name", "type": "string"})

# get_fields tests
def test_get_fields_success(service):
    service.create_field({"key": "name", "type": "string"})
    service.create_field({"key": "age", "type": "integer"})

    fields = service.get_fields()

    assert len(fields) == 2
    assert {field.key for field in fields} == {"name", "age"}

def test_get_fields_empty(service):
    assert service.get_fields() == []


# create_record tests
@pytest.mark.parametrize(
    "record_data",
    [
        {"name": "Alice", "age": 30},
        {"description": "A sample record", "price": 19.99},
        {"is_active": True, "due_date": "2024-01-15"},
        {"environment": "prod"},
    ],
)
def test_create_record_success(service, record_data):
    for key, type, options in [
        ("name", "string", None),
        ("description", "text", None),
        ("age", "integer", None),
        ("price", "float", None),
        ("is_active", "boolean", None),
        ("due_date", "date", None),
        ("environment", "list", ["prod", "dev"]),
    ]:
        service.create_field({"key": key, "type": type, "options": options})

    result = service.create_record(record_data)

    assert result["record_id"]
    for key, value in record_data.items():
        assert result["values"][key] == (30 if key == "age" else value)

@pytest.mark.parametrize(
    "record_data",
    [
        {"age": "not-a-number"},
        {"price": "not-a-float"},
        {"is_active": "not-a-boolean"},
        {"due_date": "not-a-date"},
        {"environment": "not-in-options"},
    ],
)
def test_create_record_invalid_type(service, record_data):
    service.create_field({"key": "age", "type": "integer"})
    service.create_field({"key": "price", "type": "float"})
    service.create_field({"key": "is_active", "type": "boolean"})
    service.create_field({"key": "due_date", "type": "date"})
    service.create_field({"key": "environment", "type": "list", "options": ["prod", "dev"]})

    with pytest.raises(ValidationError):
        service.create_record(record_data)


# get_records test
@pytest.mark.parametrize(
    ("offset", "limit", "sort", "filters", "expected_total", "expected_scores"),
    [
        (0, 10, "score", None, 3, [10, 20, 30]),
        (0, 10, "-score", None, 3, [30, 20, 10]),
        (0, 10, "score", ["score:gte:20"], 2, [20, 30]),
        (0, 10, "score", ["environment:eq:prod"], 2, [10, 30]),
        (0, 10, "score", ["score:gte:10", "environment:eq:prod"], 2, [10, 30]),
        (0, 2, "score", None, 3, [10, 20]),
        (1, 2, "score", None, 3, [20, 30]),
        (3, 2, "score", None, 3, []),
    ],
)
def test_get_records_success(service, offset, limit, sort, filters, expected_total, expected_scores):
    service.create_field({"key": "score", "type": "integer"})
    service.create_field({"key": "environment", "type": "list", "options": ["prod", "dev"]})

    service.create_record({"score": 30, "environment": "prod"})
    service.create_record({"score": 10, "environment": "prod"})
    service.create_record({"score": 20, "environment": "dev"})

    result = service.get_records(
        limit=limit,
        offset=offset,
        sort=sort,
        filters=filters,
    )
    scores = [record["values"]["score"] for record in result["items"]]

    assert result["total"] == expected_total
    assert result["limit"] == (limit if limit is not None else 10)
    assert result["offset"] == (offset if offset is not None else 0)
    assert scores == expected_scores

@pytest.mark.parametrize(
    ("sort", "filters"),
    [
        ("unknown_field", None),
        (None, ["unknown_field:eq:value"]),
        (None, ["score:contains:10"]),
        (None, ["score:unknown:10"]),
        (None, ["score:gte:not-a-number"]),
    ],
)
def test_get_records_unknown_field(service, sort, filters):
    service.create_field({"key": "score", "type": "integer"})

    with pytest.raises(ValidationError):
        service.get_records(sort=sort, filters=filters)


# _validate_field tests
@pytest.mark.parametrize(
    ("field_data",),
    [
        ({"key": "name", "type": "string", "options": None},),
        ({"key": "description", "type": "text", "options": None},),
        ({"key": "age", "type": "integer", "options": None},),
        ({"key": "price", "type": "float", "options": None},),
        ({"key": "is_active", "type": "boolean", "options": None},),
        ({"key": "due_date", "type": "date", "options": None},),
        ({"key": "environment", "type": "list", "options": ["prod", "dev"]},),
    ],
)
def test_validate_field_success(service, field_data):
    service._validate_field(field_data)

@pytest.mark.parametrize(
    ("field_data",),
    [
        ({"key": "", "type": "string", "options": None},),
        ({"key": "name", "type": "unknown_type", "options": None},),
        ({"key": "environment", "type": "list", "options": []},),
    ],
)
def test_validate_field_invalid_data(service, field_data):
    with pytest.raises(ValidationError):
        service._validate_field(field_data)


# _validate_record tests
@pytest.mark.parametrize(
    ("field_type", "value", "expected"),
    [
        ("string", "hello", "hello"),
        ("text", "hello world", "hello world"),
        ("integer", "42", 42),
        ("float", "3.14", 3.14),
        ("boolean", "true", True),
        ("boolean", "false", False),
        ("date", "2024-01-15", date(2024, 1, 15)),
        ("list", "prod", "prod"),
    ],
)
def test_validate_record_success(service, field_type, value, expected):
    if field_type == "list":
        field = Fields(key="environment", type=field_type, options=["prod", "dev"])
    else:
        field = Fields(key="test_field", type=field_type, options=None)
    db.session.add(field)
    db.session.commit()

    result = service._validate_record("test_field", value, field)

    assert result == expected

@pytest.mark.parametrize(
    ("field_type", "value"),
    [
        ("integer", "not-an-integer"),
        ("float", "not-a-float"),
        ("boolean", "not-a-boolean"),
        ("date", "not-a-date"),
        ("list", "not-in-options"),
    ],
)
def test_validate_record_invalid_data(service, field_type, value):
    if field_type == "list":
        field = Fields(key="environment", type=field_type, options=["prod", "dev"])
    else:
        field = Fields(key="test_field", type=field_type, options=None)
    db.session.add(field)
    db.session.commit()

    with pytest.raises(ValidationError):
        service._validate_record("environment" if field_type == "list" else "test_field", value, field)


# _parse_filter tests
@pytest.mark.parametrize(
    ("filter_str", "expected"),
    [
        ("name:eq:Alice", ("name", "eq", "Alice")),
        ("age:gte:30", ("age", "gte", "30")),
        ("score:in:10,20,30", ("score", "in", "10,20,30")),
        ("description:contains:hello world", ("description", "contains", "hello world")),
    ],
)
def test_parse_filter_success(service, filter_str, expected):
    db.session.add(Fields(key="name", type="string"))
    db.session.add(Fields(key="age", type="integer"))
    db.session.add(Fields(key="score", type="integer"))
    db.session.add(Fields(key="description", type="text"))
    db.session.commit()

    key, operator, value = service._parse_filter(filter_str)

    assert key == expected[0]
    assert operator == expected[1]
    assert value == expected[2]

@pytest.mark.parametrize(
    ("filter_str",),
    [
        ("name:eq:Alice",),
        ("invalid_filter",),
        ("name:unknown_operator:value",),
        ("age:gte:not-a-number",),
    ],
)
def test_parse_filter_invalid_filter_str(service, filter_str):
    with pytest.raises(ValidationError):
        service._parse_filter(filter_str)


# _parse_sort tests
@pytest.mark.parametrize(
    ("sort_str", "expected_key", "expected_descending"),
    [
        ("name", "name", False),
        ("-age", "age", True),
        ("score", "score", False),
        ("-created_at", "created_at", True),
    ],
)
def test_parse_sort_success(service, sort_str, expected_key, expected_descending):
    db.session.add(Fields(key="name", type="string"))
    db.session.add(Fields(key="age", type="integer"))
    db.session.add(Fields(key="score", type="integer"))
    db.session.add(Fields(key="created_at", type="date"))
    db.session.commit()

    key, descending = service._parse_sort(sort_str)

    assert key == expected_key
    assert descending == expected_descending

@pytest.mark.parametrize(
    ("sort_str",),
    [
        ("-unknown_field",),
        ("unknown_field",),
    ],
)
def test_parse_sort_nonexistent(service, sort_str):
    with pytest.raises(ValidationError):
        service._parse_sort(sort_str)


# _condition tests
@pytest.mark.parametrize(
    ("field_type", "operator", "value"),
    [
        ("integer", "eq", "10"),
        ("string", "neq", "Alice"),
        ("integer", "gt", "5"),
        ("float", "gte", "1.5"),
        ("date", "lt", "2024-01-01"),
        ("integer", "lte", "100"),
        ("string", "contains", "ali"),
        ("integer", "in", "1,2,3"),
        ("string", "is_null", "true"),
    ],
)
def test_condition_success(service, field_type, operator, value):
    value_alias = aliased(RecordValues)
    condition = service._condition(value_alias, field_type, operator, value)

    assert condition is not None

@pytest.mark.parametrize(
    ("field_type", "operator", "value"),
    [
        ("integer", "eq", "not-an-integer"),
        ("float", "gte", "not-a-float"),
        ("date", "lt", "not-a-date"),
    ],
)
def test_condition_invalid_type(service, field_type, operator, value):
    value_alias = aliased(RecordValues)

    with pytest.raises(ValidationError):
        service._condition(value_alias, field_type, operator, value)


# _convert_type tests
@pytest.mark.parametrize(
    ("field_type", "raw_value", "expected"),
    [
        ("string", 123, "123"),
        ("text", "hello", "hello"),
        ("integer", "42", 42),
        ("float", "3.14", 3.14),
        ("boolean", "true", True),
        ("boolean", "false", False),
        ("date", "2024-01-15", date(2024, 1, 15)),
        ("list", "prod", "prod"),
    ],
)
def test_convert_type_success(service_no_db, field_type, raw_value, expected):
    result = service_no_db._convert_type(field_type, raw_value)

    if field_type == "float":
        assert result == pytest.approx(expected)
    else:
        assert result == expected

@pytest.mark.parametrize(
    ("field_type", "raw_value"),
    [
        ("integer", "abc"),
        ("float", "abc"),
        ("date", "15-01-2024"),
    ],
)
def test_convert_type_invalid_type(service_no_db, field_type, raw_value):
    with pytest.raises(ValidationError):
        service_no_db._convert_type(field_type, raw_value)


# _serialize_record tests
@pytest.mark.parametrize(
    ("values", "expected_values"),
    [
        ({"name": "Alice", "age": 30}, {"values": {"name": "Alice", "age": 30}}),
        ({"description": "A sample record"}, {"values": {"description": "A sample record"}}),
        ({"score": 10, "environment": "prod"}, {"values": {"score": 10, "environment": "prod"}}),
    ],
)
def test_serialize_record_success(service, values, expected_values):
    name_field = Fields(key="name", type="string")
    age_field = Fields(key="age", type="integer")
    due_field = Fields(key="due", type="date")
    desc_field = Fields(key="description", type="text")
    score_field = Fields(key="score", type="integer")
    env_field = Fields(key="environment", type="list", options=["prod", "dev"])
    db.session.add_all([name_field, age_field, due_field, desc_field, score_field, env_field])
    db.session.commit()

    created = service.create_record(values)
    result = service._serialize_record(created["record_id"])

    assert result["record_id"] == created["record_id"]
    assert result["values"] == expected_values["values"]

def test_serialize_record_nonexistent(service):
    result = service._serialize_record("nonexistent-record")

    assert result == {"record_id": "nonexistent-record", "values": {}}