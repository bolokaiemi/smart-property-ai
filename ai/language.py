"""Language utilities for Smart Property AI.

This module normalizes language preferences and provides lightweight
language detection for English, German, French, and Spanish.

It has no third-party dependencies, so it can be imported safely
during application startup.

The detector is intentionally conservative. A low-confidence result
falls back to the authenticated user's preference or the application's
default language.
"""

from __future__ import annotations

import re
import unicodedata

from dataclasses import dataclass
from typing import Final, Iterable, Mapping


DEFAULT_LANGUAGE: Final[str] = "en"
MIN_DETECTION_CHARACTERS: Final[int] = 3


@dataclass(frozen=True, slots=True)
class LanguageInfo:
    """Metadata for one supported language."""

    code: str
    name: str
    native_name: str
    locale: str
    direction: str = "ltr"


@dataclass(frozen=True, slots=True)
class LanguageDetection:
    """Result returned by detect_language()."""

    language: str
    confidence: float
    scores: Mapping[str, float]
    used_fallback: bool = False


SUPPORTED_LANGUAGES: Final[
    dict[str, LanguageInfo]
] = {
    "en": LanguageInfo(
        code="en",
        name="English",
        native_name="English",
        locale="en-GB",
    ),
    "de": LanguageInfo(
        code="de",
        name="German",
        native_name="Deutsch",
        locale="de-DE",
    ),
    "fr": LanguageInfo(
        code="fr",
        name="French",
        native_name="Français",
        locale="fr-FR",
    ),
    "es": LanguageInfo(
        code="es",
        name="Spanish",
        native_name="Español",
        locale="es-ES",
    ),
}


LANGUAGE_ALIASES: Final[dict[str, str]] = {
    "english": "en",
    "englisch": "en",
    "anglais": "en",
    "inglés": "en",
    "ingles": "en",

    "german": "de",
    "deutsch": "de",
    "allemand": "de",
    "alemán": "de",
    "aleman": "de",

    "french": "fr",
    "français": "fr",
    "francais": "fr",
    "französisch": "fr",
    "franzosisch": "fr",
    "francés": "fr",
    "frances": "fr",

    "spanish": "es",
    "español": "es",
    "espanol": "es",
    "spanisch": "es",
    "espagnol": "es",
}


LANGUAGE_WORDS: Final[
    dict[str, frozenset[str]]
] = {
    "en": frozenset(
        {
            "a",
            "an",
            "and",
            "apartment",
            "application",
            "are",
            "can",
            "complaint",
            "document",
            "find",
            "for",
            "hello",
            "help",
            "how",
            "i",
            "is",
            "lease",
            "maintenance",
            "my",
            "payment",
            "please",
            "property",
            "rent",
            "tenant",
            "the",
            "this",
            "to",
            "viewing",
            "what",
            "when",
            "where",
            "with",
            "you",
        }
    ),

    "de": frozenset(
        {
            "aber",
            "antrag",
            "bitte",
            "danke",
            "das",
            "der",
            "die",
            "dokument",
            "eine",
            "einen",
            "für",
            "hallo",
            "haus",
            "ich",
            "ist",
            "kann",
            "miete",
            "mieter",
            "mietvertrag",
            "mit",
            "reparatur",
            "und",
            "wann",
            "was",
            "wie",
            "wohnung",
            "wo",
            "zahlen",
        }
    ),

    "fr": frozenset(
        {
            "appartement",
            "avec",
            "bail",
            "bonjour",
            "comment",
            "demande",
            "des",
            "document",
            "est",
            "je",
            "les",
            "loyer",
            "locataire",
            "logement",
            "merci",
            "mon",
            "paiement",
            "pour",
            "propriété",
            "quand",
            "que",
            "réparation",
            "une",
            "vous",
        }
    ),

    "es": frozenset(
        {
            "alquiler",
            "apartamento",
            "arrendamiento",
            "con",
            "contrato",
            "documento",
            "dónde",
            "el",
            "es",
            "gracias",
            "hola",
            "inquilino",
            "la",
            "mantenimiento",
            "mi",
            "para",
            "pago",
            "por",
            "propiedad",
            "qué",
            "reparación",
            "solicitud",
            "una",
            "usted",
            "vivienda",
        }
    ),
}


