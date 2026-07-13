from uuid import uuid4
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Fields(db.Model):
    __tablename__ = "fields"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    key = db.Column(db.String(128), nullable=False, unique=True)
    type = db.Column(db.String(32), nullable=False)
    options = db.Column(db.JSON, nullable=True)

    def _to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "type": self.type,
            "options": self.options
        }

class Records(db.Model):  
    __tablename__ = "records"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    values = db.relationship("RecordValues", cascade="all, delete-orphan")

class RecordValues(db.Model):
    __tablename__ = "record_values"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    record_id = db.Column(db.String(36), db.ForeignKey("records.id"), nullable=False)
    field_id = db.Column(db.String(36), db.ForeignKey("fields.id"), nullable=False)
    
    string_value = db.Column(db.String(255), nullable=True)
    text_value = db.Column(db.Text, nullable=True)
    integer_value = db.Column(db.Integer, nullable=True)
    float_value = db.Column(db.Float, nullable=True)
    boolean_value = db.Column(db.Boolean, nullable=True)
    date_value = db.Column(db.Date, nullable=True)
    list_value = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("record_id", "field_id", name="uq_record_field"),
    )

