
from datetime import datetime

from sqlalchemy.orm import aliased
from app.models import db, Fields, Records, RecordValues
from app.error_handler import ConflictError, ValidationError


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

        field = Fields(
            key=data['key'],
            type=data['type'],
            options=data.get('options')
        )
        db.session.add(field)
        db.session.commit()

        return field

    def _validate_field(self, data):
        key = data.get('key')
        type = data.get('type')
        options = data.get('options')

        if not key:
            raise ValidationError(details=[{"field": "key", "message": "key is required and cannot be empty."}])
        if type not in TYPE_COLUMNS:
            raise ValidationError(details=[{"field": "type", "message": f"type must be one of {list(TYPE_COLUMNS.keys())}."}])
        if type == 'list':
            if options is None or not isinstance(options, list) or len(options) == 0:
                raise ValidationError(details=[{"field": "options", "message": "options must be a non-empty list for type 'list'."}])
        else:
            if options is not None:
                raise ValidationError(details=[{"field": "options", "message": "options must be null for non-list types."}])

        if Fields.query.filter_by(key=key).first():
            raise ConflictError(details=[{"field": "key", "message": f"Field with key '{key}' already exists."}])

    def get_fields(self):
        return Fields.query.all()

    def create_record(self, values_dict):
        record = Records()
        db.session.add(record)
        db.session.flush()
        
        for key, value in values_dict.items():
            field = Fields.query.filter_by(key=key).first()
            value = self._validate_record(key, value, field)
            record_value = RecordValues(record_id=record.id, field_id=field.id)

            if field.type == 'string':
                record_value.string_value = value
            elif field.type == 'text':
                record_value.text_value = value
            elif field.type == 'integer':
                record_value.integer_value = value
            elif field.type == 'float':
                record_value.float_value = value
            elif field.type == 'boolean':
                record_value.boolean_value = value
            elif field.type == 'date':
                record_value.date_value = value
            elif field.type == 'list':
                record_value.list_value = value
            
            db.session.add(record_value)
        
        db.session.commit()
        return self._serialize_record(record)

    def _validate_record(self, key, value, field):
        if not field:
            raise ValidationError(details=[{"field": f"values.{key}", "message": f"Field '{key}' does not exist."}])
        try:
            converted_value = self._convert_type(field.type, value)
        except ValueError as e:
            raise ValidationError(details=[{"field": f"values.{key}", "message": str(e)}])
        if field.type == 'list' and converted_value not in field.options:
            raise ValidationError(details=[{"field": f"values.{key}", "message": f"Value '{converted_value}' is not a valid option for field '{key}'."}])

        return converted_value

    def get_records(self, limit=50, offset=0, sort=None, filters=None):
        records_query = Records.query

        if filters:
            records_query = self._filter_records(records_query, filters)
        if sort:
            records_query = self._sort_records(records_query, sort)

        total = records_query.count()
        records = records_query.offset(offset).limit(limit).all()
        
        return {
            "items": [self._serialize_record(record) for record in records],
            "limit": limit,
            "offset": offset,
            "total": total
        }

    
    def _filter_records(self, records_query, filters):
        '''
        JOIN record_values AS value1
        ON value1.record_id = records.id
        AND value1.field_id = <field ID 1>

        JOIN record_values AS value2
        ON value2.record_id = records.id
        AND value2.field_id = <field ID 2>

        WHERE <value 조건 1>
        AND <value 조건 2>
        '''

        for filter in filters:
            key, operator, value = self._parse_filter(filter)
            field = Fields.query.filter_by(key=key).first()

            value_alias = aliased(RecordValues)

            records_query = records_query.outerjoin(
                value_alias,
                (value_alias.record_id == Records.id)
                & (value_alias.field_id == field.id))
            
            records_query = records_query.filter(
                self._condition(value_alias, field.type, operator, value)
            )

        return records_query
    
    def _sort_records(self, records_query, sort):
        '''        
        LEFT OUTER JOIN record_values AS sort_value
        ON sort_value.record_id = records.id
        AND sort_value.field_id = <field ID>

        ORDER BY
        sort_value.<field value> DESC NULLS LAST,
        records.id ASC
        '''

        key, descending = self._parse_sort(sort)
        field = Fields.query.filter_by(key=key).first()

        value_alias = aliased(RecordValues)

        records_query = records_query.outerjoin(
            value_alias,
            (value_alias.record_id == Records.id)
            & (value_alias.field_id == field.id)
        )

        col_name = TYPE_COLUMNS[field.type]
        col_value = getattr(value_alias, col_name)

        if descending:
            records_query = records_query.order_by(
                col_value.desc().nullslast(),
                Records.id.asc()
            )
        else:
            records_query = records_query.order_by(
                col_value.asc().nullslast(),
                Records.id.asc()
            )

        return records_query

    def _parse_filter(self, filter_text):
        key, operator, value = filter_text.split(":", 2)

        field = Fields.query.filter_by(key=key).first()
        if field is None:
            raise ValidationError(details=[{"field": "filter", "message": f"Field '{key}' does not exist."}])
        if operator not in ALLOWED_OPERATORS[field.type]:
            raise ValidationError(details=[{"field": "filter", "message": f"Operator '{operator}' is not valid for field '{key}'."}])

        return key, operator, value

    def _parse_sort(self, sort_text):
        descending = sort_text.startswith("-")
        key = sort_text[1:] if descending else sort_text
        
        field = Fields.query.filter_by(key=key).first()
        if field is None:
            raise ValidationError(details=[{"field": "sort", "message": f"Field '{key}' does not exist."}])

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
                return value.lower() == "true"
            elif type == "date":
                return datetime.strptime(value, "%Y-%m-%d").date()
            else:
                return value
        except Exception as e:
            raise ValidationError(details=[{"field": f"type", "message": f"Value '{value}' is not valid for type '{type}'."}])

    def _serialize_record(self, record):
        values = {}

        for value in record.values:
            field = Fields.query.get(value.field_id)
            col_name = TYPE_COLUMNS[field.type]
            val = getattr(value, col_name)
            
            if field.type == "date" and val:
                values[field.key] = val.isoformat()
            else:
                values[field.key] = val

        return {
            "record_id": record.id,
            "values": values
        }