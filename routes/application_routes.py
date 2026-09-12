"""Rental application and viewing appointment submission routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database.database import get_db
from services.application_service import (
    ApplicationServiceError,
    ApplicationValidationError,
    UnitUnavailableError,
    create_application,
    validate_csrf,
)
from services.appointment_service import (
    AppointmentConflictError,
    AppointmentServiceError,
    AppointmentValidationError,
    create_appointment,
)

logger = logging.getLogger("smart_property_ai")

router = APIRouter(
    prefix="/listings",
    tags=["Applications and appointments"],
)


def form_boolean(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value

    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def current_user_id(request: Request) -> int | None:
    user = getattr(request.state, "user", None)

    if user is not None:
        if isinstance(user, dict):
            return user.get("id")

        return getattr(user, "id", None)

    try:
        value = request.session.get("user_id")
    except (AssertionError, RuntimeError):
        return None

    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def session_value(
    request: Request,
    key: str,
    default: Any = None,
) -> Any:
    try:
        return request.session.get(key, default)
    except (AssertionError, RuntimeError):
        return default


def set_session_value(
    request: Request,
    key: str,
    value: Any,
) -> None:
    try:
        request.session[key] = value
    except (AssertionError, RuntimeError):
        logger.warning(
            "SessionMiddleware is unavailable; could not save %s.",
            key,
        )


@router.post(
    "/{property_id}/apply",
    name="listing_application_submit",
)
def submit_rental_application(
    property_id: int,
    request: Request,
    unit_id: int = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    current_address: str = Form(...),
    current_city: str = Form(...),
    postal_code: str = Form(...),
    adult_occupants: int = Form(...),
    child_occupants: int = Form(0),
    desired_move_in_date: str = Form(...),
    lease_duration_months: int | None = Form(None),
    has_pets: str | None = Form(None),
    pet_details: str | None = Form(None),
    employment_status: str = Form(...),
    employer_name: str | None = Form(None),
    monthly_income: str = Form(...),
    employment_length: str | None = Form(None),
    message: str | None = Form(None),
    information_confirmed: str | None = Form(None),
    privacy_consent: str | None = Form(None),
    landlord_contact_consent: str | None = Form(None),
    ai_assistance_consent: str | None = Form(None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        validate_csrf(
            csrf_token,
            session_value(request, "csrf_token"),
        )

        application = create_application(
            db,
            property_id=property_id,
            unit_id=unit_id,
            user_id=current_user_id(request),
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            current_address=current_address,
            current_city=current_city,
            postal_code=postal_code,
            adult_occupants=adult_occupants,
            child_occupants=child_occupants,
            desired_move_in_date=desired_move_in_date,
            lease_duration_months=lease_duration_months,
            has_pets=form_boolean(has_pets),
            pet_details=pet_details,
            employment_status=employment_status,
            employer_name=employer_name,
            monthly_income=monthly_income,
            employment_length=employment_length,
            message=message,
            information_confirmed=form_boolean(
                information_confirmed
            ),
            privacy_consent=form_boolean(privacy_consent),
            landlord_contact_consent=form_boolean(
                landlord_contact_consent
            ),
            ai_assistance_consent=form_boolean(
                ai_assistance_consent
            ),
        )

        set_session_value(
            request,
            "success_message",
            (
                "Your rental application was submitted successfully. "
                f"Reference number: {application.id}."
            ),
        )

        return RedirectResponse(
            url=f"/listings/{property_id}",
            status_code=303,
        )

    except (
        ApplicationValidationError,
        UnitUnavailableError,
    ) as exc:
        set_session_value(
            request,
            "error_message",
            str(exc),
        )

        return RedirectResponse(
            url=(
                f"/listings/{property_id}/apply"
                f"?unit_id={unit_id}"
            ),
            status_code=303,
        )

    except ApplicationServiceError as exc:
        logger.exception(
            "Rental application failed: %s",
            exc,
        )

        set_session_value(
            request,
            "error_message",
            "The application could not be submitted.",
        )

        return RedirectResponse(
            url=f"/listings/{property_id}/apply",
            status_code=303,
        )

    except Exception as exc:
        logger.exception(
            "Unexpected rental application error: %s",
            exc,
        )

        set_session_value(
            request,
            "error_message",
            "An unexpected error occurred. Please try again.",
        )

        return RedirectResponse(
            url=f"/listings/{property_id}/apply",
            status_code=303,
        )


@router.post(
    "/{property_id}/appointment",
    name="listing_appointment_submit",
)
def submit_viewing_appointment(
    property_id: int,
    request: Request,
    unit_id: int = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    preferred_language: str = Form("en"),
    preferred_date: str = Form(...),
    preferred_time: str = Form(...),
    alternative_date: str | None = Form(None),
    alternative_time: str | None = Form(None),
    viewing_type: str = Form(...),
    needs_accommodation: str | None = Form(None),
    accommodation_details: str | None = Form(None),
    message: str | None = Form(None),
    reminder_email: str | None = Form(None),
    reminder_sms: str | None = Form(None),
    reminder_whatsapp: str | None = Form(None),
    reminder_phone: str | None = Form(None),
    contact_consent: str | None = Form(None),
    reminder_consent: str | None = Form(None),
    privacy_consent: str | None = Form(None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        validate_csrf(
            csrf_token,
            session_value(request, "csrf_token"),
        )

        timezone_name = session_value(
            request,
            "timezone",
            "UTC",
        )

        appointment = create_appointment(
            db,
            property_id=property_id,
            unit_id=unit_id,
            requester_user_id=current_user_id(request),
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            preferred_language=preferred_language,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            alternative_date=alternative_date,
            alternative_time=alternative_time,
            viewing_type=viewing_type,
            needs_accommodation=form_boolean(
                needs_accommodation
            ),
            accommodation_details=accommodation_details,
            message=message,
            reminder_email=form_boolean(reminder_email),
            reminder_sms=form_boolean(reminder_sms),
            reminder_whatsapp=form_boolean(
                reminder_whatsapp
            ),
            reminder_phone=form_boolean(reminder_phone),
            contact_consent=form_boolean(contact_consent),
            reminder_consent=form_boolean(reminder_consent),
            privacy_consent=form_boolean(privacy_consent),
            timezone_name=timezone_name,
        )

        set_session_value(
            request,
            "success_message",
            (
                "Your viewing request was submitted successfully. "
                f"Reference number: {appointment.id}. "
                "Wait for confirmation before visiting the property."
            ),
        )

        return RedirectResponse(
            url=f"/listings/{property_id}",
            status_code=303,
        )

    except (
        AppointmentValidationError,
        AppointmentConflictError,
    ) as exc:
        set_session_value(
            request,
            "error_message",
            str(exc),
        )

        return RedirectResponse(
            url=(
                f"/listings/{property_id}/appointment"
                f"?unit_id={unit_id}"
            ),
            status_code=303,
        )

    except AppointmentServiceError as exc:
        logger.exception(
            "Viewing appointment request failed: %s",
            exc,
        )

        set_session_value(
            request,
            "error_message",
            "The viewing request could not be submitted.",
        )

        return RedirectResponse(
            url=f"/listings/{property_id}/appointment",
            status_code=303,
        )

    except Exception as exc:
        logger.exception(
            "Unexpected appointment error: %s",
            exc,
        )

        set_session_value(
            request,
            "error_message",
            "An unexpected error occurred. Please try again.",
        )

        return RedirectResponse(
            url=f"/listings/{property_id}/appointment",
            status_code=303,
        )