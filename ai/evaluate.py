"""
Model registry for Smart Property AI.

This module manages:

- Available AI models
- Model versions and providers
- Local model checkpoints
- Active model selection
- Supported languages and tasks
- Evaluation metrics
- Checkpoint integrity verification

Important:
Never store API keys, access tokens, passwords, cookies, or credentials
inside the model registry. Store secrets in environment variables.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import threading
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping


# ============================================================
# PATHS AND DEFAULT VALUES
# ============================================================

AI_DIRECTORY = Path(__file__).resolve().parent

DEFAULT_CHECKPOINT_DIRECTORY = AI_DIRECTORY / "checkpoints"

DEFAULT_REGISTRY_PATH = (
    DEFAULT_CHECKPOINT_DIRECTORY / "registry.json"
)

REGISTRY_VERSION = 1

DEFAULT_MODEL_ID = "smart-property-local-v1"


# ============================================================
# VALIDATION SETTINGS
# ============================================================

MODEL_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$"
)

VERSION_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9.+_-]{0,79}$"
)

SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")

SECRET_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "cookie",
    "authorization",
    "private_key",
)


# ============================================================
# EXCEPTIONS
# ============================================================

class ModelRegistryError(ValueError):
    """Base exception for model-registry errors."""


class ModelNotFoundError(ModelRegistryError):
    """Raised when a requested model is not registered."""


class DuplicateModelError(ModelRegistryError):
    """Raised when a model ID already exists."""


class InvalidCheckpointError(ModelRegistryError):
    """Raised when a checkpoint is missing or unsafe."""


# ============================================================
# ENUMS
# ============================================================

class ModelStatus(str, Enum):
    """Lifecycle state of a registered model."""

    REGISTERED = "registered"
    TRAINING = "training"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class ModelKind(str, Enum):
    """Type of AI model implementation."""

    RULE_BASED = "rule_based"
    CHAT_MODEL = "chat_model"
    FINE_TUNED = "fine_tuned"
    ADAPTER = "adapter"


class ModelProvider(str, Enum):
    """Location or provider type for a model."""

    LOCAL = "local"
    COMPATIBLE_API = "compatible_api"
    HUGGING_FACE = "huggingface"
    CUSTOM = "custom"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def utc_now() -> str:
    """Return the current UTC time in ISO format."""

    return datetime.now(timezone.utc).isoformat()


def normalize_string(
    value: Any,
    maximum_length: int,
) -> str:
    """Normalize a short registry text value."""

    text = " ".join(
        str(value or "")
        .replace("\x00", " ")
        .split()
    )

    if len(text) > maximum_length:
        raise ModelRegistryError(
            "A registry text field exceeds its allowed size."
        )

    return text


def normalize_list(
    values: Iterable[Any] | None,
    maximum_items: int = 50,
) -> tuple[str, ...]:
    """Normalize a list of language codes or task names."""

    if values is None:
        return ()

    normalized: list[str] = []

    for raw_value in values:
        value = normalize_string(
            raw_value,
            maximum_length=100,
        ).lower()

        if value and value not in normalized:
            normalized.append(value)

        if len(normalized) >= maximum_items:
            break

    return tuple(normalized)


def validate_model_id(model_id: str) -> str:
    """Validate and return a model ID."""

    value = str(model_id or "").strip()

    if not MODEL_ID_PATTERN.fullmatch(value):
        raise ModelRegistryError(
            "Model ID must start with a letter or number and "
            "contain only letters, numbers, dots, underscores, "
            "or hyphens."
        )

    return value


def validate_version(version: str) -> str:
    """Validate and return a model version."""

    value = str(version or "").strip()

    if not VERSION_PATTERN.fullmatch(value):
        raise ModelRegistryError(
            "The model version has an invalid format."
        )

    return value


def contains_secret_key(value: Any) -> bool:
    """
    Check recursively whether metadata contains secret-like keys.

    This prevents credentials from accidentally being written into
    registry.json.
    """

    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            normalized_key = (
                str(key)
                .strip()
                .lower()
                .replace("-", "_")
            )

            if any(
                fragment in normalized_key
                for fragment in SECRET_KEY_FRAGMENTS
            ):
                return True

            if contains_secret_key(nested_value):
                return True

    elif isinstance(value, (list, tuple, set)):
        return any(
            contains_secret_key(item)
            for item in value
        )

    return False


def validate_metadata(
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate registry metadata."""

    if metadata is None:
        return {}

    if not isinstance(metadata, Mapping):
        raise ModelRegistryError(
            "Model metadata must be a dictionary."
        )

    if contains_secret_key(metadata):
        raise ModelRegistryError(
            "Registry metadata must not contain API keys, "
            "tokens, passwords, cookies, private keys, "
            "credentials, or other secrets."
        )

    try:
        encoded = json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ModelRegistryError(
            "Registry metadata must be JSON serializable."
        ) from exc

    if len(encoded.encode("utf-8")) > 32_000:
        raise ModelRegistryError(
            "Registry metadata exceeds the size limit."
        )

    return json.loads(encoded)


