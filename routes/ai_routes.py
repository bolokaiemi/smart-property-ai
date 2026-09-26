"""
Smart Property AI assistant routes.

File:
    routes/ai_routes.py

Routes:
    GET  /ai-assistant
    GET  /assistant
    POST /api/ai/chat
    POST /api/ai/clear
    GET  /api/ai/status
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    status,
)
# Guardrail service for professional tone
from services.guardrail_service import apply_professional_guardrails
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field


logger = logging.getLogger("smart_property_ai")

router = APIRouter(
    tags=["AI Assistant"],
)

templates = Jinja2Templates(
    directory="templates",
)


MAX_CONVERSATION_MESSAGES = 20
MAX_MESSAGE_LENGTH = 4000


DEFAULT_AI_MODEL = "smart-property-standard"

AVAILABLE_AI_MODELS: dict[str, dict[str, str]] = {
    "smart-property-standard": {
        "value": "smart-property-standard",
        "label": "Smart Property AI — Standard",
        "description": "Balanced local property guidance.",
    },
    "smart-property-fast": {
        "value": "smart-property-fast",
        "label": "Smart Property AI — Fast",
        "description": "Shorter responses for quick questions.",
    },
    "smart-property-detailed": {
        "value": "smart-property-detailed",
        "label": "Smart Property AI — Detailed",
        "description": "More detailed step-by-step guidance.",
    },
}


SUPPORTED_LANGUAGES = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "nl": "Nederlands",
    "pl": "Polski",
    "tr": "Türkçe",
    "ar": "العربية",
    "fa": "فارسی",
    "ur": "اردو",
    "he": "עברית",
    "hi": "हिन्दी",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
    "ru": "Русский",
    "uk": "Українська",
    "sw": "Kiswahili",
}


# ============================================================
# Request and response models
# ============================================================

class AIChatRequest(BaseModel):
    """Validated request received from an AI chat interface."""

    message: str = Field(
        min_length=1,
        max_length=MAX_MESSAGE_LENGTH,
    )

    language: str = Field(
        default="en",
        min_length=2,
        max_length=15,
    )

    conversation_id: str | None = Field(
        default=None,
        max_length=100,
    )

    model: str = Field(
        default=DEFAULT_AI_MODEL,
        min_length=1,
        max_length=80,
    )

    page_context: str | None = Field(
        default=None,
        max_length=500,
    )

    consent: bool = False


class AIChatResponse(BaseModel):
    """Validated response returned by the AI chat endpoint."""

    success: bool
    reply: str
    conversation_id: str
    language: str
    model: str
    human_review_required: bool = False
    emergency: bool = False
    disclaimer: str | None = None


# ============================================================
# General helpers
# ============================================================

def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-formatted string."""

    return datetime.now(
        timezone.utc
    ).isoformat()


def get_session(
    request: Request,
) -> Any:
    """
    Return the current request session.

    SessionMiddleware must be configured in app.py.
    """

    try:
        return request.session

    except (
        AssertionError,
        RuntimeError,
    ) as exc:
        logger.exception(
            "SessionMiddleware is unavailable."
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "SessionMiddleware must be configured "
                "before using the AI assistant."
            ),
        ) from exc


def get_current_user(
    request: Request,
) -> Any | None:
    """Return the current authenticated user when available."""

    state_user = getattr(
        request.state,
        "user",
        None,
    )

    if state_user is not None:
        return state_user

    session = get_session(request)

    return session.get("user")


def get_current_user_id(
    request: Request,
) -> str | None:
    """Return an identifier for the signed-in user."""

    user = get_current_user(request)

    if isinstance(user, dict):
        user_id = (
            user.get("id")
            or user.get("user_id")
            or user.get("username")
        )

        if user_id:
            return str(user_id)

    if user is not None:
        user_id = (
            getattr(user, "id", None)
            or getattr(user, "user_id", None)
            or getattr(user, "username", None)
        )

        if user_id:
            return str(user_id)

        if isinstance(user, str) and user:
            return user

    session = get_session(request)

    user_id = (
        session.get("user_id")
        or session.get(
            "authenticated_user_id"
        )
        or session.get("username")
    )

    return (
        str(user_id)
        if user_id
        else None
    )


