import os

class Config:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5433")
    DB_NAME = os.getenv("DB_NAME", "custom_field_db")
    DB_USER = os.getenv("DB_USER", "custom_field_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "custom_field_pass")
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PORT = int(os.getenv("PORT", 8080))
