"""Rental-application business logic."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from database.models import Property, RentalApplication, Unit


class ApplicationServiceError(Exception):
    """Base rental-application error."""


class ApplicationValidationError(ApplicationServiceError):
    """Raised when submitted application data is invalid."""


class ApplicationNotFoundError(ApplicationServiceError):
    """Raised when an application cannot be found."""


class UnitUnavailableError(ApplicationServiceError):
    """Raised when a unit is unavailable."""


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clean_text(
    value: Any,
    *,
    maximum_length: int | None = None,
    required: bool = False,
    field_name: str = "Field",
) -> str | None:
    if value is None:
        cleaned = ""
    else:
        cleaned = str(value).strip()

    if required and not cleaned:
        raise ApplicationValidationError(
            f"{field_name} is required."
        )

    if maximum_length and len(cleaned) > maximum_length:
        raise ApplicationValidationError(
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
    )

    email = email.lower()

    if not EMAIL_PATTERN.fullmatch(email):
        raise ApplicationValidationError(
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

    permitted = set(
        "0123456789+()- ."
    )

    if any(character not in permitted for character in phone):
        raise ApplicationValidationError(
            "Enter a valid phone number."
        )

    digits = "".join(
        character
        for character in phone
        if character.isdigit()
    )

    if len(digits) < 7:
        raise ApplicationValidationError(
            "Phone number is too short."
        )

    return phone


def parse_decimal(
    value: Any,
    *,
    field_name: str,
    minimum: Decimal = Decimal("0"),
) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ApplicationValidationError(
            f"{field_name} must be a valid number."
        ) from exc

    if number < minimum:
        raise ApplicationValidationError(
            f"{field_name} must be at least {minimum}."
        )

    return number.quantize(Decimal("0.01"))


def parse_integer(
    value: Any,
    *,
    field_name: str,
    minimum: int = 0,
    maximum: int = 100,
) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ApplicationValidationError(
            f"{field_name} must be a whole number."
        ) from exc

    if number < minimum or number > maximum:
        raise ApplicationValidationError(
            f"{field_name} must be between "
            f"{minimum} and {maximum}."
        )

    return number


def parse_date(
    value: Any,
    *,
    field_name: str,
    future_only: bool = False,
) -> date:
    if isinstance(value, date):
        parsed = value
    else:
        try:
            parsed = date.fromisoformat(str(value))
        except (TypeError, ValueError) as exc:
            raise ApplicationValidationError(
                f"{field_name} must be a valid date."
            ) from exc

    if future_only and parsed < date.today():
        raise ApplicationValidationError(
            f"{field_name} cannot be in the past."
        )

    return parsed


def validate_csrf(
    submitted_token: str | None,
    session_token: str | None,
) -> None:
    """
    Validate a form CSRF token using constant-time comparison.
    """

    import secrets

    if not submitted_token or not session_token:
        raise ApplicationValidationError(
            "Your form session expired. Refresh the page and try again."
        )

    if not secrets.compare_digest(
        submitted_token,
        session_token,
    ):
        raise ApplicationValidationError(
            "Invalid form security token."
        )


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
        raise UnitUnavailableError(
            "The selected unit does not exist."
        )

    if hasattr(unit, "is_active") and not unit.is_active:
        raise UnitUnavailableError(
            "The selected unit is inactive."
        )

    if (
        hasattr(unit, "is_available")
        and not unit.is_available
    ):
        raise UnitUnavailableError(
            "The selected unit is no longer available."
        )

    status_value = _status_value(unit)

    if status_value and status_value not in {
        "available",
        "vacant",
        "ready",
    }:
        raise UnitUnavailableError(
            "The selected unit is no longer available."
        )

    return unit


def get_public_property(
    db: Session,
    property_id: int,
) -> Property:
    property_record = (
        db.query(Property)
        .filter(Property.id == property_id)
        .first()
    )

    if property_record is None:
        raise ApplicationValidationError(
            "The requested property does not exist."
        )

    if (
        hasattr(property_record, "is_active")
        and not property_record.is_active
    ):
        raise ApplicationValidationError(
            "This property is not accepting applications."
        )

    return property_record


def create_application(
    db: Session,
    *,
    property_id: int,
    unit_id: int,
    user_id: int | None,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    current_address: str,
    current_city: str,
    postal_code: str,
    adult_occupants: int,
    child_occupants: int,
    desired_move_in_date: date | str,
    lease_duration_months: int | None,
    has_pets: bool,
    pet_details: str | None,
    employment_status: str,
    employer_name: str | None,
    monthly_income: Decimal | str | float,
    employment_length: str | None,
    message: str | None,
    information_confirmed: bool,
    privacy_consent: bool,
    landlord_contact_consent: bool,
    ai_assistance_consent: bool = False,
) -> RentalApplication:
    """
    Validate and save a new rental application.
    """

    get_public_property(db, property_id)
    get_available_unit(
        db,
        property_id=property_id,
        unit_id=unit_id,
    )

    if not information_confirmed:
        raise ApplicationValidationError(
            "You must confirm that your information is accurate."
        )

    if not privacy_consent:
        raise ApplicationValidationError(
            "Privacy consent is required."
        )

    if not landlord_contact_consent:
        raise ApplicationValidationError(
            "Contact consent is required."
        )

    adults = parse_integer(
        adult_occupants,
        field_name="Adult occupants",
        minimum=1,
        maximum=20,
    )

    children = parse_integer(
        child_occupants,
        field_name="Child occupants",
        minimum=0,
        maximum=20,
    )

    lease_duration = None

    if lease_duration_months not in (None, ""):
        lease_duration = parse_integer(
            lease_duration_months,
            field_name="Lease duration",
            minimum=1,
            maximum=120,
        )

    cleaned_pet_details = clean_text(
        pet_details,
        maximum_length=500,
        field_name="Pet details",
    )

    if has_pets and not cleaned_pet_details:
        raise ApplicationValidationError(
            "Provide basic information about your pets."
        )

    application = RentalApplication(
        property_id=property_id,
        unit_id=unit_id,
        applicant_user_id=user_id,
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
        current_address=clean_text(
            current_address,
            maximum_length=250,
            required=True,
            field_name="Current address",
        ),
        current_city=clean_text(
            current_city,
            maximum_length=120,
            required=True,
            field_name="Current city",
        ),
        postal_code=clean_text(
            postal_code,
            maximum_length=20,
            required=True,
            field_name="Postal code",
        ),
        adult_occupants=adults,
        child_occupants=children,
        desired_move_in_date=parse_date(
            desired_move_in_date,
            field_name="Desired move-in date",
            future_only=True,
        ),
        lease_duration_months=lease_duration,
        has_pets=bool(has_pets),
        pet_details=cleaned_pet_details,
        employment_status=clean_text(
            employment_status,
            maximum_length=50,
            required=True,
            field_name="Employment status",
        ),
        employer_name=clean_text(
            employer_name,
            maximum_length=150,
            field_name="Employer or income source",
        ),
        monthly_income=parse_decimal(
            monthly_income,
            field_name="Monthly income",
        ),
        employment_length=clean_text(
            employment_length,
            maximum_length=100,
            field_name="Employment length",
        ),
        message=clean_text(
            message,
            maximum_length=2000,
            field_name="Application message",
        ),
        status="submitted",
        information_confirmed=True,
        privacy_consent=True,
        landlord_contact_consent=True,
        ai_assistance_consent=bool(ai_assistance_consent),
        submitted_at=utc_now(),
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    try:
        db.add(application)
        db.commit()
        db.refresh(application)
    except Exception:
        db.rollback()
        raise

    return application


def get_application(
    db: Session,
    application_id: int,
) -> RentalApplication:
    application = (
        db.query(RentalApplication)
        .filter(RentalApplication.id == application_id)
        .first()
    )

    if application is None:
        raise ApplicationNotFoundError(
            "Rental application not found."
        )

    return application