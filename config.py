import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


load_dotenv()


def build_database_uri() -> str:
    """Build a SQLAlchemy URI from environment variables without exposing secrets."""
    driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.getenv("DB_SERVER", "localhost")
    database = os.getenv("DB_NAME", "sports_field_booking")
    username = os.getenv("DB_USERNAME", "")
    password = os.getenv("DB_PASSWORD", "")
    trusted_connection = os.getenv("DB_TRUSTED_CONNECTION", "yes").lower() == "yes"
    trust_server_certificate = os.getenv(
        "DB_TRUST_SERVER_CERTIFICATE", "yes"
    ).lower() == "yes"

    connection_parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
    ]

    if trusted_connection:
        connection_parts.append("Trusted_Connection=yes")
    else:
        connection_parts.extend([f"UID={username}", f"PWD={password}"])

    if trust_server_certificate:
        connection_parts.append("TrustServerCertificate=yes")

    connection_string = ";".join(connection_parts)
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}"


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
}
