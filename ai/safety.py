"""Safety and privacy checks for Smart Property AI.

This module provides deterministic safety checks that run before and after
AI inference. It does not replace authentication, permission checks, CSRF
protection, rate limiting, or human review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Iterable, Pattern


MAX_INPUT_CHARACTERS: Final[int] = 4_000
MAX_OUTPUT_CHARACTERS: Final[int] = 8_000
DEFAULT_LANGUAGE: Final[str] = "en"


class SafetyCategory(StrEnum):
    """Categories returned by the safety checks."""

    SAFE = "safe"
    EMPTY = "empty"
    TOO_LONG = "too_long"
    PROMPT_INJECTION = "prompt_injection"
    SENSITIVE_DATA = "sensitive_data"
    CREDENTIALS = "credentials"
    DISCRIMINATION = "housing_discrimination"
    EMERGENCY = "emergency"
    ILLEGAL_REQUEST = "illegal_request"
    UNSUPPORTED_DECISION = "unsupported_decision"


class SafetyAction(StrEnum):
    """Action the assistant layer should take."""

    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class SafetyResult:
    """Structured result from an input or output safety check."""

    allowed: bool
    action: SafetyAction
    sanitized_text: str
    categories: tuple[SafetyCategory, ...]
    user_message: str | None = None
    requires_human_review: bool = False
    is_emergency: bool = False

    @property
    def primary_category(self) -> SafetyCategory:
        """Return the first detected category."""

        if self.categories:
            return self.categories[0]

        return SafetyCategory.SAFE


def _compile(pattern: str) -> Pattern[str]:
    """Compile a case-insensitive Unicode regular expression."""

    return re.compile(
        pattern,
        re.IGNORECASE | re.UNICODE,
    )


SENSITIVE_PATTERNS: Final[
    tuple[tuple[str, Pattern[str]], ...]
] = (
    (
        "email",
        _compile(
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
        ),
    ),
    (
        "iban",
        _compile(
            r"\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]){11,30}\b"
        ),
    ),
    (
        "payment_card",
        _compile(
            r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"
        ),
    ),
    (
        "access_token",
        _compile(
            r"\b(?:bearer\s+[A-Z0-9._~+/=-]{12,}|"
            r"(?:api[_-]?key|access[_-]?token|secret[_-]?key)"
            r"\s*[:=]\s*[A-Z0-9._~+/=-]{8,})"
        ),
    ),
    (
        "session_cookie",
        _compile(
            r"\b(?:session|cookie|csrf[_-]?token)"
            r"\s*[:=]\s*[^\s,;]{8,}"
        ),
    ),
    (
        "password",
        _compile(
            r"\b(?:password|passwort|mot\s+de\s+passe|contraseña)"
            r"\s*[:=]\s*\S+"
        ),
    ),
    (
        "phone",
        _compile(
            r"(?<!\w)"
            r"(?:\+\d{1,3}[\s.-]?)?"
            r"(?:\(?\d{2,5}\)?[\s.-]?){2,5}"
            r"\d{2,5}"
            r"(?!\w)"
        ),
    ),
)


PROMPT_INJECTION_PATTERNS: Final[
    tuple[Pattern[str], ...]
] = (
    _compile(
        r"\bignore\s+(?:all\s+)?"
        r"(?:previous|prior|system)\s+instructions?\b"
    ),
    _compile(
        r"\bforget\s+(?:all\s+)?"
        r"(?:previous|prior|system)\s+instructions?\b"
    ),
    _compile(
        r"\breveal\s+(?:the\s+)?"
        r"(?:system|developer|hidden)\s+"
        r"(?:prompt|instructions?)\b"
    ),
    _compile(
        r"\bshow\s+me\s+(?:the\s+)?"
        r"(?:system|developer|hidden)\s+"
        r"(?:prompt|instructions?)\b"
    ),
    _compile(
        r"\b(?:bypass|disable|remove)\s+(?:the\s+)?"
        r"(?:safety|security|authorization|guardrails?)\b"
    ),
    _compile(
        r"\bact\s+as\s+(?:an?\s+)?"
        r"(?:unrestricted|unfiltered|jailbroken)\b"
    ),
    _compile(
        r"\bdeveloper\s+mode\b|"
        r"\bjailbreak\b|"
        r"\bDAN\s+mode\b"
    ),
    _compile(
        r"\bignoriere\s+(?:alle\s+)?"
        r"(?:vorherigen|bisherigen|system)"
        r"[^.!?]{0,30}anweisungen\b"
    ),
    _compile(
        r"\bzeige\s+(?:mir\s+)?(?:den\s+)?"
        r"(?:systemprompt|system-prompt)\b"
    ),
    _compile(
        r"\bignorez\s+(?:toutes\s+)?"
        r"les\s+instructions?\s+précédentes?\b"
    ),
    _compile(
        r"\bignora\s+(?:todas\s+)?"
        r"las\s+instrucciones?\s+anteriores?\b"
    ),
)


EMERGENCY_PATTERNS: Final[
    tuple[Pattern[str], ...]
] = (
    _compile(
        r"\b(?:fire|smoke|gas\s+leak|"
        r"carbon\s+monoxide|explosion)\b"
    ),
    _compile(
        r"\b(?:immediate\s+danger|"
        r"life[- ]threatening|someone\s+is\s+hurt)\b"
    ),
    _compile(
        r"\b(?:feuer|rauch|gas|gasleck|gasgeruch|"
        r"explosion|lebensgefahr)\b"
    ),
    _compile(
        r"\b(?:incendie|fuite\s+de\s+gaz|"
        r"explosion|danger\s+immédiat)\b"
    ),
    _compile(
        r"\b(?:incendio|fuga\s+de\s+gas|"
        r"explosión|peligro\s+inmediato)\b"
    ),
)


DISCRIMINATION_PATTERNS: Final[
    tuple[Pattern[str], ...]
] = (
    _compile(
        r"\b(?:reject|exclude|refuse|avoid|"
        r"do\s+not\s+rent\s+to|only\s+rent\s+to)"
        r"[^.!?]{0,80}"
        r"\b(?:race|ethnicity|religion|nationality|"
        r"gender|sex|disability|pregnan(?:t|cy)|"
        r"family\s+status|sexual\s+orientation)\b"
    ),
    _compile(
        r"\b(?:ablehnen|ausschließen|"
        r"nicht\s+vermieten|nur\s+vermieten)"
        r"[^.!?]{0,80}"
        r"\b(?:herkunft|religion|nationalität|"
        r"geschlecht|behinderung|schwanger|"
        r"familienstand|sexuelle\s+orientierung)\b"
    ),
    _compile(
        r"\b(?:rejeter|exclure|"
        r"ne\s+pas\s+louer|louer\s+uniquement)"
        r"[^.!?]{0,80}"
        r"\b(?:origine|religion|nationalité|sexe|"
        r"handicap|grossesse|situation\s+familiale|"
        r"orientation\s+sexuelle)\b"
    ),
    _compile(
        r"\b(?:rechazar|excluir|"
        r"no\s+alquilar|alquilar\s+solo)"
        r"[^.!?]{0,80}"
        r"\b(?:raza|origen|religión|nacionalidad|"
        r"género|sexo|discapacidad|embarazo|"
        r"estado\s+familiar|orientación\s+sexual)\b"
    ),
)


ILLEGAL_REQUEST_PATTERNS: Final[
    tuple[Pattern[str], ...]
] = (
    _compile(
        r"\b(?:forge|fake|falsify)\s+(?:a\s+)?"
        r"(?:lease|signature|document|income\s+statement)\b"
    ),
    _compile(
        r"\b(?:break\s+in|pick\s+the\s+lock|"
        r"disable\s+the\s+alarm)\b"
    ),
    _compile(
        r"\b(?:hack|steal)\s+(?:the\s+)?"
        r"(?:tenant|landlord|property|account)\b"
    ),
    _compile(
        r"\b(?:fälsche|fälschen)\s+"
        r"(?:mietvertrag|unterschrift|dokument)\b"
    ),
)


UNSUPPORTED_DECISION_PATTERNS: Final[
    tuple[Pattern[str], ...]
] = (
    _compile(
        r"\b(?:automatically\s+)?"
        r"(?:reject|deny|approve)\s+(?:this\s+)?"
        r"(?:tenant|applicant|application)\b"
    ),
    _compile(
        r"\b(?:score|rank)\s+(?:the\s+)?"
        r"(?:tenant|applicant)s?\b"
    ),
    _compile(
        r"\b(?:lehne|genehmige)\s+(?:den\s+)?"
        r"(?:mieter|bewerber|antrag)\b"
    ),
)


MESSAGES: Final[dict[str, dict[str, str]]] = {
    "en": {
        "empty": (
            "Please enter a question so I can help."
        ),
        "too_long": (
            "Your message is too long. "
            "Please shorten it and try again."
        ),
        "injection": (
            "I cannot follow instructions that attempt to "
            "bypass security or reveal protected system information."
        ),
        "credentials": (
            "For your security, remove passwords, access tokens, "
            "payment details, and other credentials before continuing."
        ),
        "discrimination": (
            "I cannot help make discriminatory housing decisions. "
            "I can help create a fair, documented, and legally "
            "reviewed process."
        ),
        "illegal": (
            "I cannot assist with fraud, unauthorized access, "
            "or other illegal activity."
        ),
        "decision": (
            "AI should not make the final housing decision. "
            "A qualified person should review the relevant "
            "lawful criteria."
        ),
        "emergency": (
            "This may be an emergency. Move to safety and contact "
            "the local emergency services immediately. In Germany "
            "or the EU, call 112. Then notify the responsible "
            "property contact when it is safe to do so."
        ),
    },
    "de": {
        "empty": (
            "Bitte geben Sie eine Frage ein, damit ich helfen kann."
        ),
        "too_long": (
            "Ihre Nachricht ist zu lang. Bitte kürzen Sie sie "
            "und versuchen Sie es erneut."
        ),
        "injection": (
            "Ich kann keine Anweisungen befolgen, die "
            "Sicherheitsmaßnahmen umgehen oder geschützte "
            "Systeminformationen offenlegen sollen."
        ),
        "credentials": (
            "Entfernen Sie zu Ihrer Sicherheit Passwörter, "
            "Zugangstoken, Zahlungsdaten und andere Zugangsdaten."
        ),
        "discrimination": (
            "Ich kann nicht bei diskriminierenden "
            "Wohnungsentscheidungen helfen. Ich kann einen fairen, "
            "dokumentierten und rechtlich geprüften Prozess "
            "unterstützen."
        ),
        "illegal": (
            "Ich kann nicht bei Betrug, unbefugtem Zugriff oder "
            "anderen rechtswidrigen Handlungen helfen."
        ),
        "decision": (
            "Die endgültige Wohnungsentscheidung sollte nicht von "
            "einer KI getroffen werden. Eine qualifizierte Person "
            "muss die zulässigen Kriterien prüfen."
        ),
        "emergency": (
            "Dies könnte ein Notfall sein. Bringen Sie sich in "
            "Sicherheit und rufen Sie sofort den örtlichen Notdienst "
            "an. In Deutschland und der EU wählen Sie 112. "
            "Informieren Sie danach die zuständige Kontaktperson, "
            "sobald dies sicher möglich ist."
        ),
    },
    "fr": {
        "empty": (
            "Veuillez saisir une question afin que je puisse "
            "vous aider."
        ),
        "too_long": (
            "Votre message est trop long. Veuillez le raccourcir "
            "et réessayer."
        ),
        "injection": (
            "Je ne peux pas suivre des instructions visant à "
            "contourner la sécurité ou à révéler des informations "
            "système protégées."
        ),
        "credentials": (
            "Pour votre sécurité, retirez les mots de passe, "
            "jetons d’accès, informations de paiement et autres "
            "identifiants."
        ),
        "discrimination": (
            "Je ne peux pas aider à prendre une décision de "
            "logement discriminatoire. Je peux aider à établir "
            "un processus équitable et contrôlé juridiquement."
        ),
        "illegal": (
            "Je ne peux pas aider à commettre une fraude, "
            "un accès non autorisé ou une autre activité illégale."
        ),
        "decision": (
            "L’IA ne doit pas prendre la décision finale concernant "
            "le logement. Une personne qualifiée doit vérifier "
            "les critères légaux pertinents."
        ),
        "emergency": (
            "Il peut s’agir d’une urgence. Mettez-vous en sécurité "
            "et contactez immédiatement les services d’urgence "
            "locaux. En Allemagne ou dans l’UE, appelez le 112. "
            "Informez ensuite le responsable du logement lorsque "
            "cela est possible sans danger."
        ),
    },
    "es": {
        "empty": (
            "Escriba una pregunta para que pueda ayudarle."
        ),
        "too_long": (
            "Su mensaje es demasiado largo. Acórtelo e inténtelo "
            "de nuevo."
        ),
        "injection": (
            "No puedo seguir instrucciones que intenten eludir "
            "la seguridad o revelar información protegida del sistema."
        ),
        "credentials": (
            "Por su seguridad, elimine contraseñas, tokens de acceso, "
            "datos de pago y otras credenciales."
        ),
        "discrimination": (
            "No puedo ayudar a tomar decisiones de vivienda "
            "discriminatorias. Puedo ayudar a crear un proceso "
            "justo y revisado legalmente."
        ),
        "illegal": (
            "No puedo ayudar con fraude, acceso no autorizado "
            "u otras actividades ilegales."
        ),
        "decision": (
            "La IA no debe tomar la decisión final de vivienda. "
            "Una persona cualificada debe revisar los criterios "
            "legales correspondientes."
        ),
        "emergency": (
            "Esto puede ser una emergencia. Póngase a salvo y "
            "contacte inmediatamente con los servicios de emergencia "
            "locales. En Alemania o la UE, llame al 112. Después, "
            "avise al contacto responsable del inmueble cuando "
            "sea seguro hacerlo."
        ),
    },
}


def normalize_language(
    language: str | None,
) -> str:
    """Normalize a language value."""

    if not language:
        return DEFAULT_LANGUAGE

    normalized = (
        str(language)
        .strip()
        .lower()
        .replace("_", "-")
        .split("-", 1)[0]
    )

    if normalized in MESSAGES:
        return normalized

    return DEFAULT_LANGUAGE


def _message(
    language: str | None,
    key: str,
) -> str:
    """Return a localized safety message."""

    normalized = normalize_language(language)

    return MESSAGES[normalized][key]


def _matches_any(
    text: str,
    patterns: Iterable[Pattern[str]],
) -> bool:
    """Return whether any pattern matches the text."""

    return any(
        pattern.search(text) is not None
        for pattern in patterns
    )


def detected_sensitive_types(
    text: str,
) -> tuple[str, ...]:
    """Return detected sensitive data types."""

    found: list[str] = []

    for name, pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            found.append(name)

    return tuple(found)


def redact_sensitive_data(
    text: str,
) -> str:
    """Replace recognized sensitive values with placeholders."""

    sanitized = str(text).replace(
        "\x00",
        "",
    )

    replacements = {
        "email": "[EMAIL REDACTED]",
        "iban": "[IBAN REDACTED]",
        "payment_card": "[PAYMENT CARD REDACTED]",
        "access_token": "[ACCESS TOKEN REDACTED]",
        "session_cookie": "[SESSION DATA REDACTED]",
        "password": "[PASSWORD REDACTED]",
        "phone": "[PHONE REDACTED]",
    }

    for name, pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(
            replacements[name],
            sanitized,
        )

    return sanitized


def contains_prompt_injection(
    text: str,
) -> bool:
    """Return whether text contains a prompt-injection attempt."""

    return _matches_any(
        str(text),
        PROMPT_INJECTION_PATTERNS,
    )


def contains_emergency(
    text: str,
) -> bool:
    """Return whether text describes a possible emergency."""

    return _matches_any(
        str(text),
        EMERGENCY_PATTERNS,
    )


def contains_discrimination_request(
    text: str,
) -> bool:
    """Return whether discriminatory housing treatment is requested."""

    return _matches_any(
        str(text),
        DISCRIMINATION_PATTERNS,
    )


def _result(
    *,
    allowed: bool,
    action: SafetyAction,
    text: str,
    categories: Iterable[SafetyCategory],
    user_message: str | None = None,
    human_review: bool = False,
    emergency: bool = False,
) -> SafetyResult:
    """Construct an immutable safety result."""

    unique_categories = tuple(
        dict.fromkeys(categories)
    )

    if not unique_categories:
        unique_categories = (
            SafetyCategory.SAFE,
        )

    return SafetyResult(
        allowed=allowed,
        action=action,
        sanitized_text=text,
        categories=unique_categories,
        user_message=user_message,
        requires_human_review=human_review,
        is_emergency=emergency,
    )


def check_input(
    text: str | None,
    *,
    language: str = DEFAULT_LANGUAGE,
    maximum_characters: int = MAX_INPUT_CHARACTERS,
) -> SafetyResult:
    """Validate and sanitize one user message before inference."""

    original = (
        ""
        if text is None
        else str(text)
    )

    cleaned = (
        original
        .replace("\x00", "")
        .strip()
    )

    if not cleaned:
        return _result(
            allowed=False,
            action=SafetyAction.BLOCK,
            text="",
            categories=(
                SafetyCategory.EMPTY,
            ),
            user_message=_message(
                language,
                "empty",
            ),
        )

    safe_maximum = max(
        1,
        min(
            int(maximum_characters),
            MAX_INPUT_CHARACTERS,
        ),
    )

    if len(cleaned) > safe_maximum:
        return _result(
            allowed=False,
            action=SafetyAction.BLOCK,
            text=cleaned[:safe_maximum],
            categories=(
                SafetyCategory.TOO_LONG,
            ),
            user_message=_message(
                language,
                "too_long",
            ),
        )

    if contains_emergency(cleaned):
        return _result(
            allowed=False,
            action=SafetyAction.ESCALATE,
            text=redact_sensitive_data(cleaned),
            categories=(
                SafetyCategory.EMERGENCY,
            ),
            user_message=_message(
                language,
                "emergency",
            ),
            human_review=True,
            emergency=True,
        )

    if contains_prompt_injection(cleaned):
        return _result(
            allowed=False,
            action=SafetyAction.BLOCK,
            text=redact_sensitive_data(cleaned),
            categories=(
                SafetyCategory.PROMPT_INJECTION,
            ),
            user_message=_message(
                language,
                "injection",
            ),
        )

    if contains_discrimination_request(cleaned):
        return _result(
            allowed=False,
            action=SafetyAction.BLOCK,
            text=redact_sensitive_data(cleaned),
            categories=(
                SafetyCategory.DISCRIMINATION,
            ),
            user_message=_message(
                language,
                "discrimination",
            ),
            human_review=True,
        )

    if _matches_any(
        cleaned,
        ILLEGAL_REQUEST_PATTERNS,
    ):
        return _result(
            allowed=False,
            action=SafetyAction.BLOCK,
            text=redact_sensitive_data(cleaned),
            categories=(
                SafetyCategory.ILLEGAL_REQUEST,
            ),
            user_message=_message(
                language,
                "illegal",
            ),
        )

    if _matches_any(
        cleaned,
        UNSUPPORTED_DECISION_PATTERNS,
    ):
        return _result(
            allowed=False,
            action=SafetyAction.ESCALATE,
            text=redact_sensitive_data(cleaned),
            categories=(
                SafetyCategory.UNSUPPORTED_DECISION,
            ),
            user_message=_message(
                language,
                "decision",
            ),
            human_review=True,
        )

    sensitive_types = detected_sensitive_types(
        cleaned
    )

    if sensitive_types:
        categories: list[SafetyCategory] = [
            SafetyCategory.SENSITIVE_DATA
        ]

        credential_types = {
            "iban",
            "payment_card",
            "access_token",
            "session_cookie",
            "password",
        }

        if credential_types.intersection(
            sensitive_types
        ):
            categories.append(
                SafetyCategory.CREDENTIALS
            )

            return _result(
                allowed=False,
                action=SafetyAction.BLOCK,
                text=redact_sensitive_data(cleaned),
                categories=categories,
                user_message=_message(
                    language,
                    "credentials",
                ),
            )

        return _result(
            allowed=True,
            action=SafetyAction.REDACT,
            text=redact_sensitive_data(cleaned),
            categories=categories,
        )

    return _result(
        allowed=True,
        action=SafetyAction.ALLOW,
        text=cleaned,
        categories=(
            SafetyCategory.SAFE,
        ),
    )


def check_output(
    text: str | None,
    *,
    language: str = DEFAULT_LANGUAGE,
    maximum_characters: int = MAX_OUTPUT_CHARACTERS,
) -> SafetyResult:
    """Validate model output before returning it to a user."""

    original = (
        ""
        if text is None
        else str(text)
    )

    cleaned = (
        original
        .replace("\x00", "")
        .strip()
    )

    if not cleaned:
        fallback = {
            "en": (
                "The assistant could not produce a safe response. "
                "Please try again."
            ),
            "de": (
                "Der Assistent konnte keine sichere Antwort erstellen. "
                "Bitte versuchen Sie es erneut."
            ),
            "fr": (
                "L’assistant n’a pas pu produire une réponse sûre. "
                "Veuillez réessayer."
            ),
            "es": (
                "El asistente no pudo producir una respuesta segura. "
                "Inténtelo de nuevo."
            ),
        }

        return _result(
            allowed=False,
            action=SafetyAction.BLOCK,
            text="",
            categories=(
                SafetyCategory.EMPTY,
            ),
            user_message=fallback[
                normalize_language(language)
            ],
        )

    safe_maximum = max(
        1,
        min(
            int(maximum_characters),
            MAX_OUTPUT_CHARACTERS,
        ),
    )

    categories: list[SafetyCategory] = []
    action = SafetyAction.ALLOW

    if len(cleaned) > safe_maximum:
        cleaned = (
            cleaned[: safe_maximum - 1]
            .rstrip()
            + "…"
        )

        categories.append(
            SafetyCategory.TOO_LONG
        )

        action = SafetyAction.REDACT

    if contains_prompt_injection(cleaned):
        return _result(
            allowed=False,
            action=SafetyAction.BLOCK,
            text="",
            categories=(
                SafetyCategory.PROMPT_INJECTION,
            ),
            user_message=_message(
                language,
                "injection",
            ),
            human_review=True,
        )

    if contains_discrimination_request(cleaned):
        return _result(
            allowed=False,
            action=SafetyAction.BLOCK,
            text="",
            categories=(
                SafetyCategory.DISCRIMINATION,
            ),
            user_message=_message(
                language,
                "discrimination",
            ),
            human_review=True,
        )

    if _matches_any(
        cleaned,
        ILLEGAL_REQUEST_PATTERNS,
    ):
        return _result(
            allowed=False,
            action=SafetyAction.BLOCK,
            text="",
            categories=(
                SafetyCategory.ILLEGAL_REQUEST,
            ),
            user_message=_message(
                language,
                "illegal",
            ),
            human_review=True,
        )

    sensitive_types = detected_sensitive_types(
        cleaned
    )

    if sensitive_types:
        cleaned = redact_sensitive_data(
            cleaned
        )

        categories.append(
            SafetyCategory.SENSITIVE_DATA
        )

        action = SafetyAction.REDACT

        credential_types = {
            "iban",
            "payment_card",
            "access_token",
            "session_cookie",
            "password",
        }

        if credential_types.intersection(
            sensitive_types
        ):
            categories.append(
                SafetyCategory.CREDENTIALS
            )

    if not categories:
        categories.append(
            SafetyCategory.SAFE
        )

    return _result(
        allowed=True,
        action=action,
        text=cleaned,
        categories=categories,
    )


def safe_fallback_message(
    result: SafetyResult,
    *,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """Return a safe response for a blocked safety result."""

    if result.user_message:
        return result.user_message

    normalized = normalize_language(
        language
    )

    fallbacks = {
        "en": (
            "I cannot safely complete that request. "
            "Please rephrase it without sensitive information."
        ),
        "de": (
            "Ich kann diese Anfrage nicht sicher bearbeiten. "
            "Bitte formulieren Sie sie ohne sensible Informationen neu."
        ),
        "fr": (
            "Je ne peux pas traiter cette demande en toute sécurité. "
            "Veuillez la reformuler sans informations sensibles."
        ),
        "es": (
            "No puedo procesar esta solicitud de forma segura. "
            "Reformúlela sin información sensible."
        ),
    }

    return fallbacks[normalized]


__all__ = [
    "DEFAULT_LANGUAGE",
    "MAX_INPUT_CHARACTERS",
    "MAX_OUTPUT_CHARACTERS",
    "SafetyAction",
    "SafetyCategory",
    "SafetyResult",
    "check_input",
    "check_output",
    "contains_discrimination_request",
    "contains_emergency",
    "contains_prompt_injection",
    "detected_sensitive_types",
    "normalize_language",
    "redact_sensitive_data",
    "safe_fallback_message",
]