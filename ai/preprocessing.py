"""Secure dataset preprocessing for Smart Property AI.

This module:

- Validates JSONL training records
- Normalizes languages and intents
- Redacts sensitive contact information
- Rejects credentials and unsafe records
- Removes duplicate examples
- Creates deterministic dataset splits
- Produces privacy-safe processing reports

Message contents are never printed to the console or included
in processing reports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import unicodedata

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

from .language import (
    detect_language,
    normalize_language,
)

from .prompts import (
    build_training_prompt,
)

from .safety import (
    check_input,
    check_output,
    detected_sensitive_types,
    redact_sensitive_data,
)


MAX_LINE_BYTES = 1_000_000
MAX_USER_CHARACTERS = 4_000
MAX_ASSISTANT_CHARACTERS = 6_000

DEFAULT_SEED = "smart-property-ai-v1"


ALLOWED_INTENTS = frozenset(
    {
        "greeting",
        "capabilities",
        "property_search",
        "guided_search",
        "listing_question",
        "rental_application",
        "viewing_appointment",
        "lease_question",
        "rent_payment",
        "maintenance_request",
        "complaint",
        "document_help",
        "landlord_support",
        "tenant_support",
        "accessibility_help",
        "privacy_question",
        "legal_information",
        "emergency_redirect",
        "unknown",
    }
)


ALLOWED_SAFETY_LABELS = frozenset(
    {
        "safe",
        "sensitive",
        "blocked",
        "emergency",
        "human_review",
    }
)


ALLOWED_SPLITS = frozenset(
    {
        "train",
        "validation",
        "test",
    }
)


class DatasetError(ValueError):
    """Base exception for invalid dataset input."""


class DatasetLineError(DatasetError):
    """Raised when a JSONL line cannot be parsed."""


class RecordValidationError(DatasetError):
    """Raised when one record fails validation."""


@dataclass(slots=True)
class ProcessingReport:
    """Privacy-safe aggregate processing report."""

    input_records: int = 0
    accepted_records: int = 0
    rejected_records: int = 0

    duplicate_records: int = 0
    redacted_records: int = 0
    generated_ids: int = 0

    rejection_reasons: Counter[str] = field(
        default_factory=Counter
    )

    languages: Counter[str] = field(
        default_factory=Counter
    )

    intents: Counter[str] = field(
        default_factory=Counter
    )

    splits: Counter[str] = field(
        default_factory=Counter
    )

    def reject(
        self,
        reason: str,
    ) -> None:
        """Register a rejected record."""

        self.rejected_records += 1
        self.rejection_reasons[reason] += 1

    def to_dict(
        self,
    ) -> dict[str, object]:
        """Return a JSON-ready report."""

        return {
            "input_records": self.input_records,

            "accepted_records": (
                self.accepted_records
            ),

            "rejected_records": (
                self.rejected_records
            ),

            "duplicate_records": (
                self.duplicate_records
            ),

            "redacted_records": (
                self.redacted_records
            ),

            "generated_ids": (
                self.generated_ids
            ),

            "rejection_reasons": dict(
                sorted(
                    self.rejection_reasons.items()
                )
            ),

            "languages": dict(
                sorted(
                    self.languages.items()
                )
            ),

            "intents": dict(
                sorted(
                    self.intents.items()
                )
            ),

            "splits": dict(
                sorted(
                    self.splits.items()
                )
            ),
        }


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Processed records and aggregate report."""

    records: tuple[
        dict[str, object],
        ...,
    ]

    report: ProcessingReport


def _clean_text(
    value: object,
    maximum: int,
) -> str:
    """Normalize and validate a text value."""

    text = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    )

    text = (
        text
        .replace(
            "\x00",
            "",
        )
        .replace(
            "\r\n",
            "\n",
        )
        .replace(
            "\r",
            "\n",
        )
    )

    text = "\n".join(
        line.rstrip()
        for line in text.split("\n")
    ).strip()

    if len(text) > maximum:
        raise RecordValidationError(
            "text_too_long"
        )

    return text


