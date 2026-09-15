"""
Smart Property AI assistant routes.

File:
    routes/ai_routes.py

Routes:
    GET  /ai-assistant
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

from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field


logger = logging.getLogger("smart_property_ai")

router = APIRouter(
    tags=["AI Assistant"],
)

templates = Jinja2Templates(directory="templates")

MAX_CONVERSATION_MESSAGES = 20
MAX_MESSAGE_LENGTH = 3000


class AIChatRequest(BaseModel):
    """Validated request sent by the AI chat interface."""

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

    page_context: str | None = Field(
        default=None,
        max_length=500,
    )

    consent: bool = False


class AIChatResponse(BaseModel):
    """Response returned by the AI chat API."""

    success: bool
    reply: str
    conversation_id: str
    language: str
    human_review_required: bool = False
    emergency: bool = False
    disclaimer: str | None = None


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-formatted string."""

    return datetime.now(timezone.utc).isoformat()


def get_session(request: Request) -> Any:
    """
    Return the request session.

    SessionMiddleware must be installed in app.py.
    """

    try:
        return request.session
    except (AssertionError, RuntimeError) as exc:
        logger.exception("SessionMiddleware is unavailable.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "SessionMiddleware must be configured before "
                "using the AI assistant."
            ),
        ) from exc


def get_current_user(request: Request) -> Any | None:
    """Return the authenticated user when available."""

    state_user = getattr(request.state, "user", None)

    if state_user is not None:
        return state_user

    session = get_session(request)
    session_user = session.get("user")

    return session_user


def get_current_user_id(request: Request) -> str | None:
    """Return the authenticated user's UUID string."""

    user = get_current_user(request)

    if isinstance(user, dict):
        user_id = user.get("id")

        if user_id:
            return str(user_id)

    if user is not None:
        user_id = getattr(user, "id", None)

        if user_id:
            return str(user_id)

    session = get_session(request)

    user_id = (
        session.get("user_id")
        or session.get("authenticated_user_id")
    )

    return str(user_id) if user_id else None


def is_authenticated(request: Request) -> bool:
    """Return True when the user is signed in."""

    return get_current_user_id(request) is not None


def sanitize_message(message: str) -> str:
    """Normalize and validate a user message."""

    cleaned = str(message or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a message before sending.",
        )

    if len(cleaned) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Messages cannot exceed "
                f"{MAX_MESSAGE_LENGTH} characters."
            ),
        )

    return cleaned


def normalize_language(language: str | None) -> str:
    """Normalize a requested language code."""

    supported_languages = {
        "en",
        "de",
        "fr",
        "es",
        "it",
        "pt",
        "nl",
        "pl",
        "tr",
        "ar",
        "fa",
        "ur",
        "he",
        "hi",
        "zh",
        "ja",
        "ko",
        "ru",
        "uk",
        "sw",
    }

    normalized = str(language or "en").strip().lower()
    normalized = normalized.replace("_", "-").split("-")[0]

    if normalized in supported_languages:
        return normalized

    return "en"


def contains_sensitive_information(message: str) -> bool:
    """
    Detect obvious sensitive information.

    This is a basic warning layer and not a complete data-loss
    prevention system.
    """

    patterns = (
        r"\b(?:password|passcode|pin)\s*(?:is|:)\s*\S+",
        r"\b\d{13,19}\b",
        r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b",
        r"\b(?:cvv|cvc)\s*(?:is|:)?\s*\d{3,4}\b",
    )

    return any(
        re.search(pattern, message, re.IGNORECASE)
        for pattern in patterns
    )


def detect_emergency(message: str) -> bool:
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

    # token is valid, proceed
    return any(
        term in lowered
        for term in emergency_terms
    )


def detect_housing_decision_request(message: str) -> bool:
    """
    Detect attempts to make the AI perform final tenant-selection
    decisions.
    """

    lowered = message.lower()

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

    return any(
        phrase in lowered
        for phrase in decision_phrases
    )


