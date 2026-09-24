

from __future__ import annotations

from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def language_module() -> ModuleType:
    try:
        import ai.language as module
    except Exception as exc:
        pytest.fail(f"ai.language could not be imported: {exc!r}")
    return module


def find_callable(module: ModuleType, names: tuple[str, ...]):
    for name in names:
        value = getattr(module, name, None)
        if callable(value):
            return value
    return None


def test_core_languages_are_declared(language_module: ModuleType) -> None:
    supported = None
    for name in ("SUPPORTED_LANGUAGES", "LANGUAGES", "SUPPORTED_LANGUAGE_CODES"):
        value = getattr(language_module, name, None)
        if value is not None:
            supported = value
            break

    if supported is None:
        pytest.skip("Supported languages are provided dynamically")

    codes = set(supported.keys() if isinstance(supported, dict) else supported)
    assert {"en", "de", "fr", "es"}.issubset({str(code).lower() for code in codes})


@pytest.mark.parametrize(
    ("raw_code", "expected"),
    (
        ("EN", "en"),
        ("de-DE", "de"),
        ("fr_FR", "fr"),
        ("es", "es"),
    ),
)
def test_language_normalization_when_available(
    language_module: ModuleType,
    raw_code: str,
    expected: str,
) -> None:
    normalizer = find_callable(
        language_module,
        ("normalize_language", "normalize_language_code", "normalise_language"),
    )
    if normalizer is None:
        pytest.skip("No public language normalizer")
    assert str(normalizer(raw_code)).lower() == expected


def test_unknown_language_has_safe_fallback_when_available(
    language_module: ModuleType,
) -> None:
    normalizer = find_callable(
        language_module,
        ("normalize_language", "normalize_language_code", "normalise_language"),
    )
    if normalizer is None:
        pytest.skip("No public language normalizer")
    result = normalizer("not-a-real-language")
    assert result is None or str(result).lower() in {"en", "unknown", "und"}

