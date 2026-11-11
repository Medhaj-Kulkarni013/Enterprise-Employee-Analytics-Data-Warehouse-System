
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


def get_database_config():
    """Return MySQL configuration with SSL support."""

    # Support existing DB_ names and MYSQL_ names
    host = os.getenv("DB_HOST") or os.getenv("MYSQL_HOST")
    port = os.getenv("DB_PORT") or os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("DB_USER") or os.getenv("MYSQL_USER")
    password = os.getenv("DB_PASSWORD") or os.getenv("MYSQL_PASSWORD")

    database = (
        os.getenv("OLTP_DB_NAME")
        or os.getenv("DB_NAME")
        or os.getenv("MYSQL_DATABASE")
        or "oltp"
    )

    ca_cert = (
        os.getenv("MYSQL_CA_CERT")
        or os.getenv("DB_SSL_CA")
    )

    missing = [
        name
        for name, value in {
            "DB_HOST": host,
            "DB_USER": user,
            "DB_PASSWORD": password,
            "MYSQL_CA_CERT": ca_cert,
        }.items()
        if not value
    ]

    if missing:
        raise ValueError(
            f"Missing database configuration: {', '.join(missing)}"
        )

    certificate_path = Path(ca_cert)

    if not certificate_path.is_absolute():
        certificate_path = PROJECT_ROOT / certificate_path

    if not certificate_path.is_file():
        raise FileNotFoundError(
            f"CA certificate not found: {certificate_path}"
        )

    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "database": database,
        "ssl_ca": str(certificate_path),
    }