def translated_response(
    language: str,
    response_key: str,
) -> str:
    """Return essential assistant responses in selected languages."""

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
                "I can help with apartment searches, property "
                "information, viewing appointments, rental "
                "applications, tenant services, maintenance requests, "
                "landlord tools, accessibility, and privacy. Please "
                "tell me which area you need."
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
            "privacy": (
                "Bitte senden Sie im KI-Chat keine Passwörter, "
                "Kartennummern, Online-Banking-Daten oder unnötige "
                "sensible persönliche Informationen."
            ),
            "decision": (
                "Ich kann keine endgültige Wohnungsentscheidung treffen "
                "oder Bewerber anhand geschützter persönlicher Merkmale "
                "bewerten. Eine berechtigte Person muss die Bewerbung "
                "nach rechtmäßigen Kriterien prüfen."
            ),
            "unknown": (
                "Ich kann bei Wohnungssuche, Immobilieninformationen, "
                "Besichtigungen, Bewerbungen, Mieterservices, Wartung, "
                "Vermieterfunktionen, Barrierefreiheit und Datenschutz "
                "helfen. Wobei benötigen Sie Unterstützung?"
            ),
        },
    }

    selected_language = translations.get(
        language,
        translations["en"],
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

    if detect_housing_decision_request(message):
        return (
            translated_response(language, "decision"),
            True,
        )

    if contains_sensitive_information(message):
        return (
            translated_response(language, "privacy"),
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
        lowered == term or lowered.startswith(f"{term} ")
        for term in greeting_terms
    ):
        return (
            translated_response(language, "welcome"),
            False,
        )

    search_terms = (
        "find apartment",
        "find an apartment",
        "find a home",
        "apartment search",
        "search apartment",
        "wohnung suchen",
        "rent apartment",
    )

    if any(term in lowered for term in search_terms):
        return (
            translated_response(language, "search"),
            False,
        )

    guided_terms = (
        "guided search",
        "guide me",
        "help me search",
        "geführte suche",
        "voice search",
    )

    if any(term in lowered for term in guided_terms):
        return (
            translated_response(language, "guided"),
            False,
        )

    tenant_terms = (
        "tenant portal",
        "my lease",
        "my rent",
        "tenant dashboard",
        "mieterportal",
    )

    if any(term in lowered for term in tenant_terms):
        return (
            translated_response(language, "tenant"),
            False,
        )

    landlord_terms = (
        "landlord",
        "property manager",
        "manage property",
        "vermieter",
    )

    if any(term in lowered for term in landlord_terms):
        return (
            translated_response(language, "landlord"),
            False,
        )

    maintenance_terms = (
        "maintenance",
        "repair",
        "broken",
        "complaint",
        "damage",
        "wartung",
        "reparatur",
    )

    if any(term in lowered for term in maintenance_terms):
        return (
            translated_response(language, "maintenance"),
            False,
        )

    privacy_terms = (
        "privacy",
        "personal data",
        "data protection",
        "datenschutz",
        "credit card",
        "password",
    )

    if any(term in lowered for term in privacy_terms):
        return (
            translated_response(language, "privacy"),
            False,
        )

    return (
        translated_response(language, "unknown"),
        False,
    )


def safe_conversation_content(message: str) -> str:
    """
    Avoid storing messages that appear to contain sensitive data.
    """

    if contains_sensitive_information(message):
        return "[Sensitive information removed]"

    return message


def save_conversation_message(
    request: Request,
    *,
    role: str,
    content: str,
    language: str,
) -> None:
    """Store a short conversation history in the signed session."""

    session = get_session(request)

    conversation = session.get(
        "ai_conversation",
        [],
    )

    if not isinstance(conversation, list):
        conversation = []

    conversation.append(
        {
            "role": role,
            "content": safe_conversation_content(content),
            "language": language,
            "timestamp": utc_now_iso(),
        }
    )

    session["ai_conversation"] = conversation[
        -MAX_CONVERSATION_MESSAGES:
    ]


def verify_csrf_token(
    request: Request,
    submitted_token: str | None,
) -> None:
    """
    Validate a CSRF token when one exists in the session.

    JSON chat requests can send the token through the X-CSRF-Token
    header. This protects cookie-authenticated requests.
    """

    logger.debug(f"CSRF verification: request headers: {dict(request.headers)}")
    session = get_session(request)
    expected_token = session.get("csrf_token")

    if not expected_token:
        logger.debug("CSRF token missing in session")
        return

    if not submitted_token:
        logger.debug(f"CSRF token not submitted: expected {expected_token}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing form security token.",
        )

    if not secrets.compare_digest(
        str(expected_token),
        str(submitted_token),
    ):
        logger.debug(f"CSRF token mismatch: expected {expected_token}, got {submitted_token}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid form security token.",
        )

    logger.debug("CSRF token verified successfully")
    # token is valid, proceed


@router.get("/ai-assistant", name="ai_assistant")
@router.get("/ai-assistant", name="ai_assistant")
def ai_assistant(request: Request):
    """
    Display the Smart Property AI assistant.

    Authentication is required because the assistant may connect to
    private tenant and landlord information in later development.
    """

    if not is_authenticated(request):
        login_url = request.url_for("login")

        return RedirectResponse(
            url=f"{login_url}?next=/ai-assistant",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    session = get_session(request)

    conversation_id = session.get(
        "ai_conversation_id"
    )

    if not conversation_id:
        conversation_id = str(uuid4())
        session["ai_conversation_id"] = conversation_id

    conversation = session.get(
        "ai_conversation",
        [],
    )

    csrf_token = session.get("csrf_token")

    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        session["csrf_token"] = csrf_token

    return templates.TemplateResponse(
        request=request,
        name="ai_assistant.html",
        context={
            "request": request,
            "page_title": "AI Assistant",
            "page_description": (
                "Multilingual Smart Property AI assistant."
            ),
            "current_user": get_current_user(request),
            "is_authenticated": True,
            "conversation_id": conversation_id,
            "conversation": conversation,
            "csrf_token": csrf_token,
            "ai_disclosure": (
                "AI responses may contain errors. Housing decisions "
                "must be reviewed by an authorized person."
            ),
        },
    )


@router.post(
    "/api/ai/chat",
    response_model=AIChatResponse,
    name="ai_chat",
)
def ai_chat(
    payload: AIChatRequest,
    request: Request,
) -> AIChatResponse:
    """
    Process one AI assistant message.

    Replace generate_local_response() with your trained AI service
    when the AI layer is ready.
    """

    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to use the AI assistant.",
        )
    logger.info(f"AI chat request received from user {get_current_user_id(request)}")

    verify_csrf_token(
        request,
        request.headers.get("X-CSRF-Token"),
    )

    logger.debug(f"AI chat payload: {payload}")
    message = sanitize_message(payload.message)
    language = normalize_language(payload.language)
    session = get_session(request)

    conversation_id = (
        payload.conversation_id
        or session.get("ai_conversation_id")
        or str(uuid4())
    )

    session["ai_conversation_id"] = conversation_id

    emergency = detect_emergency(message)

    if emergency:
        response_text = (
            "This may be an emergency. Leave the dangerous area if "
            "you can do so safely and contact the appropriate local "
            "emergency service immediately. In Germany, call 112 for "
            "fire or medical emergencies and 110 for police. Do not "
            "wait for an AI or maintenance response."
        )

        human_review_required = True
    else:
        response_text, human_review_required = (
            generate_local_response(
                message,
                language,
            )
        )

    # Save the sanitized conversation in the current session.
    save_conversation_message(
        request,
        role="user",
        content=message,
        language=language,
    )

    save_conversation_message(
        request,
        role="assistant",
        content=response_text,
        language=language,
    )

    logger.info(
        "AI assistant request handled: user=%s conversation=%s",
        get_current_user_id(request),
        conversation_id,
    )

    return AIChatResponse(
        success=True,
        reply=response_text,
        conversation_id=conversation_id,
        language=language,
        human_review_required=human_review_required,
        emergency=emergency,
        disclaimer=(
            "AI-generated information may be incomplete or incorrect. "
            "An authorized person must make final housing decisions."
        ),
    )


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
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to manage an AI conversation.",
        )

    verify_csrf_token(
        request,
        request.headers.get("X-CSRF-Token"),
    )

    session = get_session(request)

    session.pop("ai_conversation", None)
    session["ai_conversation_id"] = str(uuid4())

    return JSONResponse(
        content={
            "success": True,
            "message": "Conversation cleared.",
            "conversation_id": session[
                "ai_conversation_id"
            ],
        }
    )