def is_authenticated(
    request: Request,
) -> bool:
    """Return True when a user is signed in."""

    return (
        get_current_user_id(request)
        is not None
    )


def ensure_csrf_token(
    request: Request,
) -> str:
    """Return the session CSRF token, creating it when necessary."""

    session = get_session(request)

    csrf_token = session.get(
        "csrf_token"
    )

    if not csrf_token:
        csrf_token = secrets.token_urlsafe(
            32
        )

        session["csrf_token"] = (
            csrf_token
        )

    return str(csrf_token)


def verify_csrf_token(
    request: Request,
    submitted_token: str | None,
) -> None:
    """
    Validate the CSRF token submitted in the X-CSRF-Token header.

    Token values are never written to application logs.
    """

    session = get_session(request)

    expected_token = session.get(
        "csrf_token"
    )

    if not expected_token:
        logger.warning(
            "AI request rejected because the session "
            "CSRF token is unavailable."
        )

        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Your security session is unavailable. "
                "Refresh the page and try again."
            ),
        )

    if not submitted_token:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Missing form security token."
            ),
        )

    if not secrets.compare_digest(
        str(expected_token),
        str(submitted_token),
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Invalid form security token."
            ),
        )


def sanitize_message(
    message: str,
) -> str:
    """Normalize and validate an incoming chat message."""

    cleaned = str(
        message or ""
    ).strip()

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    )

    if not cleaned:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Enter a message before sending."
            ),
        )

    if (
        len(cleaned)
        > MAX_MESSAGE_LENGTH
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                f"Messages cannot exceed "
                f"{MAX_MESSAGE_LENGTH} characters."
            ),
        )

    return cleaned


def normalize_language(
    language: str | None,
) -> str:
    """Normalize and validate a requested language code.

    Previously, unsupported languages defaulted to English, limiting multilingual support.
    This change returns the normalized language code regardless of whether it is listed
    in SUPPORTED_LANGUAGES, allowing the AI component to receive the desired language
    identifier.
    """
    normalized = str(
        language or "en"
    ).strip().lower()

    normalized = (
        normalized
        .replace("_", "-")
        .split("-")[0]
    )

    # Return the normalized language code even if not in SUPPORTED_LANGUAGES.
    return normalized


def normalize_model(
    model: str | None,
) -> str:
    """Validate an assistant model identifier against the allowlist."""

    normalized = str(
        model or DEFAULT_AI_MODEL
    ).strip().lower()

    if normalized not in AVAILABLE_AI_MODELS:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "The selected AI model is not available."
            ),
        )

    return normalized


# ============================================================
# Safety checks
# ============================================================

def contains_sensitive_information(
    message: str,
) -> bool:
    """
    Detect obvious sensitive information.

    This is a warning layer and not a complete
    data-loss-prevention system.
    """

    patterns = (
        (
            r"\b(?:password|passcode|pin)"
            r"\s*(?:is|:)\s*\S+"
        ),
        r"\b\d{13,19}\b",
        r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b",
        (
            r"\b(?:cvv|cvc)"
            r"\s*(?:is|:)?\s*\d{3,4}\b"
        ),
    )

    return any(
        re.search(
            pattern,
            message,
            re.IGNORECASE,
        )
        for pattern in patterns
    )


def detect_emergency(
    message: str,
) -> bool:
    """Detect possible safety or property emergencies."""

    emergency_terms = {
        "fire",
        "smoke",
        "gas leak",
        "carbon monoxide",
        "electrical fire",
        "flooding",
        "burst pipe",
        "break in",
        "break-in",
        "immediate danger",
        "medical emergency",
        "not breathing",
        "feuer",
        "gasleck",
        "überschwemmung",
        "unmittelbare gefahr",
    }

    lowered = message.lower()

    return any(
        term in lowered
        for term in emergency_terms
    )