def _clean_identifier(
    value: object,
) -> str:
    """Validate a non-personal record identifier."""

    value = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    ).strip()

    if not value:
        return ""

    if len(value) > 160:
        raise RecordValidationError(
            "invalid_identifier"
        )

    valid = all(
        character.isalnum()
        or character in "-_.:"
        for character in value
    )

    if not valid:
        raise RecordValidationError(
            "invalid_identifier"
        )

    return value


def _normalize_intent(
    value: object,
) -> str:
    """Normalize an intent label."""

    intent = (
        str(value or "unknown")
        .strip()
        .lower()
        .replace(
            "-",
            "_",
        )
        .replace(
            " ",
            "_",
        )
    )

    if intent in ALLOWED_INTENTS:
        return intent

    return "unknown"


def _normalize_safety_label(
    value: object,
) -> str:
    """Normalize and validate a safety label."""

    label = (
        str(value or "safe")
        .strip()
        .lower()
        .replace(
            "-",
            "_",
        )
        .replace(
            " ",
            "_",
        )
    )

    if label not in ALLOWED_SAFETY_LABELS:
        raise RecordValidationError(
            "invalid_safety_label"
        )

    return label


def _record_hash(
    language: str,
    intent: str,
    user_message: str,
    assistant_response: str,
) -> str:
    """Create a stable hash used for deduplication."""

    canonical = "\x1f".join(
        (
            language,
            intent,
            " ".join(
                user_message
                .casefold()
                .split()
            ),
            " ".join(
                assistant_response
                .casefold()
                .split()
            ),
        )
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _generated_id(
    record_hash: str,
) -> str:
    """Generate a non-personal record ID."""

    return (
        f"spa-{record_hash[:20]}"
    )


def deterministic_split(
    record_id: str,
    *,
    seed: str = DEFAULT_SEED,
    train_ratio: float = 0.8,
    validation_ratio: float = 0.1,
) -> str:
    """Assign a stable dataset split.

    The same record ID and seed always produce the same split.
    """

    if train_ratio <= 0:
        raise ValueError(
            "Train ratio must be positive."
        )

    if validation_ratio < 0:
        raise ValueError(
            "Validation ratio cannot be negative."
        )

    if (
        train_ratio
        + validation_ratio
        >= 1
    ):
        raise ValueError(
            "Train and validation ratios must "
            "leave room for test data."
        )

    digest = hashlib.sha256(
        f"{seed}:{record_id}".encode(
            "utf-8"
        )
    ).digest()

    value = (
        int.from_bytes(
            digest[:8],
            "big",
        )
        / float(2**64)
    )

    if value < train_ratio:
        return "train"

    if (
        value
        < train_ratio
        + validation_ratio
    ):
        return "validation"

    return "test"


def load_jsonl(
    path: str | Path,
) -> Iterator[dict[str, object]]:
    """Read objects from a UTF-8 JSONL file."""

    source = Path(path)

    if not source.is_file():
        raise FileNotFoundError(
            f"Dataset file not found: {source}"
        )

    with source.open("rb") as handle:
        for line_number, raw_line in enumerate(
            handle,
            start=1,
        ):
            if len(raw_line) > MAX_LINE_BYTES:
                raise DatasetLineError(
                    f"Line {line_number}: "
                    "line_too_large"
                )

            if not raw_line.strip():
                continue

            try:
                decoded = raw_line.decode(
                    "utf-8"
                )

                value = json.loads(
                    decoded
                )

            except UnicodeDecodeError as exc:
                raise DatasetLineError(
                    f"Line {line_number}: "
                    "invalid_utf8"
                ) from exc

            except json.JSONDecodeError as exc:
                raise DatasetLineError(
                    f"Line {line_number}: "
                    "invalid_json"
                ) from exc

            if not isinstance(
                value,
                dict,
            ):
                raise DatasetLineError(
                    f"Line {line_number}: "
                    "record_must_be_object"
                )

            yield value


def normalize_record(
    record: Mapping[str, object],
    *,
    seed: str = DEFAULT_SEED,
    preserve_split: bool = False,
    allow_blocked_examples: bool = False,
) -> tuple[
    dict[str, object],
    bool,
    bool,
]:
    """Validate and normalize one training record.

    Returns:

    normalized record,
    whether redaction happened,
    whether an ID was generated.
    """

    user_message = _clean_text(
        record.get(
            "user_message"
        ),
        MAX_USER_CHARACTERS,
    )

    assistant_response = _clean_text(
        record.get(
            "assistant_response"
        ),
        MAX_ASSISTANT_CHARACTERS,
    )

    if not user_message:
        raise RecordValidationError(
            "empty_user_message"
        )

    if not assistant_response:
        raise RecordValidationError(
            "empty_assistant_response"
        )

    requested_language = str(
        record.get(
            "language"
        )
        or ""
    ).strip()

    if requested_language:
        language = normalize_language(
            requested_language
        )
    else:
        language = detect_language(
            user_message
        ).language

    intent = _normalize_intent(
        record.get(
            "intent"
        )
    )

    safety_label = (
        _normalize_safety_label(
            record.get(
                "safety_label"
            )
        )
    )

    source = _clean_text(
        record.get(
            "source"
        ),
        300,
    )

    consent = _clean_text(
        record.get(
            "consent"
        ),
        120,
    )

    if not source:
        raise RecordValidationError(
            "missing_source"
        )

    if not consent:
        raise RecordValidationError(
            "missing_consent"
        )

    sensitive_input = set(
        detected_sensitive_types(
            user_message
        )
    )

    sensitive_output = set(
        detected_sensitive_types(
            assistant_response
        )
    )

    sensitive_types = (
        sensitive_input
        | sensitive_output
    )

    credentials = {
        "iban",
        "payment_card",
        "access_token",
        "session_cookie",
        "password",
    }

    if credentials.intersection(
        sensitive_types
    ):
        raise RecordValidationError(
            "credentials_detected"
        )

    input_check = check_input(
        user_message,
        language=language,
    )

    blocked_example = (
        safety_label
        in {
            "blocked",
            "emergency",
            "human_review",
        }
    )

    allow_safety_example = (
        allow_blocked_examples
        and blocked_example
        and source.casefold()
        == "synthetic"
    )

    if (
        not input_check.allowed
        and not allow_safety_example
    ):
        category = (
            input_check
            .primary_category
            .value
        )

        raise RecordValidationError(
            f"unsafe_input:{category}"
        )

    output_check = check_output(
        assistant_response,
        language=language,
    )

    if not output_check.allowed:
        category = (
            output_check
            .primary_category
            .value
        )

        raise RecordValidationError(
            f"unsafe_output:{category}"
        )

    sanitized_user = (
        redact_sensitive_data(
            user_message
        )
    )

    sanitized_assistant = (
        redact_sensitive_data(
            output_check.sanitized_text
        )
    )

    was_redacted = (
        sanitized_user
        != user_message
        or sanitized_assistant
        != assistant_response
    )

    digest = _record_hash(
        language,
        intent,
        sanitized_user,
        sanitized_assistant,
    )

    record_id = _clean_identifier(
        record.get(
            "id"
        )
    )

    generated_identifier = (
        not bool(record_id)
    )

    if generated_identifier:
        record_id = _generated_id(
            digest
        )

    supplied_split = str(
        record.get(
            "split"
        )
        or ""
    ).strip().lower()

    if (
        preserve_split
        and supplied_split
        in ALLOWED_SPLITS
    ):
        split = supplied_split
    else:
        split = deterministic_split(
            record_id,
            seed=seed,
        )

    training = build_training_prompt(
        sanitized_user,
        sanitized_assistant,
        language=language,
        intent=intent,
    )

    normalized: dict[
        str,
        object,
    ] = {
        "id": record_id,
        "language": language,
        "intent": intent,

        "user_message": (
            sanitized_user
        ),

        "assistant_response": (
            sanitized_assistant
        ),

        "safety_label": safety_label,
        "source": source,
        "consent": consent,
        "split": split,

        "record_hash": digest,

        "messages": training[
            "messages"
        ],
    }

    optional_fields = (
        "country",
        "dataset_version",
        "requires_authentication",
        "requires_human_review",
        "accessibility_tags",
        "expected_entities",
    )

    for optional_field in optional_fields:
        if optional_field in record:
            normalized[
                optional_field
            ] = record[
                optional_field
            ]

    return (
        normalized,
        was_redacted,
        generated_identifier,
    )


def preprocess_records(
    records: Iterable[
        Mapping[str, object]
    ],
    *,
    seed: str = DEFAULT_SEED,
    preserve_split: bool = False,
    allow_blocked_examples: bool = False,
    fail_fast: bool = False,
) -> ProcessingResult:
    """Validate, normalize, and deduplicate records."""

    report = ProcessingReport()

    accepted: list[
        dict[str, object]
    ] = []

    seen_hashes: set[str] = set()
    seen_ids: set[str] = set()

    for record in records:
        report.input_records += 1

        try:
            (
                normalized,
                redacted,
                generated_identifier,
            ) = normalize_record(
                record,
                seed=seed,
                preserve_split=(
                    preserve_split
                ),
                allow_blocked_examples=(
                    allow_blocked_examples
                ),
            )

        except RecordValidationError as exc:
            report.reject(
                str(exc)
            )

            if fail_fast:
                raise

            continue

        record_hash = str(
            normalized[
                "record_hash"
            ]
        )

        record_id = str(
            normalized[
                "id"
            ]
        )

        if (
            record_hash in seen_hashes
            or record_id in seen_ids
        ):
            report.duplicate_records += 1
            continue

        seen_hashes.add(
            record_hash
        )

        seen_ids.add(
            record_id
        )

        accepted.append(
            normalized
        )

        report.accepted_records += 1

        report.redacted_records += int(
            redacted
        )

        report.generated_ids += int(
            generated_identifier
        )

        report.languages[
            str(
                normalized[
                    "language"
                ]
            )
        ] += 1

        report.intents[
            str(
                normalized[
                    "intent"
                ]
            )
        ] += 1

        report.splits[
            str(
                normalized[
                    "split"
                ]
            )
        ] += 1

    accepted.sort(
        key=lambda item: (
            str(
                item["split"]
            ),
            str(
                item["id"]
            ),
        )
    )

    return ProcessingResult(
        records=tuple(
            accepted
        ),
        report=report,
    )


def _atomic_write_text(
    path: Path,
    content: str,
) -> None:
    """Write UTF-8 text atomically."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        descriptor,
        temporary_name,
    ) = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(
            path.parent
        ),
        text=True,
    )

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(
                content
            )

            handle.flush()

            os.fsync(
                handle.fileno()
            )

        os.replace(
            temporary_name,
            path,
        )

    except Exception:
        try:
            os.unlink(
                temporary_name
            )
        except FileNotFoundError:
            pass

        raise


def write_jsonl(
    records: Iterable[
        Mapping[str, object]
    ],
    path: str | Path,
) -> None:
    """Write records as deterministic JSONL."""

    lines = [
        json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )
        for record in records
    ]

    content = "\n".join(
        lines
    )

    if content:
        content += "\n"

    _atomic_write_text(
        Path(path),
        content,
    )


def write_processing_result(
    result: ProcessingResult,
    output: str | Path,
) -> dict[str, Path]:
    """Write a combined file or split directory."""

    destination = Path(
        output
    )

    written: dict[
        str,
        Path,
    ] = {}

    if (
        destination
        .suffix
        .lower()
        == ".jsonl"
    ):
        write_jsonl(
            result.records,
            destination,
        )

        report_path = (
            destination
            .with_suffix(
                ".report.json"
            )
        )

        report_content = json.dumps(
            result.report.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"

        _atomic_write_text(
            report_path,
            report_content,
        )

        written[
            "dataset"
        ] = destination

        written[
            "report"
        ] = report_path

        return written

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    for split in (
        "train",
        "validation",
        "test",
    ):
        path = (
            destination
            / f"{split}.jsonl"
        )

        split_records = [
            record
            for record in result.records
            if record["split"]
            == split
        ]

        write_jsonl(
            split_records,
            path,
        )

        written[
            split
        ] = path

    report_path = (
        destination
        / "processing_report.json"
    )

    report_content = json.dumps(
        result.report.to_dict(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    _atomic_write_text(
        report_path,
        report_content,
    )

    written[
        "report"
    ] = report_path

    return written


def preprocess_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    seed: str = DEFAULT_SEED,
    preserve_split: bool = False,
    allow_blocked_examples: bool = False,
    fail_fast: bool = False,
) -> ProcessingResult:
    """Preprocess a JSONL file and write the output."""

    result = preprocess_records(
        load_jsonl(
            input_path
        ),
        seed=seed,
        preserve_split=(
            preserve_split
        ),
        allow_blocked_examples=(
            allow_blocked_examples
        ),
        fail_fast=fail_fast,
    )

    write_processing_result(
        result,
        output_path,
    )

    return result


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Validate and preprocess "
            "Smart Property AI JSONL datasets."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input raw JSONL file.",
    )

    parser.add_argument(
        "--output",
        required=True,
        help=(
            "Output JSONL file or directory "
            "for train, validation, and test files."
        ),
    )

    parser.add_argument(
        "--seed",
        default=DEFAULT_SEED,
    )

    parser.add_argument(
        "--preserve-split",
        action="store_true",
        help=(
            "Keep valid split values "
            "already present in the input."
        ),
    )

    parser.add_argument(
        "--allow-blocked-examples",
        action="store_true",
        help=(
            "Allow synthetic and correctly "
            "labelled safety-training examples."
        ),
    )

    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help=(
            "Stop processing after the "
            "first invalid record."
        ),
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Command-line entry point."""

    arguments = (
        build_argument_parser()
        .parse_args(argv)
    )

    try:
        result = preprocess_file(
            arguments.input,
            arguments.output,
            seed=arguments.seed,
            preserve_split=(
                arguments.preserve_split
            ),
            allow_blocked_examples=(
                arguments
                .allow_blocked_examples
            ),
            fail_fast=(
                arguments.fail_fast
            ),
        )

    except (
        OSError,
        DatasetError,
        ValueError,
    ) as exc:
        # Do not print record contents.
        print(
            "Dataset preprocessing failed: "
            f"{type(exc).__name__}"
        )

        return 1

    report = result.report

    print(
        "Dataset preprocessing complete: "
        f"accepted={report.accepted_records}, "
        f"rejected={report.rejected_records}, "
        f"duplicates={report.duplicate_records}, "
        f"redacted={report.redacted_records}."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )


__all__ = [
    "ALLOWED_INTENTS",
    "ALLOWED_SAFETY_LABELS",
    "ALLOWED_SPLITS",
    "DEFAULT_SEED",
    "DatasetError",
    "DatasetLineError",
    "ProcessingReport",
    "ProcessingResult",
    "RecordValidationError",
    "deterministic_split",
    "load_jsonl",
    "main",
    "normalize_record",
    "preprocess_file",
    "preprocess_records",
    "write_jsonl",
    "write_processing_result",
]