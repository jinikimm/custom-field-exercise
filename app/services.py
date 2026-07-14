from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import aliased

from app.error_handler import ConflictError, ValidationError
from app.models import Fields, RecordValues, db

TYPE_COLUMNS = {
    "string": "string_value",
    "text": "text_value",
    "integer": "integer_value",
    "float": "float_value",
    "boolean": "boolean_value",
    "date": "date_value",
    "list": "list_value",
}

ALLOWED_OPERATORS = {
    "string": {"eq", "neq", "contains", "in", "is_null"},
    "text": {"eq", "neq", "contains", "is_null"},
    "integer": {"eq", "neq", "gt", "gte", "lt", "lte", "in", "is_null"},
    "float": {"eq", "neq", "gt", "gte", "lt", "lte", "is_null"},
    "boolean": {"eq", "neq", "is_null"},
    "date": {"eq", "neq", "gt", "gte", "lt", "lte", "is_null"},
    "list": {"eq", "neq", "in", "is_null"},
}


class CustomFieldService:
    def create_field(self, data):
        self._validate_field(data)

        field = Fields(key=data["key"], type=data["type"], options=data.get("options"))
        db.session.add(field)
        db.session.commit()

        return field

    def get_fields(self):
        return Fields.query.all()

    def create_record(self, values_dict):
        record_id = str(uuid4())

        for key, value in values_dict.items():
            field = Fields.query.filter_by(key=key).first()
            value = self._validate_record(key, value, field)

            record_value = RecordValues(record_id=record_id, field_id=field.field_id)
            col_name = TYPE_COLUMNS[field.type]
            setattr(record_value, col_name, value)

            db.session.add(record_value)

        db.session.commit()
        return self._serialize_record(record_id)

    def get_records(self, limit=50, offset=0, sort=None, filters=None):
        records_query = db.session.query(RecordValues.record_id).distinct()

        if filters:
            records_query = self._filter_records(records_query, filters)

        if sort:
            records_query = self._sort_records(records_query, sort)

        total = records_query.count()
        records = records_query.offset(offset).limit(limit).all()

        return {
            "items": [self._serialize_record(record.record_id) for record in records],
            "limit": limit,
            "offset": offset,
            "total": total,
        }

    def _filter_records(self, records_query, filters):
        for filter in filters:
            key, operator, value = self._parse_filter(filter)
            field = Fields.query.filter_by(key=key).first()

            value_alias = aliased(RecordValues)

            records_query = records_query.outerjoin(
                value_alias,
                (value_alias.record_id == RecordValues.record_id)
                & (value_alias.field_id == field.field_id),
            )

            records_query = records_query.filter(
                self._condition(value_alias, field.type, operator, value)
            )

        return records_query

    def _sort_records(self, records_query, sort):
        key, descending = self._parse_sort(sort)
        field = Fields.query.filter_by(key=key).first()

        value_alias = aliased(RecordValues)

        records_query = records_query.outerjoin(
            value_alias,
            (value_alias.record_id == RecordValues.record_id)
            & (value_alias.field_id == field.field_id),
        )

        col_name = TYPE_COLUMNS[field.type]
        col_value = getattr(value_alias, col_name)
        records_query = records_query.add_columns(col_value)

        if descending:
            records_query = records_query.order_by(
                col_value.desc().nullslast(), RecordValues.record_id.asc()
            )
        else:
            records_query = records_query.order_by(
                col_value.asc().nullslast(), RecordValues.record_id.asc()
            )

        return records_query

    def _parse_filter(self, filter_text):
        try:
            key, operator, value = filter_text.split(":", 2)
        except ValueError:
            raise ValidationError(
                details=[
                    {
                        "field": "filter",
                        "message": f"Filter '{filter_text}' is invalid format (not key:operator:value).",
                    }
                ]
            )

        field = Fields.query.filter_by(key=key).first()
        if field is None:
            raise ValidationError(
                details=[
                    {"field": "filter", "message": f"Field '{key}' does not exist."}
                ]
            )
        if operator not in ALLOWED_OPERATORS[field.type]:
            raise ValidationError(
                details=[
                    {
                        "field": "filter",
                        "message": f"Operator '{operator}' is not valid for field '{key}'.",
                    }
                ]
            )

        return key, operator, value

    def _parse_sort(self, sort_text):
        descending = sort_text.startswith("-")
        key = sort_text[1:] if descending else sort_text

        field = Fields.query.filter_by(key=key).first()
        if field is None:
            raise ValidationError(
                details=[{"field": "sort", "message": f"Field '{key}' does not exist."}]
            )

        return key, descending

    def _condition(self, value_alias, type, operator, value):
        col_name = TYPE_COLUMNS[type]
        col_value = getattr(value_alias, col_name)

        if operator == "in":
            if type == "integer":
                return col_value.in_([int(v) for v in value.split(",")])
            else:
                return col_value.in_(value.split(","))

        value = self._convert_type(type, value)

        if operator == "eq":
            return col_value == value
        elif operator == "neq":
            return col_value != value
        elif operator == "gt":
            return col_value > value
        elif operator == "gte":
            return col_value >= value
        elif operator == "lt":
            return col_value < value
        elif operator == "lte":
            return col_value <= value
        elif operator == "contains":
            return col_value.contains(value)
        elif operator == "is_null":
            if value:
                return col_value.is_(None)
            else:
                return col_value.isnot(None)

    def _convert_type(self, type, value):
        try:
            if type in ["string", "text"]:
                return str(value)
            elif type == "integer":
                return int(value)
            elif type == "float":
                return float(value)
            elif type == "boolean" and isinstance(value, str):
                if value.lower() == "true":
                    return True
                elif value.lower() == "false":
                    return False
                else:
                    raise ValueError(f"Value '{value}' is not valid for type '{type}'.")
            elif type == "date":
                return datetime.strptime(value, "%Y-%m-%d").date()
            else:
                return value
        except Exception as e:
            raise ValidationError(
                details=[
                    {
                        "field": f"{type}",
                        "message": f"Value '{value}' is not valid for type '{type}'.",
                    }
                ]
            )

    def _serialize_record(self, record_id):
        record_values = RecordValues.query.filter_by(record_id=record_id).all()
        values = {}

        for value in record_values:
            field = Fields.query.get(value.field_id)
            col_name = TYPE_COLUMNS[field.type]
            val = getattr(value, col_name)

            if field.type == "date" and val:
                values[field.key] = val.isoformat()
            else:
                values[field.key] = val

        return {"record_id": record_id, "values": values}

    def _validate_field(self, data):
        key = data.get("key")
        type = data.get("type")
        options = data.get("options")

        if not key:
            raise ValidationError(
                details=[
                    {"field": "key", "message": "key is required and cannot be empty."}
                ]
            )
        if type not in TYPE_COLUMNS:
            raise ValidationError(
                details=[
                    {
                        "field": "type",
                        "message": f"type must be one of {list(TYPE_COLUMNS.keys())}.",
                    }
                ]
            )
        if type == "list":
            if options is None or not isinstance(options, list) or len(options) == 0:
                raise ValidationError(
                    details=[
                        {
                            "field": "options",
                            "message": "options must be a non-empty list for type 'list'.",
                        }
                    ]
                )
        else:
            if options is not None:
                raise ValidationError(
                    details=[
                        {
                            "field": "options",
                            "message": "options must be null for non-list types.",
                        }
                    ]
                )

        if Fields.query.filter_by(key=key).first():
            raise ConflictError(
                details=[
                    {
                        "field": "key",
                        "message": f"Field with key '{key}' already exists.",
                    }
                ]
            )

    def _validate_record(self, key, value, field):
        if not field:
            raise ValidationError(
                details=[
                    {
                        "field": f"values.{key}",
                        "message": f"Field '{key}' does not exist.",
                    }
                ]
            )
        try:
            converted_value = self._convert_type(field.type, value)
        except ValueError as e:
            raise ValidationError(
                details=[{"field": f"values.{key}", "message": str(e)}]
            )
        if field.type == "list" and converted_value not in field.options:
            raise ValidationError(
                details=[
                    {
                        "field": f"values.{key}",
                        "message": f"Value '{converted_value}' is not a valid option for field '{key}'.",
                    }
                ]
            )

        return converted_value
