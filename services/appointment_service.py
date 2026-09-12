"""Property-viewing appointment business logic."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from database.models import Property, Unit, ViewingAppointment


class AppointmentServiceError(Exception):
    """Base appointment error."""


class AppointmentValidationError(AppointmentServiceError):
    """Raised when appointment information is invalid."""


class AppointmentNotFoundError(AppointmentServiceError):
    """Raised when an appointment cannot be found."""


class AppointmentConflictError(AppointmentServiceError):
    """Raised when an appointment time is unavailable."""


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)

ALLOWED_VIEWING_TYPES = {
    "in_person",
    "video_call",
    "recorded_tour",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clean_text(
    value: Any,
    *,
    maximum_length: int | None = None,
    required: bool = False,
    field_name: str = "Field",
) -> str | None:
    cleaned = str(value or "").strip()

    if required and not cleaned:
        raise AppointmentValidationError(
            f"{field_name} is required."
        )

    if maximum_length and len(cleaned) > maximum_length:
        raise AppointmentValidationError(
            f"{field_name} cannot exceed "
            f"{maximum_length} characters."
        )

    return cleaned or None


def clean_email(value: Any) -> str:
    email = clean_text(
        value,
        maximum_length=254,
        required=True,
        field_name="Email address",
    ).lower()

    if not EMAIL_PATTERN.fullmatch(email):
        raise AppointmentValidationError(
            "Enter a valid email address."
        )

    return email


def clean_phone(value: Any) -> str:
    phone = clean_text(
        value,
        maximum_length=30,
        required=True,
        field_name="Phone number",
    )

    allowed = set("0123456789+()- .")

    if any(character not in allowed for character in phone):
        raise AppointmentValidationError(
            "Enter a valid phone number."
        )

    digit_count = sum(
        character.isdigit()
        for character in phone
    )

    if digit_count < 7:
        raise AppointmentValidationError(
            "Phone number is too short."
        )

    return phone


def parse_date(value: Any, field_name: str) -> date:
    if isinstance(value, date):
        parsed = value
    else:
        try:
            parsed = date.fromisoformat(str(value))
        except (TypeError, ValueError) as exc:
            raise AppointmentValidationError(
                f"{field_name} must be a valid date."
            ) from exc

    if parsed < date.today():
        raise AppointmentValidationError(
            f"{field_name} cannot be in the past."
        )

    return parsed


def parse_time(value: Any, field_name: str) -> time:
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)

    try:
        parsed = time.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise AppointmentValidationError(
            f"{field_name} must be a valid time."
        ) from exc

    return parsed.replace(second=0, microsecond=0)


def combine_datetime(
    date_value: Any,
    time_value: Any,
    *,
    timezone_name: str,
    date_field_name: str,
    time_field_name: str,
) -> datetime:
    appointment_date = parse_date(
        date_value,
        date_field_name,
    )
    appointment_time = parse_time(
        time_value,
        time_field_name,
    )

    try:
        local_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise AppointmentValidationError(
            "The property time zone is invalid."
        ) from exc

    local_datetime = datetime.combine(
        appointment_date,
        appointment_time,
        tzinfo=local_timezone,
    )

    utc_datetime = local_datetime.astimezone(timezone.utc)

    if utc_datetime <= utc_now():
        raise AppointmentValidationError(
            "Appointment time must be in the future."
        )

    return utc_datetime


def _status_value(instance: Any) -> str:
    status = getattr(instance, "status", "")
    return str(getattr(status, "value", status)).lower()


def get_available_unit(
    db: Session,
    *,
    property_id: int,
    unit_id: int,
) -> Unit:
    unit = (
        db.query(Unit)
        .filter(
            Unit.id == unit_id,
            Unit.property_id == property_id,
        )
        .first()
    )

    if unit is None:
        raise AppointmentValidationError(
            "The selected unit does not exist."
        )

    if hasattr(unit, "is_active") and not unit.is_active:
        raise AppointmentValidationError(
            "The selected unit is inactive."
        )

    if (
        hasattr(unit, "is_available")
        and not unit.is_available
    ):
        raise AppointmentValidationError(
            "The selected unit is unavailable."
        )

    unit_status = _status_value(unit)

    if unit_status and unit_status not in {
        "available",
        "vacant",
        "ready",
    }:
        raise AppointmentValidationError(
            "The selected unit is unavailable."
        )

    return unit


def get_property(
    db: Session,
    property_id: int,
) -> Property:
    property_record = (
        db.query(Property)
        .filter(Property.id == property_id)
        .first()
    )

    if property_record is None:
        raise AppointmentValidationError(
            "The requested property does not exist."
        )

    return property_record


def create_appointment(
    db: Session,
    *,
    property_id: int,
    unit_id: int,
    requester_user_id: int | None,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    preferred_language: str,
    preferred_date: date | str,
    preferred_time: time | str,
    alternative_date: date | str | None,
    alternative_time: time | str | None,
    viewing_type: str,
    needs_accommodation: bool,
    accommodation_details: str | None,
    message: str | None,
    reminder_email: bool,
    reminder_sms: bool,
    reminder_whatsapp: bool,
    reminder_phone: bool,
    contact_consent: bool,
    reminder_consent: bool,
    privacy_consent: bool,
    timezone_name: str = "UTC",
) -> ViewingAppointment:
    """
    Validate and create a viewing request.
    """

    get_property(db, property_id)
    get_available_unit(
        db,
        property_id=property_id,
        unit_id=unit_id,
    )

    if viewing_type not in ALLOWED_VIEWING_TYPES:
        raise AppointmentValidationError(
            "Select a valid viewing method."
        )

    if not contact_consent:
        raise AppointmentValidationError(
            "Contact consent is required."
        )

    if not reminder_consent:
        raise AppointmentValidationError(
            "Reminder consent is required."
        )

    if not privacy_consent:
        raise AppointmentValidationError(
            "Privacy consent is required."
        )

    preferred_datetime = combine_datetime(
        preferred_date,
        preferred_time,
        timezone_name=timezone_name,
        date_field_name="Preferred date",
        time_field_name="Preferred time",
    )

    alternative_datetime = None

    if alternative_date or alternative_time:
        if not alternative_date or not alternative_time:
            raise AppointmentValidationError(
                "Provide both an alternative date and time."
            )

        alternative_datetime = combine_datetime(
            alternative_date,
            alternative_time,
            timezone_name=timezone_name,
            date_field_name="Alternative date",
            time_field_name="Alternative time",
        )

        if alternative_datetime == preferred_datetime:
            raise AppointmentValidationError(
                "Alternative time must differ from the preferred time."
            )

    accommodation = clean_text(
        accommodation_details,
        maximum_length=1000,
        field_name="Accommodation details",
    )

    if needs_accommodation and not accommodation:
        raise AppointmentValidationError(
            "Describe the accommodation you need."
        )

    conflicting_request = (
        db.query(ViewingAppointment)
        .filter(
            ViewingAppointment.unit_id == unit_id,
            ViewingAppointment.preferred_datetime
            == preferred_datetime,
            ViewingAppointment.status.in_(
                ["requested", "confirmed"]
            ),
        )
        .first()
    )

    if conflicting_request is not None:
        raise AppointmentConflictError(
            "That appointment time is no longer available."
        )

    reminder_requested = any(
        (
            reminder_email,
            reminder_sms,
            reminder_whatsapp,
            reminder_phone,
        )
    )

    appointment = ViewingAppointment(
        property_id=property_id,
        unit_id=unit_id,
        requester_user_id=requester_user_id,
        first_name=clean_text(
            first_name,
            maximum_length=100,
            required=True,
            field_name="First name",
        ),
        last_name=clean_text(
            last_name,
            maximum_length=100,
            required=True,
            field_name="Last name",
        ),
        email=clean_email(email),
        phone=clean_phone(phone),
        preferred_language=clean_text(
            preferred_language,
            maximum_length=20,
            field_name="Preferred language",
        ) or "en",
        preferred_datetime=preferred_datetime,
        alternative_datetime=alternative_datetime,
        timezone_name=timezone_name,
        viewing_type=viewing_type,
        needs_accommodation=bool(needs_accommodation),
        accommodation_details=accommodation,
        message=clean_text(
            message,
            maximum_length=1500,
            field_name="Appointment message",
        ),
        reminder_email=bool(reminder_email),
        reminder_sms=bool(reminder_sms),
        reminder_whatsapp=bool(reminder_whatsapp),
        reminder_phone=bool(reminder_phone),
        reminder_at=(
            preferred_datetime - timedelta(minutes=30)
            if reminder_requested
            else None
        ),
        reminder_sent=False,
        contact_consent=True,
        reminder_consent=True,
        privacy_consent=True,
        status="requested",
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    try:
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
    except Exception:
        db.rollback()
        raise

    return appointment


def get_appointment(
    db: Session,
    appointment_id: int,
) -> ViewingAppointment:
    appointment = (
        db.query(ViewingAppointment)
        .filter(ViewingAppointment.id == appointment_id)
        .first()
    )

    if appointment is None:
        raise AppointmentNotFoundError(
            "Viewing appointment not found."
        )

    return appointment