def detect_housing_decision_request(
    message: str,
) -> bool:
    """
    Detect attempts to make the AI perform a final
    tenant-selection decision.
    """

    decision_phrases = (
        "approve this tenant",
        "reject this tenant",
        "choose the best tenant",
        "score this tenant",
        "rank the applicants",
        "should i reject",
        "should i approve",
        "automatically reject",
        "automatically approve",
        "best applicant",
        "worst applicant",
    )

    lowered = message.lower()

    return any(
        phrase in lowered
        for phrase in decision_phrases
    )


# ============================================================
# Local AI responses
# ============================================================

def translated_response(
    language: str,
    response_key: str,
) -> str:
    """
    Return an assistant response in the requested language.

    Languages without a translated response currently fall back
    to English.
    """

    translations = {
        "en": {
            "welcome": (
                "Hello! I can help you search for apartments, "
                "understand property details, prepare a viewing "
                "request, or navigate the tenant and landlord portals."
            ),
            "search": (
                "I can help with your apartment search. Tell me your "
                "preferred city, maximum monthly rent, number of "
                "bedrooms, and any accessibility requirements."
            ),
            "guided": (
                "Open the guided search to answer one question at a "
                "time. It supports keyboard navigation, voice input, "
                "and spoken instructions."
            ),
            "tenant": (
                "The tenant portal contains your lease information, "
                "rent status, maintenance requests, complaints, "
                "documents, messages, and appointments."
            ),
            "landlord": (
                "The landlord portal lets authorized users manage "
                "properties, units, tenants, applications, viewing "
                "appointments, maintenance costs, and reports."
            ),
            "maintenance": (
                "Describe the maintenance issue, its location, when "
                "it started, and whether it creates an immediate "
                "safety risk. Do not include passwords or payment "
                "card information."
            ),
            "rent": (
                "You can review rent amounts, payment due dates, and "
                "payment status in the Payments section of your "
                "tenant dashboard."
            ),
            "lease": (
                "Open Lease Details in the tenant portal to review "
                "lease dates, rent, deposit, and renewal information."
            ),
            "appointment": (
                "You can request a viewing from a property listing. "
                "An appointment reminder can be sent 30 minutes "
                "before the scheduled time."
            ),
            "privacy": (
                "Please do not send passwords, card numbers, banking "
                "login details, identity-document numbers, or other "
                "unnecessary sensitive information in the AI chat."
            ),
            "decision": (
                "I cannot make a final housing decision or rank "
                "applicants using protected or sensitive personal "
                "characteristics. An authorized person must review "
                "applications using lawful and documented criteria."
            ),
            "unknown": (
                "I can help with apartment searches, applications, "
                "appointments, payments, leases, maintenance requests, "
                "complaints, documents, accessibility, and privacy. "
                "Please describe what you need."
            ),
        },

        "de": {
            "welcome": (
                "Hallo! Ich kann Ihnen bei der Wohnungssuche, bei "
                "Immobilieninformationen, Besichtigungsterminen sowie "
                "im Mieter- oder Vermieterportal helfen."
            ),
            "search": (
                "Ich helfe Ihnen bei der Wohnungssuche. Nennen Sie "
                "bitte die gewünschte Stadt, die maximale Monatsmiete, "
                "die Anzahl der Schlafzimmer und Anforderungen an die "
                "Barrierefreiheit."
            ),
            "guided": (
                "Öffnen Sie die geführte Suche, um jeweils eine Frage "
                "zu beantworten. Sie unterstützt Tastaturbedienung, "
                "Spracheingabe und gesprochene Anweisungen."
            ),
            "tenant": (
                "Im Mieterportal finden Sie Mietvertrag, Mietstatus, "
                "Wartungsanfragen, Beschwerden, Dokumente, Nachrichten "
                "und Termine."
            ),
            "landlord": (
                "Im Vermieterportal können berechtigte Personen "
                "Immobilien, Wohneinheiten, Mieter, Bewerbungen, "
                "Besichtigungen, Wartungskosten und Berichte verwalten."
            ),
            "maintenance": (
                "Beschreiben Sie das Problem, den Ort, den Beginn und "
                "ob eine unmittelbare Gefahr besteht. Geben Sie keine "
                "Passwörter oder Zahlungskartendaten ein."
            ),
            "rent": (
                "Mietbeträge, Fälligkeiten und Zahlungsstatus finden "
                "Sie im Bereich Zahlungen Ihres Mieterportals."
            ),
            "lease": (
                "Unter Mietvertragsdetails finden Sie Laufzeit, Miete, "
                "Kaution und Verlängerungsinformationen."
            ),
            "appointment": (
                "Über ein Wohnungsangebot können Sie einen "
                "Besichtigungstermin anfragen. Eine Erinnerung kann "
                "30 Minuten vorher gesendet werden."
            ),
            "privacy": (
                "Bitte senden Sie im KI-Chat keine Passwörter, "
                "Kartennummern, Online-Banking-Daten oder unnötige "
                "sensible persönliche Informationen."
            ),
            "decision": (
                "Ich kann keine endgültige Wohnungsentscheidung "
                "treffen oder Bewerber anhand geschützter persönlicher "
                "Merkmale bewerten. Eine berechtigte Person muss die "
                "Bewerbung nach rechtmäßigen Kriterien prüfen."
            ),
            "unknown": (
                "Ich kann bei Wohnungssuche, Bewerbungen, Terminen, "
                "Zahlungen, Mietverträgen, Reparaturen, Beschwerden "
                "und Dokumenten helfen."
            ),
        },
    }

    selected_language = (
        translations.get(
            language,
            translations["en"],
        )
    )

    return selected_language.get(
        response_key,
        translations["en"]["unknown"],
    )


