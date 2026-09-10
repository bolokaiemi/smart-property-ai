"""
Smart Property AI
Public and legal page routes.

File:
    routes/main_routes.py
"""

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    Form,
    Request,
    status,
)
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


router = APIRouter()

templates = Jinja2Templates(directory="templates")


# Languages currently displayed in base.html.
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

DEFAULT_LANGUAGE = "en"


def get_current_year() -> int:
    """Return the current UTC year."""

    return datetime.now(timezone.utc).year


def get_current_language(request: Request) -> str:
    """
    Return the language stored in the user's session.

    Unsupported values fall back to English.
    """

    language = request.session.get(
        "language",
        DEFAULT_LANGUAGE,
    )

    if language not in SUPPORTED_LANGUAGES:
        return DEFAULT_LANGUAGE

    return language


def build_template_context(
    request: Request,
    **extra_context,
) -> dict:
    """
    Build the common context supplied to all Jinja templates.
    """

    context = {
        "request": request,
        "current_year": get_current_year(),
        "current_language": get_current_language(request),
        "supported_languages": SUPPORTED_LANGUAGES,
    }

    context.update(extra_context)

    return context


def safe_local_redirect_url(
    redirect_to: Optional[str],
) -> str:
    """
    Accept only local redirect paths.

    This prevents users from being redirected to an external
    malicious website through the language-selection route.
    """

    if not redirect_to:
        return "/"

    parsed_url = urlparse(redirect_to)

    if parsed_url.scheme or parsed_url.netloc:
        return "/"

    if not redirect_to.startswith("/"):
        return "/"

    if redirect_to.startswith("//"):
        return "/"

    return redirect_to


# --------------------------------------------------------------------------
# Homepage
# --------------------------------------------------------------------------

@router.get(
    "/",
    name="home",
)
async def home(request: Request):
    """
    Render the public Smart Property AI homepage.
    """

    context = build_template_context(
        request=request,
    )

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=context,
        status_code=status.HTTP_200_OK,
    )


# --------------------------------------------------------------------------
# Contact page
# --------------------------------------------------------------------------

@router.get(
    "/contact",
    name="contact_page",
)
async def contact_page(request: Request):
    """
    Display the public contact form.
    """

    context = build_template_context(
        request=request,
    )

    return templates.TemplateResponse(
        request=request,
        name="contact.html",
        context=context,
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/contact",
    name="submit_contact",
)
async def submit_contact(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
):
    """
    Validate and process a contact-form submission.

    Replace the development placeholder with your email service
    or database service when it is ready.
    """

    cleaned_name = name.strip()
    cleaned_email = email.strip().lower()
    cleaned_subject = subject.strip()
    cleaned_message = message.strip()

    errors = []

    if len(cleaned_name) < 2:
        errors.append(
            "Please enter your full name."
        )

    if (
        "@" not in cleaned_email
        or "." not in cleaned_email.rsplit("@", 1)[-1]
    ):
        errors.append(
            "Please enter a valid email address."
        )

    if len(cleaned_subject) < 3:
        errors.append(
            "Please enter a subject."
        )

    if len(cleaned_message) < 10:
        errors.append(
            "Your message must contain at least 10 characters."
        )

    if len(cleaned_message) > 5000:
        errors.append(
            "Your message must not exceed 5,000 characters."
        )

    form_data = {
        "name": cleaned_name,
        "email": cleaned_email,
        "subject": cleaned_subject,
        "message": cleaned_message,
    }

    if errors:
        context = build_template_context(
            request=request,
            errors=errors,
            form_data=form_data,
        )

        return templates.TemplateResponse(
            request=request,
            name="contact.html",
            context=context,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # Add the contact message to the database or send it through
    # services/notification_service.py here.
    #
    # Example:
    #
    # await notification_service.send_contact_message(
    #     name=cleaned_name,
    #     email=cleaned_email,
    #     subject=cleaned_subject,
    #     message=cleaned_message,
    # )

    context = build_template_context(
        request=request,
        success=(
            "Thank you. Your message has been received. "
            "We will respond as soon as possible."
        ),
        form_data={},
    )

    return templates.TemplateResponse(
        request=request,
        name="contact.html",
        context=context,
        status_code=status.HTTP_200_OK,
    )


# --------------------------------------------------------------------------
# Language selection
# --------------------------------------------------------------------------

@router.post(
    "/language",
    name="set_language",
)
async def set_language(
    request: Request,
    language: str = Form(...),
    redirect_to: Optional[str] = Form(default="/"),
):
    """
    Store the selected interface language in the session.

    The frontend language selector can submit a form or send a
    FormData POST request to this endpoint.
    """

    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    request.session["language"] = language

    safe_redirect = safe_local_redirect_url(
        redirect_to
    )

    return RedirectResponse(
        url=safe_redirect,
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/api/language",
    name="set_language_api",
)
async def set_language_api(
    request: Request,
):
    """
    Store the selected language when JavaScript sends JSON.

    Expected JSON:
        {
            "language": "de"
        }
    """

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": "The request must contain valid JSON.",
            },
        )

    language = str(
        payload.get("language", "")
    ).strip().lower()

    if language not in SUPPORTED_LANGUAGES:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": "The selected language is not supported.",
                "supported_languages": SUPPORTED_LANGUAGES,
            },
        )

    request.session["language"] = language

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "language": language,
            "language_name": SUPPORTED_LANGUAGES[language],
        },
    )


