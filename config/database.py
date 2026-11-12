
import atexit
import os
from pathlib import Path
import tempfile

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

_temporary_certificates = []


def _streamlit_secret(name):
    """Read one Streamlit secret without requiring Streamlit deployment."""
    try:
        import streamlit as st
    except ImportError:
        return None

    try:
        return st.secrets[name]
    except (KeyError, FileNotFoundError):
        return None


def _setting(*names):
    """Read an environment setting, then fall back to Streamlit secrets."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value

    for name in names:
        value = _streamlit_secret(name)
        if value:
            return str(value)

    return None


def _certificate_path(certificate):
    """Resolve a local CA path or materialize PEM content from a secret."""
    if "-----BEGIN CERTIFICATE-----" in certificate:
        temporary_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".pem",
            encoding="utf-8",
            delete=False,
        )
        try:
            temporary_file.write(certificate)
        finally:
            temporary_file.close()

        _temporary_certificates.append(temporary_file.name)
        return temporary_file.name

    candidate = Path(certificate)
    if candidate.is_file():
        return str(candidate)

    raise FileNotFoundError(f"CA certificate not found: {candidate}")


def _cleanup_temporary_certificates():
    for path in _temporary_certificates:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass


atexit.register(_cleanup_temporary_certificates)


def get_database_config():
    """Return local or Streamlit-secret MySQL configuration with SSL."""

    host = _setting("DB_HOST", "MYSQL_HOST")
    port = _setting("DB_PORT", "MYSQL_PORT") or "3306"
    user = _setting("DB_USER", "MYSQL_USER")
    password = _setting("DB_PASSWORD", "MYSQL_PASSWORD")

    database = (
        _setting("OLTP_DB_NAME", "DB_NAME", "MYSQL_DATABASE")
        or "oltp"
    )

    ca_cert = _setting("MYSQL_CA_CERT", "DB_SSL_CA")

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

    certificate_path = _certificate_path(
        ca_cert if "-----BEGIN CERTIFICATE-----" in ca_cert
        else str(certificate_path)
    )

    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "database": database,
        "ssl_ca": str(certificate_path),
    }