def normalize_metrics(
    metrics: Mapping[str, Any] | None,
) -> dict[str, float]:
    """Validate and normalize evaluation metrics."""

    if metrics is None:
        return {}

    if not isinstance(metrics, Mapping):
        raise ModelRegistryError(
            "Model metrics must be a dictionary."
        )

    normalized: dict[str, float] = {}

    for raw_key, raw_value in metrics.items():
        key = (
            normalize_string(raw_key, 100)
            .lower()
            .replace(" ", "_")
        )

        if not key:
            continue

        try:
            number = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ModelRegistryError(
                f"Metric {key!r} must be numeric."
            ) from exc

        if not math.isfinite(number):
            raise ModelRegistryError(
                f"Metric {key!r} must be finite."
            )

        normalized[key] = number

    return normalized


def calculate_sha256(path: str | Path) -> str | None:
    """
    Calculate the SHA-256 checksum of a checkpoint file.

    A directory returns None because a model directory may contain
    several separate files.
    """

    checkpoint = Path(path)

    if not checkpoint.is_file():
        return None

    digest = hashlib.sha256()

    with checkpoint.open("rb") as file_handle:
        for chunk in iter(
            lambda: file_handle.read(1_048_576),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


# ============================================================
# MODEL RECORD
# ============================================================

@dataclass(frozen=True)
class ModelRecord:
    """Metadata describing one registered AI model."""

    model_id: str
    version: str

    provider: ModelProvider
    kind: ModelKind
    status: ModelStatus = ModelStatus.REGISTERED

    display_name: str | None = None
    model_name: str | None = None
    checkpoint_path: str | None = None
    checkpoint_sha256: str | None = None
    base_model: str | None = None

    languages: tuple[str, ...] = ("en",)
    tasks: tuple[str, ...] = ("property_assistant",)

    metrics: Mapping[str, float] = field(
        default_factory=dict
    )

    metadata: Mapping[str, Any] = field(
        default_factory=dict
    )

    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert the model record to JSON-compatible data."""

        data = asdict(self)

        data["provider"] = self.provider.value
        data["kind"] = self.kind.value
        data["status"] = self.status.value

        data["languages"] = list(self.languages)
        data["tasks"] = list(self.tasks)
        data["metrics"] = dict(self.metrics)
        data["metadata"] = dict(self.metadata)

        return data

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "ModelRecord":
        """Create a validated model record from registry data."""

        if not isinstance(data, Mapping):
            raise ModelRegistryError(
                "A model record must be a dictionary."
            )

        try:
            languages_data = data.get(
                "languages",
                ["en"],
            )

            tasks_data = data.get(
                "tasks",
                ["property_assistant"],
            )

            metrics_data = data.get(
                "metrics",
                {},
            )

            metadata_data = data.get(
                "metadata",
                {},
            )

            if not isinstance(
                languages_data,
                (list, tuple, set),
            ):
                raise ModelRegistryError(
                    "Model languages must be a list."
                )

            if not isinstance(
                tasks_data,
                (list, tuple, set),
            ):
                raise ModelRegistryError(
                    "Model tasks must be a list."
                )

            return cls(
                model_id=validate_model_id(
                    str(data["model_id"])
                ),
                version=validate_version(
                    str(data["version"])
                ),
                provider=ModelProvider(
                    str(data["provider"])
                ),
                kind=ModelKind(
                    str(data["kind"])
                ),
                status=ModelStatus(
                    str(
                        data.get(
                            "status",
                            ModelStatus.REGISTERED.value,
                        )
                    )
                ),
                display_name=(
                    str(data["display_name"])
                    if data.get("display_name")
                    else None
                ),
                model_name=(
                    str(data["model_name"])
                    if data.get("model_name")
                    else None
                ),
                checkpoint_path=(
                    str(data["checkpoint_path"])
                    if data.get("checkpoint_path")
                    else None
                ),
                checkpoint_sha256=(
                    str(data["checkpoint_sha256"])
                    if data.get("checkpoint_sha256")
                    else None
                ),
                base_model=(
                    str(data["base_model"])
                    if data.get("base_model")
                    else None
                ),
                languages=normalize_list(
                    languages_data
                ) or ("en",),
                tasks=normalize_list(
                    tasks_data
                ) or ("property_assistant",),
                metrics=normalize_metrics(
                    metrics_data
                ),
                metadata=validate_metadata(
                    metadata_data
                ),
                created_at=str(
                    data.get("created_at") or utc_now()
                ),
                updated_at=str(
                    data.get("updated_at") or utc_now()
                ),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            if isinstance(exc, ModelRegistryError):
                raise

            raise ModelRegistryError(
                "Invalid model record in registry."
            ) from exc


# ============================================================
# MODEL REGISTRY
# ============================================================

class ModelRegistry:
    """
    Thread-safe JSON-based model registry.

    Local model checkpoints are restricted to the configured
    checkpoint directory.
    """

    def __init__(
        self,
        registry_path: str | Path = DEFAULT_REGISTRY_PATH,
        checkpoint_directory: str | Path = (
            DEFAULT_CHECKPOINT_DIRECTORY
        ),
    ) -> None:
        self.registry_path = Path(
            registry_path
        ).resolve()

        self.checkpoint_directory = Path(
            checkpoint_directory
        ).resolve()

        self._lock = threading.RLock()

    def _empty_registry(self) -> dict[str, Any]:
        """Return the initial registry structure."""

        return {
            "registry_version": REGISTRY_VERSION,
            "active_model_id": None,
            "models": [],
            "updated_at": utc_now(),
        }

    def _load_data(self) -> dict[str, Any]:
        """Load the registry from disk."""

        if not self.registry_path.exists():
            return self._empty_registry()

        try:
            with self.registry_path.open(
                "r",
                encoding="utf-8",
            ) as file_handle:
                data = json.load(file_handle)

        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ModelRegistryError(
                "The model registry could not be read."
            ) from exc

        if not isinstance(data, dict):
            raise ModelRegistryError(
                "The model registry must contain an object."
            )

        models = data.get("models")

        if not isinstance(models, list):
            raise ModelRegistryError(
                "The registry models field must be a list."
            )

        try:
            registry_version = int(
                data.get("registry_version", 0)
            )
        except (TypeError, ValueError) as exc:
            raise ModelRegistryError(
                "The model registry version is invalid."
            ) from exc

        if registry_version != REGISTRY_VERSION:
            raise ModelRegistryError(
                "Unsupported model-registry version."
            )

        return data

    def _write_data(
        self,
        data: Mapping[str, Any],
    ) -> None:
        """
        Write registry data atomically.

        A temporary file is written first and then replaces the
        original registry file.
        """

        self.registry_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        content = (
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.registry_path.name}.",
            suffix=".tmp",
            dir=str(self.registry_path.parent),
            text=True,
        )

        try:
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as file_handle:
                file_handle.write(content)
                file_handle.flush()
                os.fsync(file_handle.fileno())

            os.replace(
                temporary_name,
                self.registry_path,
            )

        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass

            raise

    def _records(
        self,
        data: Mapping[str, Any],
    ) -> list[ModelRecord]:
        """Convert stored model dictionaries to records."""

        models = data.get("models", [])

        if not isinstance(models, list):
            raise ModelRegistryError(
                "Registry models must be a list."
            )

        records: list[ModelRecord] = []

        for model_data in models:
            if not isinstance(model_data, Mapping):
                raise ModelRegistryError(
                    "The registry contains an invalid model record."
                )

            records.append(
                ModelRecord.from_dict(model_data)
            )

        return records

    def _safe_checkpoint(
        self,
        checkpoint_path: str | Path,
    ) -> Path:
        """
        Resolve and validate a local checkpoint path.

        The checkpoint must be located inside ai/checkpoints.
        """

        candidate = Path(checkpoint_path)

        if not candidate.is_absolute():
            candidate = (
                self.checkpoint_directory / candidate
            )

        candidate = candidate.resolve()

        try:
            candidate.relative_to(
                self.checkpoint_directory
            )
        except ValueError as exc:
            raise InvalidCheckpointError(
                "Local checkpoints must be stored inside "
                "ai/checkpoints/."
            ) from exc

        if not candidate.exists():
            raise InvalidCheckpointError(
                "The local checkpoint does not exist."
            )

        return candidate

    def register(
        self,
        *,
        model_id: str,
        version: str,
        provider: ModelProvider | str,
        kind: ModelKind | str,
        status: ModelStatus | str = (
            ModelStatus.REGISTERED
        ),
        display_name: str | None = None,
        model_name: str | None = None,
        checkpoint_path: str | Path | None = None,
        checkpoint_sha256: str | None = None,
        base_model: str | None = None,
        languages: Iterable[str] = ("en",),
        tasks: Iterable[str] = (
            "property_assistant",
        ),
        metrics: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        replace_existing: bool = False,
    ) -> ModelRecord:
        """Register a model in the model registry."""

        safe_model_id = validate_model_id(model_id)
        safe_version = validate_version(version)

        try:
            safe_provider = ModelProvider(provider)
            safe_kind = ModelKind(kind)
            safe_status = ModelStatus(status)
        except ValueError as exc:
            raise ModelRegistryError(
                "Invalid model provider, kind, or status."
            ) from exc

        relative_checkpoint: str | None = None
        checkpoint_digest = checkpoint_sha256

        if checkpoint_path is not None:
            if safe_provider != ModelProvider.LOCAL:
                raise InvalidCheckpointError(
                    "checkpoint_path can only be used "
                    "with local models."
                )

            resolved_checkpoint = self._safe_checkpoint(
                checkpoint_path
            )

            relative_checkpoint = (
                resolved_checkpoint.relative_to(
                    self.checkpoint_directory
                ).as_posix()
            )

            if not checkpoint_digest:
                checkpoint_digest = calculate_sha256(
                    resolved_checkpoint
                )

        if (
            checkpoint_digest
            and not SHA256_PATTERN.fullmatch(
                checkpoint_digest
            )
        ):
            raise ModelRegistryError(
                "Checkpoint SHA-256 must contain exactly "
                "64 hexadecimal characters."
            )

        safe_languages = (
            normalize_list(languages) or ("en",)
        )

        safe_tasks = (
            normalize_list(tasks)
            or ("property_assistant",)
        )

        now = utc_now()

        record = ModelRecord(
            model_id=safe_model_id,
            version=safe_version,
            provider=safe_provider,
            kind=safe_kind,
            status=safe_status,
            display_name=(
                normalize_string(
                    display_name,
                    200,
                )
                or None
            ),
            model_name=(
                normalize_string(
                    model_name,
                    300,
                )
                or None
            ),
            checkpoint_path=relative_checkpoint,
            checkpoint_sha256=(
                checkpoint_digest.lower()
                if checkpoint_digest
                else None
            ),
            base_model=(
                normalize_string(
                    base_model,
                    300,
                )
                or None
            ),
            languages=safe_languages,
            tasks=safe_tasks,
            metrics=normalize_metrics(metrics),
            metadata=validate_metadata(metadata),
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            data = self._load_data()
            records = self._records(data)

            existing_index = next(
                (
                    index
                    for index, existing_record
                    in enumerate(records)
                    if existing_record.model_id
                    == safe_model_id
                ),
                None,
            )

            if (
                existing_index is not None
                and not replace_existing
            ):
                raise DuplicateModelError(
                    f"Model {safe_model_id!r} is "
                    "already registered."
                )

            if existing_index is not None:
                existing = records[existing_index]

                record = replace(
                    record,
                    created_at=existing.created_at,
                )

                records[existing_index] = record

            else:
                records.append(record)

            records.sort(
                key=lambda item: item.model_id
            )

            data["models"] = [
                item.to_dict()
                for item in records
            ]

            data["updated_at"] = now

            self._write_data(data)

        return record

    def list_models(
        self,
        *,
        status: ModelStatus | str | None = None,
        provider: ModelProvider | str | None = None,
        language: str | None = None,
        task: str | None = None,
    ) -> tuple[ModelRecord, ...]:
        """List models using optional filters."""

        with self._lock:
            records = self._records(
                self._load_data()
            )

        status_value = (
            ModelStatus(status)
            if status is not None
            else None
        )

        provider_value = (
            ModelProvider(provider)
            if provider is not None
            else None
        )

        language_value = (
            str(language or "")
            .strip()
            .lower()
        )

        task_value = (
            str(task or "")
            .strip()
            .lower()
        )

        filtered = [
            record
            for record in records
            if (
                status_value is None
                or record.status == status_value
            )
            and (
                provider_value is None
                or record.provider == provider_value
            )
            and (
                not language_value
                or language_value in record.languages
            )
            and (
                not task_value
                or task_value in record.tasks
            )
        ]

        return tuple(filtered)

    def get(
        self,
        model_id: str,
    ) -> ModelRecord:
        """Return a registered model."""

        safe_model_id = validate_model_id(
            model_id
        )

        for record in self.list_models():
            if record.model_id == safe_model_id:
                return record

        raise ModelNotFoundError(
            f"Model {safe_model_id!r} is not registered."
        )

    def _update_record(
        self,
        model_id: str,
        **changes: Any,
    ) -> ModelRecord:
        """Update fields on a registered model."""

        safe_model_id = validate_model_id(
            model_id
        )

        with self._lock:
            data = self._load_data()
            records = self._records(data)

            existing_index = next(
                (
                    index
                    for index, record
                    in enumerate(records)
                    if record.model_id
                    == safe_model_id
                ),
                None,
            )

            if existing_index is None:
                raise ModelNotFoundError(
                    f"Model {safe_model_id!r} "
                    "is not registered."
                )

            updated_record = replace(
                records[existing_index],
                updated_at=utc_now(),
                **changes,
            )

            records[existing_index] = updated_record

            data["models"] = [
                record.to_dict()
                for record in records
            ]

            data["updated_at"] = (
                updated_record.updated_at
            )

            self._write_data(data)

            return updated_record

    def update_status(
        self,
        model_id: str,
        status: ModelStatus | str,
    ) -> ModelRecord:
        """Update the lifecycle status of a model."""

        try:
            safe_status = ModelStatus(status)
        except ValueError as exc:
            raise ModelRegistryError(
                "Invalid model status."
            ) from exc

        return self._update_record(
            model_id,
            status=safe_status,
        )

    def update_metrics(
        self,
        model_id: str,
        metrics: Mapping[str, Any],
        *,
        merge: bool = True,
    ) -> ModelRecord:
        """Update evaluation metrics for a model."""

        current_record = self.get(model_id)
        normalized = normalize_metrics(metrics)

        combined: dict[str, float] = {}

        if merge:
            combined.update(
                dict(current_record.metrics)
            )

        combined.update(normalized)

        return self._update_record(
            model_id,
            metrics=combined,
        )

    def set_active(
        self,
        model_id: str,
    ) -> ModelRecord:
        """Set a ready model as the active model."""

        record = self.get(model_id)

        if record.status != ModelStatus.READY:
            raise ModelRegistryError(
                "Only a model with ready status "
                "can be activated."
            )

        with self._lock:
            data = self._load_data()

            data["active_model_id"] = (
                record.model_id
            )

            data["updated_at"] = utc_now()

            self._write_data(data)

        return record

    def clear_active(self) -> None:
        """Clear the active model selection."""

        with self._lock:
            data = self._load_data()

            data["active_model_id"] = None
            data["updated_at"] = utc_now()

            self._write_data(data)

    def get_active(self) -> ModelRecord | None:
        """Return the currently active model."""

        with self._lock:
            data = self._load_data()

            active_model_id = data.get(
                "active_model_id"
            )

        if not active_model_id:
            return None

        try:
            return self.get(
                str(active_model_id)
            )
        except ModelNotFoundError:
            return None

    def select(
        self,
        *,
        language: str | None = None,
        task: str | None = None,
    ) -> ModelRecord:
        """
        Select a compatible ready model.

        The active model is preferred when it supports the requested
        language and task.
        """

        language_value = (
            str(language or "")
            .strip()
            .lower()
        )

        task_value = (
            str(task or "")
            .strip()
            .lower()
        )

        active_model = self.get_active()

        if active_model is not None:
            language_matches = (
                not language_value
                or language_value
                in active_model.languages
            )

            task_matches = (
                not task_value
                or task_value
                in active_model.tasks
            )

            if (
                active_model.status
                == ModelStatus.READY
                and language_matches
                and task_matches
            ):
                return active_model

        candidates = self.list_models(
            status=ModelStatus.READY,
            language=language_value or None,
            task=task_value or None,
        )

        if not candidates:
            raise ModelNotFoundError(
                "No ready model matches the requested "
                "language and task."
            )

        return candidates[0]

    def resolve_checkpoint(
        self,
        model_id: str,
    ) -> Path | None:
        """Resolve the checkpoint path for a local model."""

        record = self.get(model_id)

        if (
            record.provider != ModelProvider.LOCAL
            or not record.checkpoint_path
        ):
            return None

        checkpoint = self._safe_checkpoint(
            record.checkpoint_path
        )

        if (
            record.checkpoint_sha256
            and checkpoint.is_file()
        ):
            current_digest = calculate_sha256(
                checkpoint
            )

            if (
                current_digest
                != record.checkpoint_sha256
            ):
                raise InvalidCheckpointError(
                    "The checkpoint checksum does not "
                    "match the registered checksum."
                )

        return checkpoint

    def archive(
        self,
        model_id: str,
    ) -> ModelRecord:
        """
        Archive a model without deleting its checkpoint.

        If the model is active, its active status is cleared.
        """

        record = self.update_status(
            model_id,
            ModelStatus.ARCHIVED,
        )

        with self._lock:
            data = self._load_data()

            if (
                data.get("active_model_id")
                == record.model_id
            ):
                data["active_model_id"] = None
                data["updated_at"] = utc_now()
                self._write_data(data)

        return record

    def ensure_local_default(self) -> ModelRecord:
        """
        Ensure the dependency-free fallback model is registered.

        This fallback can be used by ai/assistant.py when no trained
        checkpoint or external provider is available.
        """

        try:
            return self.get(DEFAULT_MODEL_ID)

        except ModelNotFoundError:
            return self.register(
                model_id=DEFAULT_MODEL_ID,
                version="1.0.0",
                provider=ModelProvider.LOCAL,
                kind=ModelKind.RULE_BASED,
                status=ModelStatus.READY,
                display_name=(
                    "Smart Property Local Assistant"
                ),
                model_name=DEFAULT_MODEL_ID,
                languages=(
                    "en",
                    "de",
                    "fr",
                    "es",
                ),
                tasks=(
                    "property_assistant",
                    "apartment_search",
                    "tenant_support",
                    "landlord_support",
                ),
                metadata={
                    "description": (
                        "Dependency-free local fallback "
                        "assistant."
                    ),
                    "production_ready": False,
                },
            )


# ============================================================
# APPLICATION-WIDE REGISTRY
# ============================================================

_registry_instance: ModelRegistry | None = None
_registry_lock = threading.Lock()


def get_model_registry() -> ModelRegistry:
    """Return the shared application model registry."""

    global _registry_instance

    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = ModelRegistry()

    return _registry_instance


def register_model(
    *,
    model_id: str,
    version: str,
    provider: ModelProvider | str,
    kind: ModelKind | str,
    status: ModelStatus | str = ModelStatus.REGISTERED,
    display_name: str | None = None,
    model_name: str | None = None,
    checkpoint_path: str | Path | None = None,
    checkpoint_sha256: str | None = None,
    base_model: str | None = None,
    languages: Iterable[str] = ("en",),
    tasks: Iterable[str] = ("property_assistant",),
    metrics: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    replace_existing: bool = False,
) -> ModelRecord:
    """Register a model in the shared registry."""

    return get_model_registry().register(
        model_id=model_id,
        version=version,
        provider=provider,
        kind=kind,
        status=status,
        display_name=display_name,
        model_name=model_name,
        checkpoint_path=checkpoint_path,
        checkpoint_sha256=checkpoint_sha256,
        base_model=base_model,
        languages=languages,
        tasks=tasks,
        metrics=metrics,
        metadata=metadata,
        replace_existing=replace_existing,
    )


def get_active_model() -> ModelRecord | None:
    """Return the active model from the shared registry."""

    return get_model_registry().get_active()


def ensure_default_model() -> ModelRecord:
    """Register the fallback model if it does not already exist."""

    return get_model_registry().ensure_local_default()


__all__ = [
    "AI_DIRECTORY",
    "DEFAULT_CHECKPOINT_DIRECTORY",
    "DEFAULT_MODEL_ID",
    "DEFAULT_REGISTRY_PATH",
    "DuplicateModelError",
    "InvalidCheckpointError",
    "ModelKind",
    "ModelNotFoundError",
    "ModelProvider",
    "ModelRecord",
    "ModelRegistry",
    "ModelRegistryError",
    "ModelStatus",
    "calculate_sha256",
    "ensure_default_model",
    "get_active_model",
    "get_model_registry",
    "register_model",
]