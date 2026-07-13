from flask import Blueprint, jsonify, request
from app.services import CustomFieldService

def register_api(app):
    bp = Blueprint("custom_field", __name__)
    api = CustomFieldAPI(CustomFieldService())
    api.add_url_rules(bp)
    app.register_blueprint(bp)

class CustomFieldAPI():
    def __init__(self, service):
        self.service = service

    def create_field(self):
        data = request.get_json()
        field = self.service.create_field(data)
        return jsonify(field._to_dict()), 201
    
    def get_fields(self):
        fields = self.service.get_fields()
        return jsonify([f._to_dict() for f in fields]), 200

    def create_record(self):
        data = request.get_json()
        serialized_record = self.service.create_record(data.get('values', {}))
        return jsonify(serialized_record), 201
    
    def get_records(self):
        sort = request.args.get('sort')
        filters = request.args.getlist('filter')

        try:
            limit = int(request.args.get('limit', 50))
            offset = int(request.args.get('offset', 0))
        except ValueError:
            return jsonify({"error": "limit and offset must be integers"}), 400
        if limit < 0 or offset < 0:
            return jsonify({"error": "limit and offset must be non-negative"}), 400
        if limit > 100:
            return jsonify({"error": "limit exceeds maximum page size (100)"}), 400

        result = self.service.get_records(limit, offset, sort=sort, filters=filters)
        return jsonify(result), 200

    def add_url_rules(self, bp):
        bp.add_url_rule("/fields", view_func=self.create_field, methods=["POST"])
        bp.add_url_rule("/fields", view_func=self.get_fields, methods=["GET"])
        bp.add_url_rule("/records", view_func=self.create_record, methods=["POST"])
        bp.add_url_rule("/records", view_func=self.get_records, methods=["GET"])