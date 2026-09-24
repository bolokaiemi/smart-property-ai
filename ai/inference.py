"""Model inference layer for Smart Property AI.

This module provides:

- A local, dependency-free inference engine
- An optional OpenAI-compatible API engine
- Automatic local fallback
- Synchronous and asynchronous functions

Input safety, authorization, prompt construction, and output safety
remain the responsibility of ai/assistant.py.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Mapping, Protocol, Sequence


DEFAULT_PROVIDER: Final[str] = "local"
DEFAULT_LOCAL_MODEL: Final[str] = "smart-property-local-v1"

DEFAULT_TIMEOUT_SECONDS: Final[float] = 30.0
MAX_TIMEOUT_SECONDS: Final[float] = 120.0

DEFAULT_MAX_NEW_TOKENS: Final[int] = 600
MAX_NEW_TOKENS: Final[int] = 2_000

MAX_RESPONSE_CHARACTERS: Final[int] = 8_000
MAX_MESSAGE_CHARACTERS: Final[int] = 8_000
MAX_MESSAGES: Final[int] = 20


class InferenceStatus(StrEnum):
    """Possible inference outcomes."""

    SUCCESS = "success"
    FALLBACK = "fallback"
    ERROR = "error"


class InferenceError(RuntimeError):
    """Base exception for inference failures."""


class InferenceConfigurationError(InferenceError):
    """Raised when the provider configuration is invalid."""


class InferenceProviderError(InferenceError):
    """Raised when a provider cannot return a response."""


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    """Provider-independent inference request."""

    messages: Sequence[Mapping[str, object]]

    language: str = "en"
    model: str | None = None

    temperature: float = 0.2

    # Primary output-length setting used by local/Hugging Face-style
    # inference engines.
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS

    # Backward-compatible alias for callers that already use max_tokens.
    # When provided, it takes precedence over max_new_tokens.
    max_tokens: int | None = None

    metadata: Mapping[str, object] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class InferenceResponse:
    """Normalized inference response."""

    text: str
    provider: str
    model: str
    status: InferenceStatus
    latency_ms: float

    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None

    used_fallback: bool = False


def _output_token_limit(
    request: InferenceRequest,
) -> int:
    """Return the safely bounded response-token limit.

    ``max_tokens`` is retained for existing callers. New code should use
    ``max_new_tokens`` because it clearly represents newly generated output
    rather than the combined prompt and response length.
    """

    requested_limit = (
        request.max_tokens
        if request.max_tokens is not None
        else request.max_new_tokens
    )

    return _bounded_int(
        requested_limit,
        1,
        MAX_NEW_TOKENS,
    )


class InferenceEngine(Protocol):
    """Interface implemented by inference engines."""

    provider_name: str

    def generate(
        self,
        request: InferenceRequest,
    ) -> InferenceResponse:
        """Generate one response."""


def _normalize_language(
    language: str | None,
) -> str:
    """Normalize a supported language code."""

    value = (
        str(language or "en")
        .strip()
        .lower()
        .replace("_", "-")
    )

    code = value.split("-", 1)[0]

    if code in {
        "en",
        "de",
        "fr",
        "es",
    }:
        return code

    return "en"


def _clean_text(
    value: object,
    maximum: int = MAX_MESSAGE_CHARACTERS,
) -> str:
    """Normalize and limit a text value."""

    text = (
        str(value or "")
        .replace("\x00", "")
        .strip()
    )

    if len(text) <= maximum:
        return text

    return (
        text[: maximum - 1]
        .rstrip()
        + "…"
    )


def _normalize_messages(
    messages: Sequence[Mapping[str, object]],
) -> list[dict[str, str]]:
    """Validate and normalize chat messages."""

    if not messages:
        raise ValueError(
            "At least one inference message is required."
        )

    normalized: list[dict[str, str]] = []

    allowed_roles = {
        "system",
        "user",
        "assistant",
    }

    for message in messages[-MAX_MESSAGES:]:
        role = str(
            message.get("role", "")
        ).strip().lower()

        content = _clean_text(
            message.get("content", "")
        )

        if role not in allowed_roles:
            continue

        if not content:
            continue

        normalized.append(
            {
                "role": role,
                "content": content,
            }
        )

    if not normalized:
        raise ValueError(
            "No valid inference messages were supplied."
        )

    if normalized[-1]["role"] != "user":
        raise ValueError(
            "The final inference message must have "
            "the user role."
        )

    return normalized


def _latest_user_message(
    messages: Sequence[Mapping[str, object]],
) -> str:
    """Return the most recent user message."""

    for message in reversed(messages):
        role = str(
            message.get("role", "")
        ).strip().lower()

        if role == "user":
            return _clean_text(
                message.get("content", ""),
                4_000,
            )

    return ""


def _bounded_float(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """Constrain a float to a safe range."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum

    if number != number:
        number = minimum

    if number in {
        float("inf"),
        float("-inf"),
    }:
        number = minimum

    return max(
        minimum,
        min(
            number,
            maximum,
        ),
    )