def generate_local_response(
    message: str,
    language: str,
) -> tuple[str, bool]:
    """
    Generate a safe temporary response.

    Replace this function later with the trained AI service.
    """

    lowered = message.lower()

    if detect_housing_decision_request(
        message
    ):
        return (
            translated_response(
                language,
                "decision",
            ),
            True,
        )

    if contains_sensitive_information(
        message
    ):
        return (
            translated_response(
                language,
                "privacy",
            ),
            True,
        )

    greeting_terms = (
        "hello",
        "hi",
        "hey",
        "hallo",
        "good morning",
        "good evening",
        "guten morgen",
        "guten abend",
    )

    if any(
        lowered == term
        or lowered.startswith(
            f"{term} "
        )
        for term in greeting_terms
    ):
        return (
            translated_response(
                language,
                "welcome",
            ),
            False,
        )

    categories = (
        (
            "search",
            (
                "find apartment",
                "find an apartment",
                "find a home",
                "apartment search",
                "search apartment",
                "wohnung suchen",
                "rent apartment",
                "listing",
            ),
        ),
        (
            "guided",
            (
                "guided search",
                "guide me",
                "help me search",
                "geführte suche",
                "voice search",
            ),
        ),
        (
            "tenant",
            (
                "tenant portal",
                "my lease",
                "my rent",
                "tenant dashboard",
                "mieterportal",
            ),
        ),
        (
            "landlord",
            (
                "landlord",
                "property manager",
                "manage property",
                "vermieter",
            ),
        ),
        (
            "maintenance",
            (
                "maintenance",
                "repair",
                "broken",
                "complaint",
                "damage",
                "wartung",
                "reparatur",
            ),
        ),
        (
            "rent",
            (
                "rent",
                "payment",
                "invoice",
                "miete",
                "zahlung",
            ),
        ),
        (
            "lease",
            (
                "lease",
                "renewal",
                "contract",
                "mietvertrag",
                "verlängerung",
            ),
        ),
        (
            "appointment",
            (
                "appointment",
                "viewing",
                "inspection",
                "termin",
                "besichtigung",
            ),
        ),
        (
            "privacy",
            (
                "privacy",
                "personal data",
                "data protection",
                "datenschutz",
                "credit card",
                "password",
            ),
        ),
    )

    for response_key, terms in categories:
        if any(
            term in lowered
            for term in terms
        ):
            return (
                translated_response(
                    language,
                    response_key,
                ),
                False,
            )

    return (
        translated_response(
            language,
            "unknown",
        ),
        False,
    )


