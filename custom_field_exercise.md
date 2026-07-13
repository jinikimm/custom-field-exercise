# Cybellum – Backend Interview Exercise

## Interview Exercise
# Custom Fields Data API

Backend service exercise for user-defined data models and query APIs

| | |
|---|---|
| **Audience** | Backend developers joining a product security services / vulnerability assessment team |
| **Primary stack** | Python 3.11+, Flask, SQLAlchemy, Docker, PostgreSQL (SQLite acceptable for tests) |
| **Main signal** | Storage-model judgment for user-defined fields, type-aware sorting and filtering, clean API boundaries, validation, persistence, tests |

---

## Custom Fields Data API

Build an HTTP service, packaged as a Docker container, that lets a user **define their own fields** on a
record type at runtime, store records against those definitions, and query the records with **sorting and
filtering on any custom field**.

This simulates a product security workflow where every customer models their assets differently: one team
tracks an asset's `firmware_version` (string) and `risk_score` (float), another tracks `end_of_life` (date)
and `environment` (single-select list). The product cannot ship a fixed column per customer — fields are
defined by the user, and the data API must sort and filter over them correctly regardless of type.

### Timebox and submission
- **Expected time: 1 day.** Prioritize correctness, clarity, and tests over extra features.
- **Submission:** Git repository containing source code, Dockerfile, README, database setup script or
  migration, and tests.
- **Required stack:** Python 3.11 or newer, Flask, Docker, and a relational database. PostgreSQL is
  preferred. SQLite is acceptable for tests.
- It is acceptable to leave non-core items unfinished if the README clearly explains what remains and how
  you would complete it.

### Core goal
The service must let a user:
1. **Define custom fields** at runtime — each field has a key, a data type, and type-specific constraints.
2. **Create records** that carry values for those custom fields.
3. **List records with sorting and filtering** over any custom field, where ordering and comparisons are
   **type-aware** (numeric fields sort numerically, string fields lexically, dates chronologically).

**The storage model is deliberately left to you.** Treat it as the core design decision, not an afterthought.

### Out of scope for the core exercise
- Authentication and authorization.
- User interface.
- Multi-tenancy / per-customer isolation (mention how you would add it).
- Distributed workers or queues.
- Editing or versioning of a field definition's type after creation.

### Supported field types
Support at least the following types. `list` is a single-select value constrained to a fixed set of options
defined on the field.

| Type | Meaning | Example value |
|---|---|---|
| `string` | Short single-line text | `"1.2.3-rc1"` |
| `text` | Long free text (textbox) | `"notes about the asset..."` |
| `integer` | Whole number | `42` |
| `float` | Decimal number | `8.1` |
| `boolean` | True / false | `true` |
| `date` | Calendar date, ISO 8601 (`YYYY-MM-DD`) | `"2026-06-30"` |
| `list` | Single value from a fixed option set | `"production"` |

### Configuration
Configure the service using environment variables. Document defaults in the README.

| Variable | Required | Notes |
|---|---|---|
| `DB_HOST` | Yes | Database host. |
| `DB_PORT` | Yes | Database port. |
| `DB_NAME` | Yes | Database name. |
| `DB_USER` | Yes | Database user. |
| `DB_PASSWORD` | Yes | Database password. |
| `PORT` | Yes | HTTP port. Default to 8080 if not supplied. |
| `MAX_PAGE_SIZE` | No | Maximum records returned per page. Use a sensible default and document it. |

---

## HTTP API

### POST /fields
Define a new custom field.

```json
{
  "key": "risk_score",
  "type": "float",
  "options": null
}
```
For `type: "list"`, `options` is a required non-empty array of allowed string values, e.g.
`["production", "staging", "lab"]`. For all other types `options` must be null or omitted.

**201 Created**
```json
{ "field_id": "uuid", "key": "risk_score", "type": "float", "options": null }
```

- Reject a duplicate `key` with **409 Conflict**.
- Reject an unknown `type`, a missing/empty `key`, or a `list` field with empty/missing `options`, with
  **400 Bad Request**.

### GET /fields
List all defined custom fields.

### POST /records
Create a record with values for previously defined custom fields.

```json
{
  "values": {
    "firmware_version": "1.2.3",
    "risk_score": 8.1,
    "environment": "production",
    "end_of_life": "2026-12-31"
  }
}
```
- Every key in `values` must reference an existing field definition. Unknown keys → **400**.
- A value that is not compatible with its field's type (e.g. `"high"` for a `float`, a non-option for a
  `list`, a non-ISO string for a `date`) → **400** with a field-level message.
- Missing fields are allowed and stored as absent/null (do not require every field on every record).

**201 Created**
```json
{ "record_id": "uuid", "values": { "firmware_version": "1.2.3", "risk_score": 8.1, "...": "..." } }
```

### GET /records
List records with **sorting**, **filtering**, and **pagination**.