@router.get(
    "/api/ai/status",
    name="ai_status",
)
def ai_status() -> dict[str, Any]:
    """Return the current AI assistant status."""

    return {
        "available": True,
        "mode": "local_navigation_assistant",
        "trained_model_connected": False,
        "multilingual": True,
        "voice_input": True,
        "speech_output": True,
        "human_review_required_for_housing_decisions": True,
        "timestamp": utc_now_iso(),
    }





templates = Jinja2Templates(directory="templates")


SUPPORTED_LANGUAGES = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "ar": "العربية",
    "tr": "Türkçe",
    "pl": "Polski",
    "uk": "Українська",
}


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="en", min_length=2, max_length=10)
    conversation_id: Optional[str] = Field(default=None, max_length=100)


class AIChatResponse(BaseModel):
    reply: str
    language: str
    conversation_id: Optional[str] = None
    source: Literal["local-rules"] = "local-rules"
    disclaimer: str


def _authenticated_user_id(request: Request) -> Optional[str]:
    return (
        request.session.get("user_id")
        or request.session.get("username")
        or request.session.get("user")
    )


def _normalize_language(language: str) -> str:
    language_code = language.strip().lower().split("-")[0]
    return language_code if language_code in SUPPORTED_LANGUAGES else "en"


def _assistant_reply(message: str, language: str) -> str:
    text = message.casefold()

    replies = {
        "en": {
            "greeting": "Hello! I can help with apartment searches, applications, appointments, rent, leases, maintenance, and tenant services.",
            "search": "Open Find an Apartment to search by city, rent, bedrooms, accessibility, and pet requirements.",
            "maintenance": "Open the tenant portal and select Maintenance Requests. If anyone is in immediate danger in Germany, call 112 for fire or medical emergencies or 110 for police.",
            "rent": "You can review rent amounts, due dates, and payment status from the Payments section of your tenant dashboard.",
            "lease": "Open Lease Details in the tenant portal to review dates, rent, deposit, and renewal information.",
            "appointment": "You can request a viewing from a property listing. Appointment reminders can be sent 30 minutes before the scheduled time.",
            "privacy": "Smart Property AI should collect only necessary information. You can review how information is handled on the Privacy and AI Disclosure pages.",
            "fallback": "I can help with apartment searches, applications, appointments, payments, leases, maintenance requests, complaints, and documents. Please describe what you need.",
        },
        "de": {
            "greeting": "Hallo! Ich kann bei Wohnungssuche, Bewerbungen, Terminen, Miete, Mietverträgen und Reparaturanfragen helfen.",
            "search": "Öffnen Sie „Wohnung finden“, um nach Stadt, Miete, Zimmern, Barrierefreiheit und Haustieren zu suchen.",
            "maintenance": "Öffnen Sie im Mieterportal den Bereich „Reparaturanfragen“. Bei akuter Gefahr wählen Sie in Deutschland 112 oder für die Polizei 110.",
            "rent": "Mietbeträge, Fälligkeiten und Zahlungsstatus finden Sie im Bereich „Zahlungen“ Ihres Mieterportals.",
            "lease": "Unter „Mietvertragsdetails“ finden Sie Laufzeit, Miete, Kaution und Verlängerungsinformationen.",
            "appointment": "Über ein Wohnungsangebot können Sie einen Besichtigungstermin anfragen. Eine Erinnerung kann 30 Minuten vorher gesendet werden.",
            "privacy": "Smart Property AI sollte nur notwendige Daten verarbeiten. Einzelheiten finden Sie unter Datenschutz und KI-Hinweise.",
            "fallback": "Ich kann bei Wohnungssuche, Bewerbungen, Terminen, Zahlungen, Mietverträgen, Reparaturen, Beschwerden und Dokumenten helfen.",
        },
    }

    selected = replies.get(language, replies["en"])

    if any(word in text for word in ("hello", "hi", "hey", "hallo", "guten tag")):
        return selected["greeting"]
    if any(word in text for word in ("apartment", "listing", "search", "wohnung", "suchen")):
        return selected["search"]
    if any(word in text for word in ("repair", "maintenance", "broken", "leak", "reparatur", "defekt")):
        return selected["maintenance"]
    if any(word in text for word in ("rent", "payment", "invoice", "miete", "zahlung")):
        return selected["rent"]
    if any(word in text for word in ("lease", "renewal", "contract", "mietvertrag", "verlängerung")):
        return selected["lease"]
    if any(word in text for word in ("appointment", "viewing", "inspection", "termin", "besichtigung")):
        return selected["appointment"]
    if any(word in text for word in ("privacy", "data", "ai", "datenschutz", "daten", "ki")):
        return selected["privacy"]

    return selected["fallback"]