def _bounded_int(
    value: int,
    minimum: int,
    maximum: int,
) -> int:
    """Constrain an integer to a safe range."""

    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum

    return max(
        minimum,
        min(
            number,
            maximum,
        ),
    )


LOCAL_RESPONSES: Final[
    dict[str, dict[str, str]]
] = {
    "en": {
        "greeting": (
            "Hello! I can help with apartment searches, "
            "applications, viewings, leases, payments, "
            "maintenance requests, complaints, documents, "
            "and landlord or tenant portal guidance. "
            "What would you like to do?"
        ),
        "capabilities": (
            "I can guide you through property searches, "
            "rental applications, appointments, leases, "
            "payments, maintenance, complaints, documents, "
            "and portal features. Private account information "
            "requires login and authorization."
        ),
        "search": (
            "I can help you search for an apartment. "
            "Tell me the city, maximum monthly rent, number "
            "of bedrooms, move-in date, and any accessibility "
            "requirements."
        ),
        "maintenance": (
            "For maintenance help, describe the problem, "
            "its location, when it started, and whether it "
            "creates an immediate safety risk. Do not include "
            "passwords, payment details, or identity numbers."
        ),
        "payment": (
            "You can review verified rent and payment "
            "information in the tenant Payments section. "
            "I cannot confirm an amount or due date unless "
            "the application supplies an authorized record."
        ),
        "lease": (
            "You can review verified lease dates and terms "
            "in the tenant Lease section. Important legal "
            "questions should also be reviewed by a qualified "
            "professional."
        ),
        "application": (
            "I can explain the rental application process "
            "and help you complete the form. Do not upload "
            "unnecessary sensitive information, and review "
            "all details before submitting."
        ),
        "appointment": (
            "I can help with viewing appointments. Provide "
            "the listing, preferred date and time, and contact "
            "preference. The appointment is confirmed only "
            "after the application reports success."
        ),
        "complaint": (
            "I can help structure a clear complaint with "
            "the issue, relevant dates, location, evidence, "
            "and requested resolution. Avoid adding "
            "unnecessary private information."
        ),
        "login": (
            "Please log in to access private account, tenancy, "
            "application, payment, document, or landlord "
            "information."
        ),
        "fallback": (
            "I can help with Smart Property AI property and "
            "tenancy tasks. Please describe whether you need "
            "property search, application, appointment, lease, "
            "payment, maintenance, complaint, document, tenant, "
            "or landlord help."
        ),
    },

    "de": {
        "greeting": (
            "Hallo! Ich kann bei Wohnungssuche, Bewerbungen, "
            "Besichtigungen, Mietverträgen, Zahlungen, "
            "Wartungsanfragen, Beschwerden, Dokumenten sowie "
            "im Vermieter- oder Mieterportal helfen. "
            "Was möchten Sie tun?"
        ),
        "capabilities": (
            "Ich kann Sie bei Wohnungssuche, Mietbewerbungen, "
            "Terminen, Mietverträgen, Zahlungen, Wartung, "
            "Beschwerden, Dokumenten und Portal-Funktionen "
            "unterstützen. Private Kontoinformationen erfordern "
            "Anmeldung und Berechtigung."
        ),
        "search": (
            "Ich kann Ihnen bei der Wohnungssuche helfen. "
            "Nennen Sie Stadt, maximale Monatsmiete, Zimmerzahl, "
            "Einzugsdatum und mögliche Anforderungen an die "
            "Barrierefreiheit."
        ),
        "maintenance": (
            "Beschreiben Sie für eine Wartungsanfrage das "
            "Problem, den Ort, den Beginn und ob ein "
            "unmittelbares Sicherheitsrisiko besteht. "
            "Geben Sie keine Passwörter, Zahlungsdaten oder "
            "Ausweisnummern an."
        ),
        "payment": (
            "Geprüfte Miet- und Zahlungsinformationen finden "
            "Sie im Bereich Zahlungen des Mieterportals. "
            "Ohne einen autorisierten Datensatz kann ich keinen "
            "Betrag oder Fälligkeitstermin bestätigen."
        ),
        "lease": (
            "Geprüfte Mietvertragsdaten und Bedingungen finden "
            "Sie im Bereich Mietvertrag. Wichtige Rechtsfragen "
            "sollten zusätzlich von einer qualifizierten "
            "Fachperson geprüft werden."
        ),
        "application": (
            "Ich kann das Bewerbungsverfahren erklären und "
            "beim Ausfüllen helfen. Laden Sie keine unnötigen "
            "sensiblen Daten hoch und prüfen Sie alle Angaben "
            "vor dem Absenden."
        ),
        "appointment": (
            "Ich kann bei Besichtigungsterminen helfen. "
            "Nennen Sie Inserat, bevorzugtes Datum, Uhrzeit "
            "und Kontaktweg. Der Termin ist erst bestätigt, "
            "wenn die Anwendung den Erfolg meldet."
        ),
        "complaint": (
            "Ich kann eine klare Beschwerde mit Problem, Datum, "
            "Ort, Nachweisen und gewünschter Lösung strukturieren. "
            "Vermeiden Sie unnötige private Angaben."
        ),
        "login": (
            "Bitte melden Sie sich an, um auf private Konto-, "
            "Miet-, Bewerbungs-, Zahlungs-, Dokument- oder "
            "Vermieterinformationen zuzugreifen."
        ),
        "fallback": (
            "Ich kann bei Immobilien- und Mietaufgaben in "
            "Smart Property AI helfen. Beschreiben Sie bitte, "
            "ob Sie Hilfe bei Suche, Bewerbung, Termin, "
            "Mietvertrag, Zahlung, Wartung, Beschwerde, "
            "Dokumenten, Mieter- oder Vermieterportal benötigen."
        ),
    },

    "fr": {
        "greeting": (
            "Bonjour ! Je peux vous aider pour la recherche "
            "de logement, les candidatures, les visites, les "
            "baux, les paiements, la maintenance, les "
            "réclamations, les documents et les portails "
            "locataire ou propriétaire. Que souhaitez-vous faire ?"
        ),
        "capabilities": (
            "Je peux vous guider pour la recherche de biens, "
            "les candidatures, les rendez-vous, les baux, "
            "les paiements, la maintenance, les réclamations, "
            "les documents et les fonctions du portail. "
            "Les données privées nécessitent une connexion "
            "et une autorisation."
        ),
        "search": (
            "Je peux vous aider à rechercher un logement. "
            "Indiquez la ville, le loyer mensuel maximum, "
            "le nombre de chambres, la date d’emménagement "
            "et les besoins d’accessibilité."
        ),
        "maintenance": (
            "Pour une demande de maintenance, décrivez le "
            "problème, son emplacement, sa date de début et "
            "tout risque immédiat. N’indiquez pas de mot de "
            "passe, de données de paiement ou de numéro "
            "d’identité."
        ),
        "payment": (
            "Consultez les informations vérifiées dans la "
            "section Paiements du portail locataire. Je ne "
            "peux confirmer un montant ou une échéance que "
            "si l’application fournit un dossier autorisé."
        ),
        "lease": (
            "Consultez les dates et conditions vérifiées dans "
            "la section Bail. Les questions juridiques "
            "importantes doivent également être examinées par "
            "un professionnel qualifié."
        ),
        "application": (
            "Je peux expliquer la procédure de candidature "
            "et vous aider à remplir le formulaire. Ne "
            "transmettez pas de données sensibles inutiles "
            "et vérifiez les informations avant l’envoi."
        ),
        "appointment": (
            "Je peux vous aider à organiser une visite. "
            "Indiquez l’annonce, la date et l’heure souhaitées "
            "et le moyen de contact. Le rendez-vous n’est "
            "confirmé qu’après confirmation de l’application."
        ),
        "complaint": (
            "Je peux structurer une réclamation claire avec "
            "le problème, les dates, le lieu, les preuves et "
            "la solution demandée. Évitez les informations "
            "privées inutiles."
        ),
        "login": (
            "Veuillez vous connecter pour accéder aux "
            "informations privées du compte, de la location, "
            "de la candidature, des paiements, des documents "
            "ou du propriétaire."
        ),
        "fallback": (
            "Je peux vous aider pour les tâches immobilières "
            "et locatives de Smart Property AI. Précisez si "
            "vous avez besoin d’aide pour une recherche, une "
            "candidature, un rendez-vous, un bail, un paiement, "
            "la maintenance, une réclamation, un document, "
            "le portail locataire ou propriétaire."
        ),
    },

    "es": {
        "greeting": (
            "¡Hola! Puedo ayudar con la búsqueda de viviendas, "
            "solicitudes, visitas, contratos, pagos, "
            "mantenimiento, reclamaciones, documentos y los "
            "portales de inquilinos o propietarios. "
            "¿Qué desea hacer?"
        ),
        "capabilities": (
            "Puedo orientarle en búsquedas de propiedades, "
            "solicitudes, citas, contratos, pagos, "
            "mantenimiento, reclamaciones, documentos y "
            "funciones del portal. La información privada "
            "requiere inicio de sesión y autorización."
        ),
        "search": (
            "Puedo ayudarle a buscar una vivienda. Indique "
            "la ciudad, el alquiler mensual máximo, el número "
            "de dormitorios, la fecha de entrada y las "
            "necesidades de accesibilidad."
        ),
        "maintenance": (
            "Para solicitar mantenimiento, describa el "
            "problema, su ubicación, cuándo comenzó y si existe "
            "un riesgo inmediato. No incluya contraseñas, datos "
            "de pago ni números de identidad."
        ),
        "payment": (
            "Consulte la información verificada en la sección "
            "Pagos del portal del inquilino. No puedo confirmar "
            "un importe o vencimiento sin un registro autorizado "
            "de la aplicación."
        ),
        "lease": (
            "Consulte las fechas y condiciones verificadas en "
            "la sección Contrato. Las cuestiones legales "
            "importantes también deben ser revisadas por un "
            "profesional cualificado."
        ),
        "application": (
            "Puedo explicar el proceso de solicitud y ayudarle "
            "a completar el formulario. No cargue datos "
            "sensibles innecesarios y revise todo antes "
            "de enviarlo."
        ),
        "appointment": (
            "Puedo ayudarle con las citas de visita. Indique "
            "el anuncio, la fecha y hora preferidas y el método "
            "de contacto. La cita solo queda confirmada cuando "
            "la aplicación informa del éxito."
        ),
        "complaint": (
            "Puedo ayudarle a estructurar una reclamación clara "
            "con el problema, las fechas, la ubicación, las "
            "pruebas y la solución solicitada. Evite información "
            "privada innecesaria."
        ),
        "login": (
            "Inicie sesión para acceder a información privada "
            "de la cuenta, alquiler, solicitud, pagos, "
            "documentos o propietario."
        ),
        "fallback": (
            "Puedo ayudar con las tareas inmobiliarias y de "
            "alquiler de Smart Property AI. Indique si necesita "
            "ayuda con búsqueda, solicitud, cita, contrato, "
            "pago, mantenimiento, reclamación, documentos o "
            "los portales de inquilino o propietario."
        ),
    },
}


