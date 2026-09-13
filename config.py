import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


load_dotenv()


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
    # MVP acceptance uses simulated payments only; environment cannot enable legacy MoMo.
    MOMO_ENABLED = False
    MOMO_PARTNER_CODE = os.getenv("MOMO_PARTNER_CODE", "")
    MOMO_ACCESS_KEY = os.getenv("MOMO_ACCESS_KEY", "")
    MOMO_SECRET_KEY = os.getenv("MOMO_SECRET_KEY", "")
    MOMO_BASE_URL = os.getenv(
        "MOMO_BASE_URL",
        "https://test-payment.momo.vn",
    )
    MOMO_REDIRECT_URL = os.getenv("MOMO_REDIRECT_URL", "")
    MOMO_IPN_URL = os.getenv("MOMO_IPN_URL", "")
    MOMO_TIMEOUT_SECONDS = int(os.getenv("MOMO_TIMEOUT_SECONDS", "30"))
    VNPAY_ENABLED = env_flag("VNPAY_ENABLED", False)
    VNPAY_TMN_CODE = os.getenv("VNPAY_TMN_CODE", "")
    VNPAY_HASH_SECRET = os.getenv("VNPAY_HASH_SECRET", "")
    VNPAY_PAYMENT_URL = os.getenv(
        "VNPAY_PAYMENT_URL",
        "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
    )
    VNPAY_API_URL = os.getenv(
        "VNPAY_API_URL",
        "https://sandbox.vnpayment.vn/merchant_webapi/api/transaction",
    )
    VNPAY_RETURN_URL = os.getenv("VNPAY_RETURN_URL", "")
    VNPAY_IPN_URL = os.getenv("VNPAY_IPN_URL", "")
    VNPAY_TIMEOUT_SECONDS = int(os.getenv("VNPAY_TIMEOUT_SECONDS", "30"))
    VNPAY_VERSION = os.getenv("VNPAY_VERSION", "2.1.0")
    VNPAY_LOCALE = os.getenv("VNPAY_LOCALE", "vn")
    VNPAY_REFUND_CREATE_BY = os.getenv("VNPAY_REFUND_CREATE_BY", "system")
    VNPAY_REFUND_IP_ADDR = os.getenv("VNPAY_REFUND_IP_ADDR", "127.0.0.1")
    MEDIA_MAX_PIXELS = 20_000_000
    MEDIA_ROOT = os.getenv("MEDIA_ROOT")
    MEDIA_MAX_BYTES = int(os.getenv("MEDIA_MAX_BYTES", str(5 * 1024 * 1024)))
    MAX_CONTENT_LENGTH = MEDIA_MAX_BYTES + 1024 * 1024
    GEOCODING_PROVIDER = os.getenv("GEOCODING_PROVIDER", "nominatim")
    NOMINATIM_BASE_URL = os.getenv(
        "NOMINATIM_BASE_URL",
        "https://nominatim.openstreetmap.org",
    )
    NOMINATIM_USER_AGENT = os.getenv(
        "NOMINATIM_USER_AGENT",
        "sports-field-booking-student-demo/1.0 "
        "(https://github.com/nguyenhuynguyenhuy195-creator/"
        "sports-field-booking-system)",
    )
    GEOCODING_TIMEOUT_SECONDS = float(
        os.getenv("GEOCODING_TIMEOUT_SECONDS", "5")
    )
    GEOCODING_CACHE_TTL_SECONDS = int(
        os.getenv("GEOCODING_CACHE_TTL_SECONDS", "86400")
    )
    MAP_TILE_URL = os.getenv(
        "MAP_TILE_URL",
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    )
    # --- Chatbot (RAG) -------------------------------------------------
    # Every default here is deliberately safe: the assistant stays OFF unless
    # it is explicitly enabled AND an API key is present. create_app() never
    # validates these, so a missing key degrades the chatbot to "unavailable"
    # instead of breaking Flask startup.
    CHATBOT_ENABLED = env_flag("CHATBOT_ENABLED", False)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    # gemini-2.5-flash-lite is retired: the API answers 404 "no longer
    # available to new users" and names gemini-3.5-flash-lite as the
    # replacement. Same flash-lite cost/latency tier, pinned (not a floating
    # -latest alias). Verified live 2026-09-13.
    CHATBOT_MODEL = os.getenv("CHATBOT_MODEL", "gemini-3.5-flash-lite")
    # Gemini 3.x replaced the numeric thinking_budget with thinking_level and
    # rejects the old field with 400. Blank omits the thinking config entirely,
    # which every tested model accepts.
    CHATBOT_THINKING_LEVEL = os.getenv("CHATBOT_THINKING_LEVEL", "low")
    CHATBOT_EMBEDDING_MODEL = os.getenv(
        "CHATBOT_EMBEDDING_MODEL",
        "gemini-embedding-001",
    )
    # gemini-embedding-001 supports Matryoshka truncation; 768 keeps the
    # in-memory index small without retraining anything.
    CHATBOT_EMBEDDING_DIMENSIONS = int(
        os.getenv("CHATBOT_EMBEDDING_DIMENSIONS", "768")
    )
    CHATBOT_CHUNK_SIZE = int(os.getenv("CHATBOT_CHUNK_SIZE", "1000"))
    CHATBOT_CHUNK_OVERLAP = int(os.getenv("CHATBOT_CHUNK_OVERLAP", "120"))
    CHATBOT_RETRIEVAL_TOP_K = int(os.getenv("CHATBOT_RETRIEVAL_TOP_K", "4"))
    # Cosine-similarity gates for the evidence check, calibrated 2026-09-13
    # against gemini-embedding-001 @768d over the current docs/chatbot/ set
    # using a 27-question Vietnamese benchmark. Measured best-score bands:
    #   relevant   0.769 - 0.870
    #   ambiguous  0.676 - 0.746
    #   unrelated  0.565 - 0.650
    # Gemini similarity has a high floor (nothing scored below 0.565 even for
    # completely off-topic questions), so a low threshold is close to noise.
    # 0.70 clears the whole unrelated band by 0.05 and sits 0.069 below the
    # weakest relevant question. Re-measure if the knowledge base or the
    # embedding model changes.
    CHATBOT_MIN_RELEVANCE_SCORE = float(
        os.getenv("CHATBOT_MIN_RELEVANCE_SCORE", "0.70")
    )
    CHATBOT_STRONG_RELEVANCE_SCORE = float(
        os.getenv("CHATBOT_STRONG_RELEVANCE_SCORE", "0.78")
    )
    CHATBOT_MAX_SOURCES = int(os.getenv("CHATBOT_MAX_SOURCES", "3"))
    CHATBOT_TIMEOUT_SECONDS = float(os.getenv("CHATBOT_TIMEOUT_SECONDS", "20"))
    # HTTP endpoint limits. The body cap is far below MAX_CONTENT_LENGTH, which
    # is sized for media uploads; a question plus eight turns of history is
    # small. The rate limit is per authenticated user, counted in-process.
    CHATBOT_MAX_REQUEST_BYTES = int(
        os.getenv("CHATBOT_MAX_REQUEST_BYTES", str(32 * 1024))
    )
    CHATBOT_RATE_LIMIT_PER_MINUTE = int(
        os.getenv("CHATBOT_RATE_LIMIT_PER_MINUTE", "12")
    )
    CHATBOT_RATE_LIMIT_WINDOW_SECONDS = int(
        os.getenv("CHATBOT_RATE_LIMIT_WINDOW_SECONDS", "60")
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
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