CHARACTER_HINTS: Final[
    dict[str, tuple[str, ...]]
] = {
    "en": (),
    "de": (
        "ä",
        "ö",
        "ü",
        "ß",
    ),
    "fr": (
        "à",
        "â",
        "ç",
        "é",
        "è",
        "ê",
        "ë",
        "î",
        "ï",
        "ô",
        "ù",
        "û",
        "œ",
    ),
    "es": (
        "á",
        "é",
        "í",
        "ñ",
        "ó",
        "ú",
        "ü",
        "¿",
        "¡",
    ),
}


PHRASE_HINTS: Final[
    dict[str, tuple[str, ...]]
] = {
    "en": (
        "how can i",
        "i would like",
        "when is my rent",
        "find an apartment",
    ),
    "de": (
        "ich möchte",
        "wie kann ich",
        "wann ist meine miete",
        "eine wohnung finden",
    ),
    "fr": (
        "je voudrais",
        "comment puis-je",
        "quand dois-je payer",
        "trouver un appartement",
    ),
    "es": (
        "me gustaría",
        "cómo puedo",
        "cuándo debo pagar",
        "buscar un apartamento",
    ),
}


LOCALIZED_MESSAGES: Final[
    dict[str, dict[str, str]]
] = {
    "en": {
        "welcome": (
            "Hello! How can I help with your property "
            "or tenancy question?"
        ),
        "clarify": (
            "Could you provide a little more information "
            "so I can help accurately?"
        ),
        "not_found": (
            "I could not find verified information "
            "for that request."
        ),
        "login_required": (
            "Please log in to access private account "
            "or tenancy information."
        ),
        "error": (
            "The assistant is temporarily unavailable. "
            "Please try again."
        ),
    },

    "de": {
        "welcome": (
            "Hallo! Wie kann ich Ihnen bei Ihrer Immobilien- "
            "oder Mietfrage helfen?"
        ),
        "clarify": (
            "Könnten Sie weitere Informationen angeben, "
            "damit ich Ihnen genau helfen kann?"
        ),
        "not_found": (
            "Ich konnte keine verifizierten Informationen "
            "zu dieser Anfrage finden."
        ),
        "login_required": (
            "Bitte melden Sie sich an, um auf private Konto- "
            "oder Mietinformationen zuzugreifen."
        ),
        "error": (
            "Der Assistent ist vorübergehend nicht verfügbar. "
            "Bitte versuchen Sie es erneut."
        ),
    },

    "fr": {
        "welcome": (
            "Bonjour ! Comment puis-je vous aider concernant "
            "votre logement ou votre location ?"
        ),
        "clarify": (
            "Pouvez-vous fournir davantage d’informations "
            "afin que je puisse vous aider avec précision ?"
        ),
        "not_found": (
            "Je n’ai trouvé aucune information vérifiée "
            "pour cette demande."
        ),
        "login_required": (
            "Veuillez vous connecter pour accéder aux informations "
            "privées du compte ou de la location."
        ),
        "error": (
            "L’assistant est temporairement indisponible. "
            "Veuillez réessayer."
        ),
    },

    "es": {
        "welcome": (
            "¡Hola! ¿Cómo puedo ayudarle con su propiedad "
            "o alquiler?"
        ),
        "clarify": (
            "¿Puede proporcionar más información para que "
            "pueda ayudarle con precisión?"
        ),
        "not_found": (
            "No encontré información verificada "
            "para esta solicitud."
        ),
        "login_required": (
            "Inicie sesión para acceder a información privada "
            "de la cuenta o del alquiler."
        ),
        "error": (
            "El asistente no está disponible temporalmente. "
            "Inténtelo de nuevo."
        ),
    },
}