Query parameters:
- `sort` — a custom field key, optionally prefixed with `-` for descending. Example: `sort=-risk_score`.
  Ordering must be **type-aware**: `risk_score` (float) sorts `2.0 < 9.5 < 10.0`, not `"10.0" < "2.0"`.
  Records missing the sort field sort last (document your null-ordering choice).
- `filter` — one or more filter clauses, combined with **AND**. You may choose the exact wire format; a
  clear, documented shape is what matters. Recommended:
  `filter=risk_score:gte:7&filter=environment:in:production,staging&filter=firmware_version:contains:rc`
- `limit`, `offset` — pagination with a sensible default and a maximum.

Return a stable order (break ties on a deterministic secondary key such as `record_id`).

**200 OK**
```json
{
  "items": [
    { "record_id": "uuid", "values": { "firmware_version": "1.2.3", "risk_score": 8.1 } }
  ],
  "limit": 50,
  "offset": 0,
  "total": 1
}
```

### Supported filter operators
Each operator is valid only for certain types. Reject an operator used against an incompatible type with
**400** (e.g. `contains` on a `float`, `gt` on a `boolean`).

| Operator | Meaning | Valid for |
|---|---|---|
| `eq` / `neq` | Equals / not equals | all types |
| `gt` / `gte` / `lt` / `lte` | Ordered comparison | `integer`, `float`, `date` |
| `contains` | Substring match | `string`, `text` |
| `in` | Value is one of a comma-separated set | `string`, `list`, `integer` |
| `is_null` | Field absent / null (`true`/`false`) | all types |

### GET /health
Return a liveness/readiness response. At minimum return `{ "status": "ok" }`. A stronger implementation
also verifies database connectivity.

### Validation and error handling
Return useful, deterministic errors with a consistent schema. Recommended shape:
```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid record payload",
    "details": [
      { "field": "values.risk_score", "message": "risk_score must be a float" }
    ]
  }
}
```
Handle at least:
- Malformed JSON.
- Unknown or invalid field `type` on field creation.
- Duplicate field `key`.
- `list` field defined without `options`.
- Record value referencing an undefined field key.
- Record value incompatible with its field's type (number, date, boolean, list-option).
- `sort` referencing an undefined field key.
- Filter using an operator not valid for the target field's type.
- Filter referencing an undefined field key.
- Invalid `limit` / `offset`.

---

## Required tests
Include automated tests runnable from the command line (pytest or another documented runner).

1. Define fields of each supported type; duplicate key is rejected with 409.
2. `list` field without `options` is rejected; a record value outside the option set is rejected.
3. Create a record and read it back with its typed values intact.
4. Record with a value incompatible with its field type is rejected (400) — cover numeric, date, and list.
5. **Type-aware sort:** with values `2, 10, 9`, `sort=risk_score` returns `2, 9, 10` (numeric), not
   lexical `10, 2, 9`.
6. **Filtering:** `gte` on a numeric field, `contains` on a string field, `in` on a list field — each
   returns exactly the matching records.
7. **Combined filters** (AND across two different custom fields) return only records matching both.
8. Operator used against an incompatible type is rejected with 400 (e.g. `contains` on a float).
9. Pagination: `limit`/`offset` return the correct window and `total`, with a stable order.
10. Sorting or filtering on an undefined field key is rejected with 400.

---

## README requirements
- How to build and run the service locally.
- How to run with Docker, and docker-compose if provided.
- Required environment variables and defaults.
- Database setup or migration instructions.
- How to run tests.
- **Your storage model and why** — EAV vs JSONB vs typed columns; how it affects indexing, type-aware
  sorting, and multi-field filtering. This is the section reviewers will read most closely.
- The filter wire format you chose and its grammar.
- Null-ordering behavior for sort, and how missing values are treated in filters.
- Assumptions and shortcuts.
- What you would improve with more time.

## Bonus items
Not required for a strong submission. Attempt only after the core is correct and tested.
- Multi-select `list` (a field holding several option values) and `in`/`contains` semantics for it.
- Full-text search on `text` fields.
- Unique / required constraints declared on a field definition.
- Multi-tenancy (records and fields scoped per tenant).
- Cursor-based pagination stable under concurrent inserts.
- Indexing strategy that makes sort + filter on a hot custom field fast; show the query plan.
- OpenAPI / Swagger specification.
- Structured JSON logging with request IDs.

## Example usage
```bash
# Define fields
curl -X POST http://localhost:8080/fields -H "Content-Type: application/json" \
  -d '{"key":"risk_score","type":"float"}'
curl -X POST http://localhost:8080/fields -H "Content-Type: application/json" \
  -d '{"key":"environment","type":"list","options":["production","staging","lab"]}'

# Create records
curl -X POST http://localhost:8080/records -H "Content-Type: application/json" \
  -d '{"values":{"risk_score":8.1,"environment":"production"}}'

# Sort numerically, descending
curl "http://localhost:8080/records?sort=-risk_score"

# Filter: risk_score >= 7 AND environment in {production,staging}
curl "http://localhost:8080/records?filter=risk_score:gte:7&filter=environment:in:production,staging"
```
