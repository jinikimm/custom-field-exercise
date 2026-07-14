# Custom Fields Data API

Backend service that allows users to define custom fields at runtime, store records with those fields, and query with type-aware sorting and filtering.

## 1) Build and run locally

Prerequisites:
- Python 3.11+
- PostgreSQL 15+

Install and run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export FLASK_APP=app:create_app

flask db upgrade

python -m app.main
```

Default API port: 8080

## 2) Run with Docker / docker-compose

```bash
docker compose up --build app db
```

Compose startup command runs DB migration first:
- flask db upgrade
- python -m app.main

### Example usage

```bash
# Define fields
curl -X POST http://localhost:8080/fields -H "Content-Type: application/json" \
  -d '{"key":"risk_score","type":"float"}'

curl -X POST http://localhost:8080/fields -H "Content-Type: application/json" \
  -d '{"key":"environment","type":"list","options":["production","staging","lab"]}'

curl -X POST http://localhost:8080/fields -H "Content-Type: application/json" \
  -d '{"key":"firmware_version","type":"string"}'

curl -X POST http://localhost:8080/fields -H "Content-Type: application/json" \
  -d '{"key":"end_of_life","type":"date"}'

# Get all fileds
curl http://localhost:8080/fields

# Create records
curl -X POST http://localhost:8080/records -H "Content-Type: application/json" \
  -d '{"values":{"risk_score":8.1,"environment":"production","firmware_version":"1.2.3"}}'

curl -X POST http://localhost:8080/records -H "Content-Type: application/json" \
  -d '{"values":{"risk_score":2.5,"environment":"staging","firmware_version":"2.0.0"}}'

curl -X POST http://localhost:8080/records -H "Content-Type: application/json" \
  -d '{"values":{"risk_score":9.5,"environment":"production","end_of_life":"2026-12-31"}}'

# Get all records
curl http://localhost:8080/records

# Sort numerically descending
curl "http://localhost:8080/records?sort=-risk_score"

# Filter: risk_score >= 7 AND environment in {production,staging}
curl "http://localhost:8080/records?filter=risk_score:gte:7&filter=environment:in:production,staging"

# Pagination
curl "http://localhost:8080/records?limit=10&offset=0"
```

## 3) Required environment variables and defaults

- DB_HOST: localhost
- DB_PORT: 5433
- DB_NAME: custom_field_db
- DB_USER: custom_field_user
- DB_PASSWORD: custom_field_pass
- PORT: 8080

In docker-compose, DB_HOST is set to db and DB_PORT is 5432.

## 4) Database setup / migration

This project uses Flask-Migrate (Alembic). Migration files are included in migrations/versions/.

Apply schema:

```bash
export FLASK_APP=app:create_app
flask db upgrade
```

## 5) Run tests

```bash
docker compose run --rm test
```

Or locally:

```bash
pytest tests/test_api.py tests/test_unit.py --cov=app
```

Tests use in-memory SQLite and do not require PostgreSQL.

## 6) Storage model and design rationale

**Model: EAV (Entity-Attribute-Value) with typed columns**

The service uses a two-table structure:
- `fields`: stores field definitions (key, type, options)
- `record_values`: stores actual values with one typed column per supported type; `record_id` (UUID) serves as the record identifier and is part of the composite primary key `(record_id, field_id)`

Each row in `record_values` populates exactly one type-specific column (`string_value`, `integer_value`, `float_value`, etc.) based on the field's type. This approach is a hybrid EAV model with typed storage.

**Why this model:**
- **Type-aware sorting and filtering**: Using typed columns allows the database to natively sort and compare values correctly (numeric 2 < 10, not lexical "10" < "2").
- **Type safety at storage layer**: Invalid values are rejected at insertion time.
- **Multi-field filtering**: JOIN one `record_values` alias per filter, allowing AND combinations across multiple custom fields.

**Trade-offs:**
- More complex queries (requires JOINs and aliases for each filter/sort field).
- Sparse storage (most type columns are NULL in each row).

**Alternatives considered:**
- Pure JSONB: simpler queries but loses native type-aware sorting/filtering, requires casting and GIN indexes.
- Dynamic table columns: not viable for runtime-defined schemas.
- Type-specific views: can simplify queries for each value type, but adds maintenance overhead and still requires multiple joins for cross-type, multi-field filtering.

## 7) Filter wire format

Filters use the format: `key:operator:value`

Multiple filters are combined with AND logic by repeating the `filter` parameter:

```
filter=risk_score:gte:7&filter=environment:in:production,staging
```

**Supported operators:**

| Operator | Meaning | Valid for |
|---|---|---|
| `eq` | Equals | all types |
| `neq` | Not equals | all types |
| `gt`, `gte`, `lt`, `lte` | Ordered comparison | integer, float, date |
| `contains` | Substring match | string, text |
| `in` | Value in comma-separated list | string, list, integer |
| `is_null` | Field absent/null (value: true/false) | all types |

**Date format:** ISO 8601 (`YYYY-MM-DD`), e.g., `2026-12-31`

**Examples:**
```
filter=risk_score:gte:7.0
filter=environment:in:production,staging
filter=firmware_version:contains:rc
filter=end_of_life:lt:2027-01-01
filter=description:is_null:false
```

## 8) Null-ordering and missing values

**Sort behavior:**
- Records with missing (null) values for the sort field appear **last** (NULLS LAST).
- Ties are broken by `record_id` ascending for stable ordering.

**Filter behavior:**
- Most operators (eq, gt, contains, etc.) exclude records with null values for that field.
- Use `is_null:true` to explicitly match records missing a field value.
- Use `is_null:false` to match only records with non-null values.

## 9) Assumptions and shortcuts

- Authentication, authorization, and multi-tenancy are out of scope.
- Field definitions cannot be modified after creation.
- Records must contain at least one field value because there is no separate `records` table.
- List fields are single-select only.
- Pagination uses offset/limit, and tests use SQLite while the service uses PostgreSQL.

## 10) Improvements with more time

- Add update and delete APIs for fields and records.
- Multi-select list (a field holding several option values) and in/contains semantics for it.
- Full-text search on text fields.
- Unique / required constraints declared on a field definition.
- Multi-tenancy (records and fields scoped per tenant).
- Cursor-based pagination stable under concurrent inserts.
- Indexing strategy that makes sort + filter on a hot custom field fast; show the query plan.
- OpenAPI / Swagger specification.