WORD_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[^\W\d_]+(?:['’][^\W\d_]+)?",
    re.UNICODE,
)


def normalize_language(
    language: str | None,
    *,
    default: str = DEFAULT_LANGUAGE,
) -> str:
    """Return a supported two-letter language code.

    Accepts values such as:

    - de-DE
    - en_GB
    - Deutsch
    - Français
    - Español
    """

    safe_default = str(
        default or DEFAULT_LANGUAGE
    ).strip().lower()

    safe_default = (
        safe_default
        .replace("_", "-")
        .split("-", 1)[0]
    )

    if safe_default not in SUPPORTED_LANGUAGES:
        safe_default = DEFAULT_LANGUAGE

    if not language:
        return safe_default

    value = unicodedata.normalize(
        "NFKC",
        str(language),
    ).strip().lower()

    if not value:
        return safe_default

    if value in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[value]

    base_code = (
        value
        .replace("_", "-")
        .split("-", 1)[0]
    )

    if base_code in SUPPORTED_LANGUAGES:
        return base_code

    return safe_default


def language_info(
    language: str | None,
) -> LanguageInfo:
    """Return metadata for a normalized language."""

    code = normalize_language(language)

    return SUPPORTED_LANGUAGES[code]


def supported_language_codes() -> tuple[str, ...]:
    """Return supported language codes."""

    return tuple(SUPPORTED_LANGUAGES)


def is_supported_language(
    language: str | None,
) -> bool:
    """Return whether a value identifies a supported language."""

    if not language:
        return False

    value = unicodedata.normalize(
        "NFKC",
        str(language),
    ).strip().lower()

    if value in LANGUAGE_ALIASES:
        return True

    base_code = (
        value
        .replace("_", "-")
        .split("-", 1)[0]
    )

    return base_code in SUPPORTED_LANGUAGES


def parse_accept_language(
    header: str | None,
) -> tuple[str, ...]:
    """Parse the HTTP Accept-Language header.

    Example:

    de-DE,de;q=0.9,en;q=0.8
    """

    if not header:
        return ()

    choices: list[
        tuple[float, int, str]
    ] = []

    for position, item in enumerate(
        str(header).split(",")
    ):
        parts = [
            part.strip()
            for part in item.split(";")
            if part.strip()
        ]

        if not parts:
            continue

        if parts[0] == "*":
            continue

        quality = 1.0

        for parameter in parts[1:]:
            if parameter.lower().startswith("q="):
                try:
                    quality = float(
                        parameter.split(
                            "=",
                            1,
                        )[1]
                    )
                except ValueError:
                    quality = 0.0

        if quality <= 0:
            continue

        candidate = parts[0]

        if is_supported_language(candidate):
            choices.append(
                (
                    max(
                        0.0,
                        min(
                            quality,
                            1.0,
                        ),
                    ),
                    position,
                    normalize_language(candidate),
                )
            )

    choices.sort(
        key=lambda item: (
            -item[0],
            item[1],
        )
    )

    ordered: list[str] = []

    for _, _, code in choices:
        if code not in ordered:
            ordered.append(code)

    return tuple(ordered)


def select_language(
    *,
    requested: str | None = None,
    session_language: str | None = None,
    user_language: str | None = None,
    accept_language: str | None = None,
    default: str = DEFAULT_LANGUAGE,
) -> str:
    """Select a language using a predictable priority.

    Priority:

    1. Explicitly requested language
    2. Authenticated user preference
    3. Session preference
    4. Browser Accept-Language header
    5. Application default
    """

    candidates = (
        requested,
        user_language,
        session_language,
    )

    for candidate in candidates:
        if is_supported_language(candidate):
            return normalize_language(
                candidate,
                default=default,
            )

    browser_languages = parse_accept_language(
        accept_language
    )

    if browser_languages:
        return browser_languages[0]

    return normalize_language(default)


def _tokenize(
    text: str,
) -> tuple[str, ...]:
    """Return lowercase tokens for language detection."""

    normalized = unicodedata.normalize(
        "NFKC",
        str(text),
    ).lower()

    return tuple(
        match.group(0)
        for match in WORD_PATTERN.finditer(normalized)
    )


def detect_language(
    text: str | None,
    *,
    fallback: str = DEFAULT_LANGUAGE,
) -> LanguageDetection:
    """Detect English, German, French, or Spanish.

    The message is never sent to an external language-detection
    service.

    Low-confidence results use the provided fallback language.
    """

    fallback_code = normalize_language(
        fallback
    )

    cleaned = unicodedata.normalize(
        "NFKC",
        str(text or ""),
    ).strip().lower()

    empty_scores = {
        code: 0.0
        for code in SUPPORTED_LANGUAGES
    }

    if len(cleaned) < MIN_DETECTION_CHARACTERS:
        return LanguageDetection(
            language=fallback_code,
            confidence=0.0,
            scores=empty_scores,
            used_fallback=True,
        )

    tokens = _tokenize(cleaned)

    scores = {
        code: 0.0
        for code in SUPPORTED_LANGUAGES
    }

    for code, vocabulary in LANGUAGE_WORDS.items():
        for token in tokens:
            if token in vocabulary:
                scores[code] += 1.0

    for code, characters in CHARACTER_HINTS.items():
        for character in characters:
            if character in cleaned:
                scores[code] += 0.65

    for code, phrases in PHRASE_HINTS.items():
        for phrase in phrases:
            if phrase in cleaned:
                scores[code] += 2.5

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    best_code, best_score = ranked[0]
    second_score = ranked[1][1]
    total_score = sum(scores.values())

    if best_score <= 0:
        return LanguageDetection(
            language=fallback_code,
            confidence=0.0,
            scores=scores,
            used_fallback=True,
        )

    if total_score:
        share = best_score / total_score
    else:
        share = 0.0

    if best_score:
        separation = (
            best_score - second_score
        ) / best_score
    else:
        separation = 0.0

    evidence = min(
        1.0,
        best_score / 3.0,
    )

    confidence = round(
        (
            0.5 * share
            + 0.3 * separation
            + 0.2 * evidence
        ),
        4,
    )

    minimum_confidence = 0.45

    if confidence < minimum_confidence:
        return LanguageDetection(
            language=fallback_code,
            confidence=confidence,
            scores=scores,
            used_fallback=True,
        )

    return LanguageDetection(
        language=best_code,
        confidence=confidence,
        scores=scores,
        used_fallback=False,
    )


def resolve_response_language(
    text: str | None,
    *,
    requested: str | None = None,
    session_language: str | None = None,
    user_language: str | None = None,
    accept_language: str | None = None,
    detect_from_text: bool = True,
) -> str:
    """Resolve the language for the assistant response.

    An explicitly requested language always wins.

    Otherwise, clear language evidence in the current message
    can override stored preferences.
    """

    preferred = select_language(
        requested=requested,
        session_language=session_language,
        user_language=user_language,
        accept_language=accept_language,
    )

    if is_supported_language(requested):
        return preferred

    if not detect_from_text:
        return preferred

    detection = detect_language(
        text,
        fallback=preferred,
    )

    return detection.language


def localized_message(
    key: str,
    language: str | None = None,
    *,
    default: str | None = None,
) -> str:
    """Return a predefined localized interface message."""

    code = normalize_language(language)

    messages = LOCALIZED_MESSAGES[code]

    if key in messages:
        return messages[key]

    if default is not None:
        return str(default)

    raise KeyError(
        f"Unknown localized message key: {key}"
    )


def html_language_attributes(
    language: str | None,
) -> dict[str, str]:
    """Return safe HTML lang and dir attributes."""

    info = language_info(language)

    return {
        "lang": info.code,
        "dir": info.direction,
    }


def language_options(
    selected: str | None = None,
) -> list[dict[str, object]]:
    """Return options for a Jinja language selector."""

    selected_code = normalize_language(
        selected
    )

    return [
        {
            "code": info.code,
            "name": info.name,
            "native_name": info.native_name,
            "locale": info.locale,
            "direction": info.direction,
            "selected": (
                info.code == selected_code
            ),
        }
        for info in SUPPORTED_LANGUAGES.values()
    ]


def validate_language_collection(
    languages: Iterable[str],
) -> tuple[str, ...]:
    """Normalize and deduplicate supported languages."""

    normalized: list[str] = []

    for language in languages:
        if not is_supported_language(language):
            continue

        code = normalize_language(language)

        if code not in normalized:
            normalized.append(code)

    return tuple(normalized)


__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGE_ALIASES",
    "LOCALIZED_MESSAGES",
    "LanguageDetection",
    "LanguageInfo",
    "SUPPORTED_LANGUAGES",
    "detect_language",
    "html_language_attributes",
    "is_supported_language",
    "language_info",
    "language_options",
    "localized_message",
    "normalize_language",
    "parse_accept_language",
    "resolve_response_language",
    "select_language",
    "supported_language_codes",
    "validate_language_collection",
]