# ============================================================
# Conversation storage
# ============================================================

def safe_conversation_content(
    message: str,
) -> str:
    """Prevent sensitive messages from being stored in the session."""

    if contains_sensitive_information(
        message
    ):
        return (
            "[Sensitive information removed]"
        )

    return message


def save_conversation_message(
    request: Request,
    *,
    role: str,
    content: str,
    language: str,
) -> None:
    """Store a limited conversation history in the signed session."""

    session = get_session(request)

    conversation = session.get(
        "ai_conversation",
        [],
    )

    if not isinstance(
        conversation,
        list,
    ):
        conversation = []

    conversation.append(
        {
            "role": role,
            "content": (
                safe_conversation_content(
                    content
                )
            ),
            "language": language,
            "timestamp": utc_now_iso(),
        }
    )

    session["ai_conversation"] = (
        conversation[
            -MAX_CONVERSATION_MESSAGES:
        ]
    )


# ============================================================
# Page routes
# ============================================================

@router.get(
    "/ai-assistant",
    response_class=HTMLResponse,
    name="ai_assistant",
)
def ai_assistant(
    request: Request,
):
    """Display the authenticated AI assistant page."""

    if not is_authenticated(request):
        login_url = request.url_for(
            "login"
        )

        return RedirectResponse(
            url=(
                f"{login_url}"
                "?next=/ai-assistant"
            ),
            status_code=(
                status.HTTP_303_SEE_OTHER
            ),
        )

    session = get_session(request)

    conversation_id = session.get(
        "ai_conversation_id"
    )

    if not conversation_id:
        conversation_id = str(
            uuid4()
        )

        session[
            "ai_conversation_id"
        ] = conversation_id

    csrf_token = ensure_csrf_token(
        request
    )

    conversation = session.get(
        "ai_conversation",
        [],
    )

    selected_model = session.get(
        "ai_selected_model",
        DEFAULT_AI_MODEL,
    )

    if selected_model not in AVAILABLE_AI_MODELS:
        selected_model = DEFAULT_AI_MODEL
        session["ai_selected_model"] = selected_model

    return templates.TemplateResponse(
        request=request,
        name="ai/assistant.html",
        context={
            "request": request,
            "page_title": (
                "AI Assistant"
            ),
            "page_description": (
                "Multilingual Smart Property AI assistant."
            ),
            "current_user": (
                get_current_user(
                    request
                )
            ),
            "is_authenticated": True,
            "conversation_id": (
                conversation_id
            ),
            "conversation": (
                conversation
            ),
            "csrf_token": (
                csrf_token
            ),
            "language": (
                session.get(
                    "language",
                    "en",
                )
            ),
            "supported_languages": (
                SUPPORTED_LANGUAGES
            ),
            "available_models": list(
                AVAILABLE_AI_MODELS.values()
            ),
            "selected_model": selected_model,
            "ai_disclosure": (
                "AI responses may contain errors. "
                "Housing decisions must be reviewed "
                "by an authorized person."
            ),
        },
    )


@router.get(
    "/assistant",
    name="ai_assistant_alias",
)
def ai_assistant_alias():
    """Redirect the old assistant URL to the canonical page."""

    return RedirectResponse(
        url="/ai-assistant",
        status_code=(
            status.HTTP_303_SEE_OTHER
        ),
    )


