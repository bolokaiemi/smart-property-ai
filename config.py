"""
Smart Property AI application configuration.

Environment values are loaded from the project .env file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def get_boolean(
    variable_name: str,
    default: bool = False,
) -> bool:
    """Convert an environment variable into a Boolean value."""

    value = os.getenv(
        variable_name,
        str(default),
    )

    return value.strip().lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


class Settings:
    """Central application configuration."""

    APP_NAME: str = os.getenv(
        "APP_NAME",
        "Smart Property AI",
    )

    APP_VERSION: str = os.getenv(
        "APP_VERSION",
        "1.0.0",
    )

    ENVIRONMENT: str = os.getenv(
        "ENVIRONMENT",
        "development",
    ).strip().lower()

    DEBUG: bool = get_boolean(
        "DEBUG",
        True,
    )

    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "development-only-secret-change-this",
    )

    SESSION_COOKIE_NAME: str = os.getenv(
        "SESSION_COOKIE_NAME",
        "smart_property_session",
    )

    SESSION_MAX_AGE: int = int(
        os.getenv(
            "SESSION_MAX_AGE",
            str(60 * 60 * 24 * 7),
        )
    )

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'smart_property.db'}",
    )

    DEFAULT_LANGUAGE: str = os.getenv(
        "DEFAULT_LANGUAGE",
        "en",
    )

    DEFAULT_CURRENCY: str = os.getenv(
        "DEFAULT_CURRENCY",
        "EUR",
    )

    MAX_UPLOAD_SIZE_MB: int = int(
        os.getenv(
            "MAX_UPLOAD_SIZE_MB",
            "10",
        )
    )

    UPLOADS_DIR: Path = BASE_DIR / "uploads"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    STATIC_DIR: Path = BASE_DIR / "static"
    LOGS_DIR: Path = BASE_DIR / "logs"
    MODEL_DIR: Path = BASE_DIR / "model_artifacts"

    ALLOWED_IMAGE_TYPES: set[str] = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    ALLOWED_DOCUMENT_TYPES: set[str] = {
        "application/pdf",
        "image/jpeg",
        "image/png",
    }

    SMTP_HOST: str = os.getenv(
        "SMTP_HOST",
        "",
    )

    SMTP_PORT: int = int(
        os.getenv(
            "SMTP_PORT",
            "587",
        )
    )

    SMTP_USERNAME: str = os.getenv(
        "SMTP_USERNAME",
        "",
    )

    SMTP_PASSWORD: str = os.getenv(
        "SMTP_PASSWORD",
        "",
    )

    SMTP_FROM_EMAIL: str = os.getenv(
        "SMTP_FROM_EMAIL",
        "",
    )

    SMTP_USE_TLS: bool = get_boolean(
        "SMTP_USE_TLS",
        True,
    )

    WHATSAPP_ACCESS_TOKEN: str = os.getenv(
        "WHATSAPP_ACCESS_TOKEN",
        "",
    )

    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv(
        "WHATSAPP_PHONE_NUMBER_ID",
        "",
    )

    PHONE_PROVIDER_ACCOUNT_ID: str = os.getenv(
        "PHONE_PROVIDER_ACCOUNT_ID",
        "",
    )

    PHONE_PROVIDER_AUTH_TOKEN: str = os.getenv(
        "PHONE_PROVIDER_AUTH_TOKEN",
        "",
    )

    AI_MODEL_PATH: Path = Path(
        os.getenv(
            "AI_MODEL_PATH",
            str(MODEL_DIR / "exported_model"),
        )
    )

    AI_TOKENIZER_PATH: Path = Path(
        os.getenv(
            "AI_TOKENIZER_PATH",
            str(MODEL_DIR / "tokenizer"),
        )
    )

    AI_MAX_INPUT_LENGTH: int = int(
        os.getenv(
            "AI_MAX_INPUT_LENGTH",
            "512",
        )
    )

    AI_MAX_OUTPUT_LENGTH: int = int(
        os.getenv(
            "AI_MAX_OUTPUT_LENGTH",
            "256",
        )
    )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def create_directories(self) -> None:
        """Create the directories required by the application."""

        directories = [
            self.UPLOADS_DIR,
            self.UPLOADS_DIR / "properties",
            self.UPLOADS_DIR / "documents",
            self.UPLOADS_DIR / "maintenance",
            self.UPLOADS_DIR / "complaints",
            self.UPLOADS_DIR / "profiles",
            self.LOGS_DIR,
            self.MODEL_DIR,
        ]

        for directory in directories:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

    def validate(self) -> None:
        """Validate security-sensitive production settings."""

        if (
            self.is_production
            and self.SECRET_KEY
            == "development-only-secret-change-this"
        ):
            raise RuntimeError(
                "A secure SECRET_KEY must be configured "
                "in production."
            )


settings = Settings()
settings.validate()
settings.create_directories()