import os
import secrets
from pathlib import Path
from datetime import timedelta

from sqlalchemy.engine import URL


def _environment_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise RuntimeError(f"{name} must be set to true or false.")
    return normalized == "true"


def load_config(instance_path: str) -> dict:
    environment = os.environ.get("CODEQUEST_ENV", "development").strip().lower()
    buddy_provider = os.environ.get("BUDDY_PROVIDER", "mock").strip().lower()
    database_path = os.environ.get("CODEQUEST_DATABASE_PATH")
    if database_path is None and environment != "production":
        database_path = str(Path(instance_path) / "codequest.sqlite3")

    return {
        "ENVIRONMENT": environment,
        "SECRET_KEY": os.environ.get("CODEQUEST_SECRET_KEY")
        or (None if environment == "production" else secrets.token_hex(32)),
        "DATABASE_PATH": database_path,
        "BUDDY_PROVIDER": buddy_provider,
        "BUDDY_GEMINI_ADULTS_ONLY": _environment_bool(
            "BUDDY_GEMINI_ADULTS_ONLY"
        ),
        "BUDDY_GEMINI_FREE_TIER_CONFIRMED": _environment_bool(
            "BUDDY_GEMINI_FREE_TIER_CONFIRMED"
        ),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": environment == "production",
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=12),
    }


def validate_config(config: dict) -> None:
    if config.get("BUDDY_PROVIDER") not in {"mock", "gemini"}:
        raise RuntimeError(
            "BUDDY_PROVIDER must be set to 'mock' or 'gemini'."
        )

    if config["ENVIRONMENT"] == "production" and not config["SECRET_KEY"]:
        raise RuntimeError(
            "CODEQUEST_SECRET_KEY must be set when CODEQUEST_ENV=production."
        )

    if config["ENVIRONMENT"] == "production":
        database_path = config.get("DATABASE_PATH")
        if not database_path or not Path(database_path).expanduser().is_absolute():
            raise RuntimeError(
                "CODEQUEST_DATABASE_PATH must be an absolute path "
                "when CODEQUEST_ENV=production."
            )


def configure_database(app) -> None:
    raw_path = app.config["DATABASE_PATH"]
    if not raw_path:
        raise RuntimeError("CODEQUEST_DATABASE_PATH must not be empty.")

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path(app.root_path).parent / path

    try:
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise RuntimeError("Unable to prepare the configured database directory.") from error

    app.config["DATABASE_PATH"] = str(path)
    app.config["SQLALCHEMY_DATABASE_URI"] = str(
        URL.create("sqlite", database=str(path))
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