# ============================================================
# Chat API
# ============================================================

@router.post(
    "/api/ai/chat",
    response_model=AIChatResponse,
    name="ai_chat",
)
def ai_chat(
    payload: AIChatRequest,
    request: Request,
) -> AIChatResponse:
    """Process one authenticated AI assistant message."""

    if not is_authenticated(request):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Sign in to use the AI assistant."
            ),
        )

    user_id = get_current_user_id(
        request
    )

    logger.info(
        "AI chat request received from user %s",
        user_id,
    )

    verify_csrf_token(
        request,
        request.headers.get(
            "X-CSRF-Token"
        ),
    )

    message = sanitize_message(
        payload.message
    )

    language = normalize_language(
        payload.language
    )

    selected_model = normalize_model(
        payload.model
    )

    session = get_session(request)

    session[
        "ai_selected_model"
    ] = selected_model

    conversation_id = (
        payload.conversation_id
        or session.get(
            "ai_conversation_id"
        )
        or str(uuid4())
    )

    session[
        "ai_conversation_id"
    ] = conversation_id

    emergency = detect_emergency(
        message
    )

    if emergency:
        response_text = (
            "This may be an emergency. Leave the dangerous area "
            "if you can do so safely and contact the appropriate "
            "local emergency service immediately. In Germany, call "
            "112 for fire or medical emergencies and 110 for police. "
            "Do not wait for an AI or maintenance response."
        )

        human_review_required = True

    else:
        (
            response_text,
            human_review_required,
        ) = generate_local_response(
            message,
            language,
        )

    # Apply professional tone guardrail before storing response
    response_text = apply_professional_guardrails(response_text)

    save_conversation_message(
        request,
        role="assistant",
        content=response_text,
        language=language,
    )

    logger.info(
        "AI assistant request handled: "
        "user=%s conversation=%s model=%s",
        user_id,
        conversation_id,
        selected_model,
    )

    return AIChatResponse(
        success=True,
        reply=response_text,
        conversation_id=conversation_id,
        language=language,
        model=selected_model,
        human_review_required=(
            human_review_required
        ),
        emergency=emergency,
        disclaimer=(
            "AI-generated information may be incomplete or incorrect. "
            "An authorized person must make final housing decisions."
        ),
    )


# ============================================================
# Clear conversation API
# ============================================================

@router.post(
    "/api/ai/clear",
    name="clear_ai_conversation",
)
def clear_ai_conversation(
    request: Request,
) -> JSONResponse:
    """Clear the current user's AI conversation."""

    if not is_authenticated(request):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Sign in to manage an AI conversation."
            ),
        )

    verify_csrf_token(
        request,
        request.headers.get(
            "X-CSRF-Token"
        ),
    )

    session = get_session(request)

    session.pop(
        "ai_conversation",
        None,
    )

    conversation_id = str(
        uuid4()
    )

    session[
        "ai_conversation_id"
    ] = conversation_id

    return JSONResponse(
        content={
            "success": True,
            "message": (
                "Conversation cleared."
            ),
            "conversation_id": (
                conversation_id
            ),
        }
    )


# ============================================================
# Status API
# ============================================================

@router.get(
    "/api/ai/status",
    name="ai_status",
)
def ai_status() -> dict[str, Any]:
    """Return the current assistant status."""

    return {
        "success": True,
        "status": "available",
        "mode": (
            "local_navigation_assistant"
        ),
        "trained_model_connected": False,
        "default_model": DEFAULT_AI_MODEL,
        "available_models": list(
            AVAILABLE_AI_MODELS.values()
        ),
        "supported_languages": list(
            SUPPORTED_LANGUAGES.keys()
        ),
        "multilingual": True,
        "voice_input": True,
        "speech_output": True,
        "human_review_required_for_housing_decisions": True,
        "timestamp": utc_now_iso(),
    }