def ai_assistant_page(request: Request):
    if not _authenticated_user_id(request):
        return RedirectResponse(
            url="/login?next=/ai-assistant",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request=request,
        name="ai/assistant.html",
        context={
            "request": request,
            "current_user": request.session.get("user"),
            "supported_languages": SUPPORTED_LANGUAGES,
            "selected_language": request.session.get("language", "en"),
        },
    )


@router.get("/assistant", name="ai_assistant_alias")
def ai_assistant_alias():
    return RedirectResponse(
        url="/ai-assistant",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/api/ai/chat",
    name="ai_chat",
    response_model=AIChatResponse,
)
def ai_chat(payload: AIChatRequest, request: Request):
    if not _authenticated_user_id(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please log in to use the AI assistant.",
        )

    language = _normalize_language(payload.language)
    message = payload.message.strip()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A message is required.",
        )

    return AIChatResponse(
        reply=_assistant_reply(message, language),
        language=language,
        conversation_id=payload.conversation_id,
        disclaimer=(
            "AI-generated information may contain mistakes. Verify important "
            "legal, financial, safety, and tenancy information."
        ),
    )


@router.get("/api/ai/status", name="ai_status")
def ai_status():
    return {
        "status": "available",
        "engine": "local-rules",
        "trained_model_connected": False,
        "supported_languages": list(SUPPORTED_LANGUAGES.keys()),
    }