# --------------------------------------------------------------------------
# German legal pages
# --------------------------------------------------------------------------

@router.get(
    "/impressum",
    name="impressum_page",
)
async def impressum_page(request: Request):
    """
    Display the German Impressum.
    """

    context = build_template_context(
        request=request,
    )

    return templates.TemplateResponse(
        request=request,
        name="legal/impressum.html",
        context=context,
        status_code=status.HTTP_200_OK,
    )


@router.get(
    "/datenschutz",
    name="datenschutz_page",
)
async def datenschutz_page(request: Request):
    """
    Display the German privacy statement.
    """

    context = build_template_context(
        request=request,
    )

    return templates.TemplateResponse(
        request=request,
        name="legal/datenschutz.html",
        context=context,
        status_code=status.HTTP_200_OK,
    )


# --------------------------------------------------------------------------
# Additional legal and information pages
# --------------------------------------------------------------------------

@router.get(
    "/privacy",
    name="privacy_page",
)
async def privacy_page(request: Request):
    """
    Display the English privacy policy.
    """

    context = build_template_context(
        request=request,
    )

    return templates.TemplateResponse(
        request=request,
        name="legal/privacy.html",
        context=context,
        status_code=status.HTTP_200_OK,
    )


@router.get(
    "/terms",
    name="terms_page",
)
async def terms_page(request: Request):
    """
    Display the terms of use.
    """

    context = build_template_context(
        request=request,
    )

    return templates.TemplateResponse(
        request=request,
        name="legal/terms.html",
        context=context,
        status_code=status.HTTP_200_OK,
    )


@router.get(
    "/ai-information",
    name="ai_disclosure_page",
)
async def ai_disclosure_page(request: Request):
    """
    Explain how Smart Property AI is used and its limitations.
    """

    context = build_template_context(
        request=request,
    )

    return templates.TemplateResponse(
        request=request,
        name="legal/ai_disclosure.html",
        context=context,
        status_code=status.HTTP_200_OK,
    )


# --------------------------------------------------------------------------
# Platform information pages
# --------------------------------------------------------------------------

@router.get(
    "/about",
    name="about_page",
)
async def about_page(request: Request):
    """
    Display information about Smart Property AI.
    """

    context = build_template_context(
        request=request,
    )

    return templates.TemplateResponse(
        request=request,
        name="about.html",
        context=context,
        status_code=status.HTTP_200_OK,
    )


@router.get(
    "/accessibility",
    name="accessibility_page",
)
async def accessibility_page(request: Request):
    """
    Display the platform accessibility statement.
    """

    context = build_template_context(
        request=request,
    )

    return templates.TemplateResponse(
        request=request,
        name="legal/accessibility.html",
        context=context,
        status_code=status.HTTP_200_OK,
    )


# --------------------------------------------------------------------------
# Application health check
# --------------------------------------------------------------------------

@router.get(
    "/health",
    name="health_check",
    include_in_schema=False,
)
async def health_check():
    """
    Return a simple application health response.

    This endpoint can be used by Render, Docker or another
    hosting platform.
    """

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "application": "Smart Property AI",
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
        },
    )