INTENT_PATTERNS: Final[
    tuple[tuple[str, re.Pattern[str]], ...]
] = (
    (
        "greeting",
        re.compile(
            r"^(?:hello|hi|hey|hallo|"
            r"guten\s+(?:tag|morgen|abend)|"
            r"bonjour|salut|hola|buenos\s+días)"
            r"[!.?\s]*$",
            re.IGNORECASE,
        ),
    ),
    (
        "capabilities",
        re.compile(
            r"\b(?:capabilit(?:y|ies)|"
            r"what\s+can\s+you|"
            r"was\s+kannst\s+du|"
            r"que\s+pouvez-vous|"
            r"qué\s+puedes)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "search",
        re.compile(
            r"\b(?:find|search|apartment|property|"
            r"wohnung|immobilie|appartement|logement|"
            r"buscar|apartamento|vivienda)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "maintenance",
        re.compile(
            r"\b(?:maintenance|repair|broken|"
            r"wartung|reparatur|kaputt|"
            r"entretien|réparation|"
            r"mantenimiento|reparación)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "payment",
        re.compile(
            r"\b(?:payment|pay|rent\s+due|"
            r"zahlung|bezahlen|miete\s+fällig|"
            r"paiement|payer|pago|pagar)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "lease",
        re.compile(
            r"\b(?:lease|tenancy|mietvertrag|"
            r"mietverhältnis|bail|location|"
            r"contrato|arrendamiento)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "application",
        re.compile(
            r"\b(?:application|apply|bewerbung|antrag|"
            r"candidature|demande|solicitud|solicitar)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "appointment",
        re.compile(
            r"\b(?:appointment|viewing|besichtigung|termin|"
            r"visite|rendez-vous|cita|visita)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "complaint",
        re.compile(
            r"\b(?:complaint|complain|beschwerde|"
            r"réclamation|plainte|reclamación|queja)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "login",
        re.compile(
            r"\b(?:login|log\s+in|sign\s+in|anmelden|"
            r"connexion|connecter|iniciar\s+sesión)\b",
            re.IGNORECASE,
        ),
    ),
)


def _local_intent(
    message: str,
) -> str:
    """Return the first matching local intent."""

    for intent, pattern in INTENT_PATTERNS:
        if pattern.search(message):
            return intent

    return "fallback"


class LocalInferenceEngine:
    """Dependency-free local inference engine."""

    provider_name = "local"

    def __init__(
        self,
        model: str = DEFAULT_LOCAL_MODEL,
    ) -> None:
        self.model = (
            _clean_text(
                model,
                120,
            )
            or DEFAULT_LOCAL_MODEL
        )

    def generate(
        self,
        request: InferenceRequest,
    ) -> InferenceResponse:
        """Generate a deterministic local response."""

        started = time.perf_counter()

        messages = _normalize_messages(
            request.messages
        )

        language = _normalize_language(
            request.language
        )

        user_message = _latest_user_message(
            messages
        )

        intent = _local_intent(
            user_message
        )

        response_text = (
            LOCAL_RESPONSES[language][intent]
        )

        latency_ms = round(
            (
                time.perf_counter()
                - started
            )
            * 1_000,
            3,
        )

        return InferenceResponse(
            text=response_text,
            provider=self.provider_name,
            model=(
                request.model
                or self.model
            ),
            status=InferenceStatus.FALLBACK,
            latency_ms=latency_ms,
            finish_reason="stop",
            used_fallback=True,
        )


class CompatibleAPIInferenceEngine:
    """OpenAI-compatible chat-completions engine."""

    provider_name = "compatible_api"

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.api_url = self._validate_url(
            api_url
        )

        self.api_key = str(
            api_key or ""
        ).strip()

        self.model = _clean_text(
            model,
            200,
        )

        self.timeout_seconds = _bounded_float(
            timeout_seconds,
            1.0,
            MAX_TIMEOUT_SECONDS,
        )

        if not self.api_key:
            raise InferenceConfigurationError(
                "AI_API_KEY is required."
            )

        if not self.model:
            raise InferenceConfigurationError(
                "AI_MODEL is required."
            )

    @staticmethod
    def _validate_url(
        value: str,
    ) -> str:
        """Validate the configured provider URL."""

        url = str(
            value or ""
        ).strip()

        parsed = urllib.parse.urlparse(
            url
        )

        if (
            parsed.scheme
            not in {"http", "https"}
            or not parsed.netloc
        ):
            raise InferenceConfigurationError(
                "AI_API_URL must be a valid "
                "HTTP or HTTPS URL."
            )

        hostname = (
            parsed.hostname or ""
        ).lower()

        local_hosts = {
            "localhost",
            "127.0.0.1",
            "::1",
        }

        if (
            parsed.scheme != "https"
            and hostname not in local_hosts
        ):
            raise InferenceConfigurationError(
                "Remote AI_API_URL values "
                "must use HTTPS."
            )

        return url

    def generate(
        self,
        request: InferenceRequest,
    ) -> InferenceResponse:
        """Generate a response using the configured API."""

        started = time.perf_counter()

        messages = _normalize_messages(
            request.messages
        )

        model = (
            _clean_text(
                request.model,
                200,
            )
            or self.model
        )

        payload = {
            "model": model,
            "messages": messages,
            "temperature": _bounded_float(
                request.temperature,
                0.0,
                1.5,
            ),
            # OpenAI-compatible chat-completions APIs commonly expect the
            # legacy name max_tokens. The internal configuration uses the
            # clearer max_new_tokens name and maps it here.
            "max_tokens": _output_token_limit(
                request
            ),
        }

        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        http_request = urllib.request.Request(
            self.api_url,
            data=body,
            headers={
                "Authorization": (
                    f"Bearer {self.api_key}"
                ),
                "Content-Type": (
                    "application/json"
                ),
                "Accept": (
                    "application/json"
                ),
                "User-Agent": (
                    "Smart-Property-AI/1.0"
                ),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                http_request,
                timeout=self.timeout_seconds,
            ) as response:
                response_body = response.read(
                    1_000_000
                )

        except urllib.error.HTTPError as exc:
            raise InferenceProviderError(
                "The AI provider returned "
                f"HTTP {exc.code}."
            ) from exc

        except urllib.error.URLError as exc:
            raise InferenceProviderError(
                "The AI provider could not be reached."
            ) from exc

        except TimeoutError as exc:
            raise InferenceProviderError(
                "The AI provider request timed out."
            ) from exc

        try:
            data = json.loads(
                response_body.decode("utf-8")
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise InferenceProviderError(
                "The AI provider returned invalid JSON."
            ) from exc

        text, finish_reason = (
            self._extract_response(data)
        )

        usage = (
            data.get("usage")
            if isinstance(data, dict)
            else None
        )

        input_tokens = None
        output_tokens = None

        if isinstance(usage, dict):
            input_tokens = self._optional_int(
                usage.get(
                    "prompt_tokens",
                    usage.get("input_tokens"),
                )
            )

            output_tokens = self._optional_int(
                usage.get(
                    "completion_tokens",
                    usage.get("output_tokens"),
                )
            )

        latency_ms = round(
            (
                time.perf_counter()
                - started
            )
            * 1_000,
            3,
        )

        return InferenceResponse(
            text=text,
            provider=self.provider_name,
            model=model,
            status=InferenceStatus.SUCCESS,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=finish_reason,
            used_fallback=False,
        )

    @staticmethod
    def _optional_int(
        value: object,
    ) -> int | None:
        """Convert an optional token count."""

        try:
            return max(
                0,
                int(value),
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    @staticmethod
    def _extract_response(
        data: object,
    ) -> tuple[str, str | None]:
        """Extract text from a compatible API response."""

        if not isinstance(data, dict):
            raise InferenceProviderError(
                "The AI provider response "
                "has an invalid structure."
            )

        choices = data.get("choices")

        if (
            isinstance(choices, list)
            and choices
        ):
            first = choices[0]

            if isinstance(first, dict):
                message = first.get("message")
                finish_reason = first.get(
                    "finish_reason"
                )

                if isinstance(message, dict):
                    content = message.get(
                        "content"
                    )

                    if (
                        isinstance(content, str)
                        and content.strip()
                    ):
                        return (
                            _clean_text(
                                content,
                                MAX_RESPONSE_CHARACTERS,
                            ),
                            (
                                str(finish_reason)
                                if finish_reason is not None
                                else None
                            ),
                        )

                direct_text = first.get(
                    "text"
                )

                if (
                    isinstance(direct_text, str)
                    and direct_text.strip()
                ):
                    return (
                        _clean_text(
                            direct_text,
                            MAX_RESPONSE_CHARACTERS,
                        ),
                        (
                            str(finish_reason)
                            if finish_reason is not None
                            else None
                        ),
                    )

        output_text = data.get(
            "output_text"
        )

        if (
            isinstance(output_text, str)
            and output_text.strip()
        ):
            return (
                _clean_text(
                    output_text,
                    MAX_RESPONSE_CHARACTERS,
                ),
                None,
            )

        raise InferenceProviderError(
            "The AI provider response "
            "did not contain text."
        )


class ResilientInferenceEngine:
    """Use a primary engine with a local fallback."""

    provider_name = "resilient"

    def __init__(
        self,
        primary: InferenceEngine,
        fallback: InferenceEngine | None = None,
    ) -> None:
        self.primary = primary

        self.fallback = (
            fallback
            or LocalInferenceEngine()
        )

    def generate(
        self,
        request: InferenceRequest,
    ) -> InferenceResponse:
        """Generate with the primary engine or local fallback."""

        try:
            return self.primary.generate(
                request
            )

        except (
            InferenceError,
            OSError,
            ValueError,
        ):
            return self.fallback.generate(
                request
            )


def create_inference_engine(
    provider: str | None = None,
    *,
    allow_fallback: bool = True,
) -> InferenceEngine:
    """Create an inference engine from environment settings.

    Environment variables:

    AI_PROVIDER
        local or compatible_api

    AI_API_URL
        Full compatible chat-completions endpoint

    AI_API_KEY
        Provider credential

    AI_MODEL
        Model name

    AI_TIMEOUT_SECONDS
        Timeout between 1 and 120 seconds
    """

    selected = str(
        provider
        or os.getenv(
            "AI_PROVIDER",
            DEFAULT_PROVIDER,
        )
    ).strip().lower()

    if selected in {
        "",
        "local",
        "offline",
        "rule_based",
    }:
        return LocalInferenceEngine(
            model=os.getenv(
                "AI_MODEL",
                DEFAULT_LOCAL_MODEL,
            )
        )

    if selected in {
        "compatible_api",
        "openai_compatible",
        "api",
    }:
        timeout_value = os.getenv(
            "AI_TIMEOUT_SECONDS",
            str(DEFAULT_TIMEOUT_SECONDS),
        )

        try:
            timeout = float(
                timeout_value
            )
        except ValueError:
            timeout = DEFAULT_TIMEOUT_SECONDS

        primary = CompatibleAPIInferenceEngine(
            api_url=os.getenv(
                "AI_API_URL",
                "",
            ),
            api_key=os.getenv(
                "AI_API_KEY",
                "",
            ),
            model=os.getenv(
                "AI_MODEL",
                "",
            ),
            timeout_seconds=timeout,
        )

        if allow_fallback:
            return ResilientInferenceEngine(
                primary
            )

        return primary

    raise InferenceConfigurationError(
        f"Unsupported AI provider: {selected}"
    )


def generate_response(
    messages: Sequence[Mapping[str, object]],
    *,
    language: str = "en",
    model: str | None = None,
    temperature: float = 0.2,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    max_tokens: int | None = None,
    engine: InferenceEngine | None = None,
    metadata: Mapping[str, object] | None = None,
) -> InferenceResponse:
    """Generate a response using the selected engine."""

    active_engine = (
        engine
        or create_inference_engine()
    )

    request = InferenceRequest(
        messages=messages,
        language=_normalize_language(
            language
        ),
        model=model,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
        max_tokens=max_tokens,
        metadata=metadata or {},
    )

    return active_engine.generate(
        request
    )


async def generate_response_async(
    messages: Sequence[Mapping[str, object]],
    *,
    language: str = "en",
    model: str | None = None,
    temperature: float = 0.2,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    max_tokens: int | None = None,
    engine: InferenceEngine | None = None,
    metadata: Mapping[str, object] | None = None,
) -> InferenceResponse:
    """Run blocking inference outside the FastAPI event loop."""

    return await asyncio.to_thread(
        generate_response,
        messages,
        language=language,
        model=model,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
        max_tokens=max_tokens,
        engine=engine,
        metadata=metadata,
    )


def engine_health(
    engine: InferenceEngine | None = None,
) -> dict[str, object]:
    """Return non-sensitive health information."""

    active_engine = (
        engine
        or create_inference_engine()
    )

    return {
        "available": True,
        "provider": getattr(
            active_engine,
            "provider_name",
            "unknown",
        ),
        "fallback_enabled": isinstance(
            active_engine,
            ResilientInferenceEngine,
        ),
    }


__all__ = [
    "CompatibleAPIInferenceEngine",
    "DEFAULT_LOCAL_MODEL",
    "DEFAULT_MAX_NEW_TOKENS",
    "DEFAULT_PROVIDER",
    "InferenceConfigurationError",
    "InferenceEngine",
    "InferenceError",
    "InferenceProviderError",
    "InferenceRequest",
    "InferenceResponse",
    "InferenceStatus",
    "LocalInferenceEngine",
    "ResilientInferenceEngine",
    "create_inference_engine",
    "engine_health",
    "generate_response",
    "generate_response_async",
]
