"""
Smart Property AI apartment-unit service.

File:
    services/unit_service.py
"""

import hashlib
import hmac
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database.models import (
    AuditLog,
    Lease,
    LeaseStatus,
    Listing,
    Unit,
    UnitStatus,
    User,
)
from security.permissions import (
    ensure_property_access,
    ensure_property_can_be_managed,
)


# ==========================================================================
# Exceptions
# ==========================================================================

class UnitServiceError(Exception):
    """Base exception for unit-service errors."""

    pass


class UnitValidationError(UnitServiceError):
    """Raised when unit information is invalid."""

    def __init__(
        self,
        errors: list[str],
    ):
        self.errors = errors
        super().__init__(" ".join(errors))


class UnitNotFoundError(UnitServiceError):
    """Raised when an apartment unit cannot be found."""

    pass


class UnitConflictError(UnitServiceError):
    """Raised when a unit operation conflicts with saved data."""

    pass


# ==========================================================================
# Data classes
# ==========================================================================

@dataclass
class UnitData:
    """Information used to create or update a unit."""

    unit_number: str
    rooms: str | float | Decimal
    monthly_rent: str | float | Decimal

    floor: Optional[str] = None
    bedrooms: int | str = 0
    bathrooms: int | str = 1
    area_square_metres: Optional[str | float | Decimal] = None
    deposit_amount: Optional[str | float | Decimal] = None
    currency: str = "EUR"
    wheelchair_accessible: bool = False
    pets_allowed: bool = False


@dataclass
class UnitStatistics:
    """Summary statistics for units in a property."""

    total_units: int
    vacant_units: int
    occupied_units: int
    maintenance_units: int
    unavailable_units: int
    total_monthly_rent: Decimal
    occupied_monthly_rent: Decimal
    potential_monthly_rent: Decimal


# ==========================================================================
# Unit service
# ==========================================================================

class UnitService:
    """Business logic for apartment-unit management."""

    SUPPORTED_CURRENCIES = {
        "EUR",
        "USD",
        "GBP",
        "NGN",
        "GHS",
        "CAD",
        "AUD",
    }

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    # ----------------------------------------------------------------------
    # Validation
    # ----------------------------------------------------------------------

    @staticmethod
    def normalize_optional_text(
        value: Optional[str],
    ) -> Optional[str]:
        """Strip optional text and convert empty strings to None."""

        if value is None:
            return None

        cleaned_value = value.strip()

        return cleaned_value or None

    @staticmethod
    def parse_decimal(
        value: Optional[str | float | Decimal],
        field_name: str,
        minimum: Optional[Decimal] = None,
        maximum: Optional[Decimal] = None,
        allow_none: bool = False,
    ) -> Optional[Decimal]:
        """Convert and validate a decimal value."""

        if value is None or value == "":
            if allow_none:
                return None

            raise UnitValidationError(
                [f"{field_name} is required."]
            )

        try:
            parsed_value = Decimal(
                str(value).strip()
            )
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as error:
            raise UnitValidationError(
                [f"{field_name} must be a valid number."]
            ) from error

        if not parsed_value.is_finite():
            raise UnitValidationError(
                [f"{field_name} must be a finite number."]
            )

        if minimum is not None and parsed_value < minimum:
            raise UnitValidationError(
                [
                    f"{field_name} must be at least "
                    f"{minimum}."
                ]
            )

        if maximum is not None and parsed_value > maximum:
            raise UnitValidationError(
                [
                    f"{field_name} must not exceed "
                    f"{maximum}."
                ]
            )

        return parsed_value

    @staticmethod
    def parse_integer(
        value: int | str,
        field_name: str,
        minimum: int = 0,
        maximum: int = 100,
    ) -> int:
        """Convert and validate an integer value."""

        try:
            parsed_value = int(value)
        except (
            TypeError,
            ValueError,
        ) as error:
            raise UnitValidationError(
                [f"{field_name} must be a whole number."]
            ) from error

        if parsed_value < minimum:
            raise UnitValidationError(
                [
                    f"{field_name} must be at least "
                    f"{minimum}."
                ]
            )

        if parsed_value > maximum:
            raise UnitValidationError(
                [
                    f"{field_name} must not exceed "
                    f"{maximum}."
                ]
            )

        return parsed_value

    def validate_unit_data(
        self,
        unit_data: UnitData,
    ) -> UnitData:
        """Normalize and validate all apartment-unit information."""

        errors = []

        unit_number = unit_data.unit_number.strip()

        floor = self.normalize_optional_text(
            unit_data.floor
        )

        currency = (
            unit_data.currency.strip().upper()
            if unit_data.currency
            else settings.DEFAULT_CURRENCY
        )

        if not unit_number:
            errors.append(
                "Unit number is required."
            )

        if len(unit_number) > 50:
            errors.append(
                "Unit number must not exceed 50 characters."
            )

        if floor and len(floor) > 30:
            errors.append(
                "Floor must not exceed 30 characters."
            )

        if currency not in self.SUPPORTED_CURRENCIES:
            errors.append(
                "The selected currency is not supported."
            )

        rooms = Decimal("0")
        monthly_rent = Decimal("0")
        area_square_metres = None
        deposit_amount = None
        bedrooms = 0
        bathrooms = 1

        try:
            rooms = self.parse_decimal(
                value=unit_data.rooms,
                field_name="Rooms",
                minimum=Decimal("0.5"),
                maximum=Decimal("100"),
            )
        except UnitValidationError as error:
            errors.extend(error.errors)

        try:
            monthly_rent = self.parse_decimal(
                value=unit_data.monthly_rent,
                field_name="Monthly rent",
                minimum=Decimal("0"),
                maximum=Decimal("100000000"),
            )
        except UnitValidationError as error:
            errors.extend(error.errors)

        try:
            bedrooms = self.parse_integer(
                value=unit_data.bedrooms,
                field_name="Bedrooms",
                minimum=0,
                maximum=100,
            )
        except UnitValidationError as error:
            errors.extend(error.errors)

        try:
            bathrooms = self.parse_integer(
                value=unit_data.bathrooms,
                field_name="Bathrooms",
                minimum=0,
                maximum=100,
            )
        except UnitValidationError as error:
            errors.extend(error.errors)

        try:
            area_square_metres = self.parse_decimal(
                value=unit_data.area_square_metres,
                field_name="Area",
                minimum=Decimal("1"),
                maximum=Decimal("1000000"),
                allow_none=True,
            )
        except UnitValidationError as error:
            errors.extend(error.errors)

        try:
            deposit_amount = self.parse_decimal(
                value=unit_data.deposit_amount,
                field_name="Deposit amount",
                minimum=Decimal("0"),
                maximum=Decimal("100000000"),
                allow_none=True,
            )
        except UnitValidationError as error:
            errors.extend(error.errors)

        if (
            rooms is not None
            and Decimal(bedrooms) > rooms
        ):
            errors.append(
                "Bedrooms cannot exceed the total number of rooms."
            )

        if errors:
            raise UnitValidationError(errors)

        return UnitData(
            unit_number=unit_number,
            floor=floor,
            rooms=rooms,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            area_square_metres=area_square_metres,
            monthly_rent=monthly_rent,
            deposit_amount=deposit_amount,
            currency=currency,
            wheelchair_accessible=bool(
                unit_data.wheelchair_accessible
            ),
            pets_allowed=bool(
                unit_data.pets_allowed
            ),
        )

    # ----------------------------------------------------------------------
    # Create unit
    # ----------------------------------------------------------------------

    def create_unit(
        self,
        current_user: User,
        property_id: str,
        unit_data: UnitData,
        request: Optional[Request] = None,
    ) -> Unit:
        """Create a unit in an authorized property."""

        ensure_property_can_be_managed(
            db=self.db,
            user=current_user,
            property_id=property_id,
        )

        validated_data = self.validate_unit_data(
            unit_data
        )

        duplicate_unit = self.db.scalar(
            select(Unit).where(
                Unit.property_id == property_id,
                func.lower(Unit.unit_number)
                == validated_data.unit_number.lower(),
            )
        )

        if duplicate_unit:
            raise UnitConflictError(
                "A unit with this number already exists "
                "in the selected property."
            )

        unit = Unit(
            property_id=property_id,
            unit_number=validated_data.unit_number,
            floor=validated_data.floor,
            rooms=validated_data.rooms,
            bedrooms=validated_data.bedrooms,
            bathrooms=validated_data.bathrooms,
            area_square_metres=(
                validated_data.area_square_metres
            ),
            monthly_rent=validated_data.monthly_rent,
            deposit_amount=validated_data.deposit_amount,
            currency=validated_data.currency,
            wheelchair_accessible=(
                validated_data.wheelchair_accessible
            ),
            pets_allowed=validated_data.pets_allowed,
            status=UnitStatus.VACANT,
        )

        try:
            self.db.add(unit)
            self.db.flush()

            self.create_audit_log(
                current_user=current_user,
                action="unit.created",
                result="success",
                unit_id=unit.id,
                property_id=property_id,
                details=(
                    f"Unit {unit.unit_number} was created "
                    "with vacant status."
                ),
                request=request,
            )

            self.db.commit()
            self.db.refresh(unit)

            return unit

        except IntegrityError as error:
            self.db.rollback()

            raise UnitConflictError(
                "The unit could not be created because "
                "its unit number already exists."
            ) from error

        except Exception:
            self.db.rollback()
            raise

    # ----------------------------------------------------------------------
    # Retrieve units
    # ----------------------------------------------------------------------

    def get_unit_by_id(
        self,
        unit_id: str,
    ) -> Optional[Unit]:
        """Return a unit without applying permission checks."""

        return self.db.get(
            Unit,
            unit_id,
        )

    def get_accessible_unit(
        self,
        current_user: User,
        unit_id: str,
    ) -> Unit:
        """Return a unit after checking property access."""

        unit = self.get_unit_by_id(
            unit_id
        )

        if unit is None:
            raise UnitNotFoundError(
                "The requested apartment unit was not found."
            )

        ensure_property_access(
            db=self.db,
            user=current_user,
            property_id=unit.property_id,
        )

        return unit

    def get_manageable_unit(
        self,
        current_user: User,
        unit_id: str,
    ) -> Unit:
        """Return a unit the user is authorized to manage."""

        unit = self.get_unit_by_id(
            unit_id
        )

        if unit is None:
            raise UnitNotFoundError(
                "The requested apartment unit was not found."
            )

        ensure_property_can_be_managed(
            db=self.db,
            user=current_user,
            property_id=unit.property_id,
        )

        return unit

    def list_units(
        self,
        current_user: User,
        property_id: str,
        page: int = 1,
        page_size: int = 25,
        unit_status: Optional[UnitStatus] = None,
        search: Optional[str] = None,
    ) -> list[Unit]:
        """List units belonging to an accessible property."""

        ensure_property_access(
            db=self.db,
            user=current_user,
            property_id=property_id,
        )

        page = max(page, 1)

        page_size = max(
            1,
            min(page_size, 100),
        )

        query = select(Unit).where(
            Unit.property_id == property_id
        )

        if unit_status:
            query = query.where(
                Unit.status == unit_status
            )

        if search:
            search_term = (
                f"%{search.strip().lower()}%"
            )

            query = query.where(
                func.lower(Unit.unit_number).like(
                    search_term
                )
            )

        query = (
            query
            .order_by(Unit.unit_number.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        return list(
            self.db.scalars(query).all()
        )

    def count_units(
        self,
        current_user: User,
        property_id: str,
        unit_status: Optional[UnitStatus] = None,
        search: Optional[str] = None,
    ) -> int:
        """Count units belonging to an accessible property."""

        ensure_property_access(
            db=self.db,
            user=current_user,
            property_id=property_id,
        )

        query = select(
            func.count(Unit.id)
        ).where(
            Unit.property_id == property_id
        )

        if unit_status:
            query = query.where(
                Unit.status == unit_status
            )

        if search:
            search_term = (
                f"%{search.strip().lower()}%"
            )

            query = query.where(
                func.lower(Unit.unit_number).like(
                    search_term
                )
            )

        return int(
            self.db.scalar(query) or 0
        )

    # ----------------------------------------------------------------------
    # Update unit
    # ----------------------------------------------------------------------

    def update_unit(
        self,
        current_user: User,
        unit_id: str,
        unit_data: UnitData,
        request: Optional[Request] = None,
    ) -> Unit:
        """Update an apartment unit."""

        unit = self.get_manageable_unit(
            current_user=current_user,
            unit_id=unit_id,
        )

        validated_data = self.validate_unit_data(
            unit_data
        )

        duplicate_unit = self.db.scalar(
            select(Unit).where(
                Unit.id != unit.id,
                Unit.property_id == unit.property_id,
                func.lower(Unit.unit_number)
                == validated_data.unit_number.lower(),
            )
        )

        if duplicate_unit:
            raise UnitConflictError(
                "Another unit with this number already "
                "exists in the selected property."
            )

        unit.unit_number = validated_data.unit_number
        unit.floor = validated_data.floor
        unit.rooms = validated_data.rooms
        unit.bedrooms = validated_data.bedrooms
        unit.bathrooms = validated_data.bathrooms

        unit.area_square_metres = (
            validated_data.area_square_metres
        )

        unit.monthly_rent = (
            validated_data.monthly_rent
        )

        unit.deposit_amount = (
            validated_data.deposit_amount
        )

        unit.currency = validated_data.currency

        unit.wheelchair_accessible = (
            validated_data.wheelchair_accessible
        )

        unit.pets_allowed = (
            validated_data.pets_allowed
        )

        try:
            self.create_audit_log(
                current_user=current_user,
                action="unit.updated",
                result="success",
                unit_id=unit.id,
                property_id=unit.property_id,
                details=(
                    f"Unit {unit.unit_number} was updated."
                ),
                request=request,
            )

            self.db.commit()
            self.db.refresh(unit)

            return unit

        except IntegrityError as error:
            self.db.rollback()

            raise UnitConflictError(
                "The unit could not be updated because "
                "its number conflicts with another record."
            ) from error

        except Exception:
            self.db.rollback()
            raise

    # ----------------------------------------------------------------------
    # Unit status
    # ----------------------------------------------------------------------

    def get_active_lease(
        self,
        unit_id: str,
    ) -> Optional[Lease]:
        """Return the active or expiring lease for a unit."""

        return self.db.scalar(
            select(Lease).where(
                Lease.unit_id == unit_id,
                Lease.status.in_(
                    [
                        LeaseStatus.ACTIVE,
                        LeaseStatus.EXPIRING,
                    ]
                ),
            )
        )

    def change_unit_status(
        self,
        current_user: User,
        unit_id: str,
        new_status: UnitStatus | str,
        request: Optional[Request] = None,
    ) -> Unit:
        """Change an apartment unit's status."""

        unit = self.get_manageable_unit(
            current_user=current_user,
            unit_id=unit_id,
        )

        if not isinstance(
            new_status,
            UnitStatus,
        ):
            try:
                new_status = UnitStatus(
                    str(new_status).strip().lower()
                )
            except ValueError as error:
                raise UnitValidationError(
                    [
                        "The selected unit status is invalid."
                    ]
                ) from error

        previous_status = unit.status

        if previous_status == new_status:
            return unit

        active_lease = self.get_active_lease(
            unit.id
        )

        if (
            new_status == UnitStatus.VACANT
            and active_lease is not None
        ):
            raise UnitConflictError(
                "This unit cannot be marked vacant while "
                "it has an active lease."
            )

        if (
            new_status == UnitStatus.OCCUPIED
            and active_lease is None
        ):
            raise UnitConflictError(
                "This unit cannot be marked occupied until "
                "an active lease has been created."
            )

        unit.status = new_status

        self.create_audit_log(
            current_user=current_user,
            action="unit.status_changed",
            result="success",
            unit_id=unit.id,
            property_id=unit.property_id,
            details=(
                f"Unit status changed from "
                f"{previous_status.value} to "
                f"{new_status.value}."
            ),
            request=request,
        )

        self.db.commit()
        self.db.refresh(unit)

        return unit

    def mark_vacant(
        self,
        current_user: User,
        unit_id: str,
        request: Optional[Request] = None,
    ) -> Unit:
        """Mark a unit as vacant."""

        return self.change_unit_status(
            current_user=current_user,
            unit_id=unit_id,
            new_status=UnitStatus.VACANT,
            request=request,
        )

    def mark_occupied(
        self,
        current_user: User,
        unit_id: str,
        request: Optional[Request] = None,
    ) -> Unit:
        """Mark a unit as occupied."""

        return self.change_unit_status(
            current_user=current_user,
            unit_id=unit_id,
            new_status=UnitStatus.OCCUPIED,
            request=request,
        )

    def mark_for_maintenance(
        self,
        current_user: User,
        unit_id: str,
        request: Optional[Request] = None,
    ) -> Unit:
        """Place a unit into maintenance status."""

        return self.change_unit_status(
            current_user=current_user,
            unit_id=unit_id,
            new_status=UnitStatus.MAINTENANCE,
            request=request,
        )

    def mark_unavailable(
        self,
        current_user: User,
        unit_id: str,
        request: Optional[Request] = None,
    ) -> Unit:
        """Mark a unit as unavailable."""

        return self.change_unit_status(
            current_user=current_user,
            unit_id=unit_id,
            new_status=UnitStatus.UNAVAILABLE,
            request=request,
        )

    # ----------------------------------------------------------------------
    # Removal
    # ----------------------------------------------------------------------

    def unit_has_history(
        self,
        unit_id: str,
    ) -> tuple[bool, Optional[str]]:
        """Check whether a unit has lease or listing history."""

        lease_id = self.db.scalar(
            select(Lease.id).where(
                Lease.unit_id == unit_id
            ).limit(1)
        )

        if lease_id:
            return (
                True,
                "The unit has lease history and cannot be deleted.",
            )

        listing_id = self.db.scalar(
            select(Listing.id).where(
                Listing.unit_id == unit_id
            ).limit(1)
        )

        if listing_id:
            return (
                True,
                "The unit has listing history and cannot be deleted.",
            )

        return False, None

    def remove_unit(
        self,
        current_user: User,
        unit_id: str,
        request: Optional[Request] = None,
    ) -> None:
        """
        Permanently remove a unit with no lease or listing history.

        A unit with history should be marked unavailable instead.
        """

        unit = self.get_manageable_unit(
            current_user=current_user,
            unit_id=unit_id,
        )

        has_history, reason = self.unit_has_history(
            unit.id
        )

        if has_history:
            raise UnitConflictError(
                reason or "The unit cannot be deleted."
            )

        unit_number = unit.unit_number
        property_id = unit.property_id
        saved_unit_id = unit.id

        try:
            self.create_audit_log(
                current_user=current_user,
                action="unit.deleted",
                result="success",
                unit_id=saved_unit_id,
                property_id=property_id,
                details=(
                    f"Unit {unit_number} was permanently deleted."
                ),
                request=request,
            )

            self.db.delete(unit)
            self.db.commit()

        except IntegrityError as error:
            self.db.rollback()

            raise UnitConflictError(
                "The unit cannot be deleted because another "
                "record depends on it."
            ) from error

        except Exception:
            self.db.rollback()
            raise

    def deactivate_unit(
        self,
        current_user: User,
        unit_id: str,
        request: Optional[Request] = None,
    ) -> Unit:
        """Mark a unit unavailable without deleting its history."""

        return self.change_unit_status(
            current_user=current_user,
            unit_id=unit_id,
            new_status=UnitStatus.UNAVAILABLE,
            request=request,
        )

    # ----------------------------------------------------------------------
    # Statistics
    # ----------------------------------------------------------------------

    def get_unit_statistics(
        self,
        current_user: User,
        property_id: str,
    ) -> UnitStatistics:
        """Return unit and rent statistics for a property."""

        ensure_property_access(
            db=self.db,
            user=current_user,
            property_id=property_id,
        )

        total_units = self.db.scalar(
            select(func.count(Unit.id)).where(
                Unit.property_id == property_id
            )
        ) or 0

        vacant_units = self.db.scalar(
            select(func.count(Unit.id)).where(
                Unit.property_id == property_id,
                Unit.status == UnitStatus.VACANT,
            )
        ) or 0

        occupied_units = self.db.scalar(
            select(func.count(Unit.id)).where(
                Unit.property_id == property_id,
                Unit.status == UnitStatus.OCCUPIED,
            )
        ) or 0

        maintenance_units = self.db.scalar(
            select(func.count(Unit.id)).where(
                Unit.property_id == property_id,
                Unit.status == UnitStatus.MAINTENANCE,
            )
        ) or 0

        unavailable_units = self.db.scalar(
            select(func.count(Unit.id)).where(
                Unit.property_id == property_id,
                Unit.status == UnitStatus.UNAVAILABLE,
            )
        ) or 0

        total_monthly_rent = self.db.scalar(
            select(
                func.coalesce(
                    func.sum(Unit.monthly_rent),
                    0,
                )
            ).where(
                Unit.property_id == property_id
            )
        ) or Decimal("0")

        occupied_monthly_rent = self.db.scalar(
            select(
                func.coalesce(
                    func.sum(Unit.monthly_rent),
                    0,
                )
            ).where(
                Unit.property_id == property_id,
                Unit.status == UnitStatus.OCCUPIED,
            )
        ) or Decimal("0")

        potential_monthly_rent = self.db.scalar(
            select(
                func.coalesce(
                    func.sum(Unit.monthly_rent),
                    0,
                )
            ).where(
                Unit.property_id == property_id,
                Unit.status.in_(
                    [
                        UnitStatus.VACANT,
                        UnitStatus.OCCUPIED,
                    ]
                ),
            )
        ) or Decimal("0")

        return UnitStatistics(
            total_units=int(total_units),
            vacant_units=int(vacant_units),
            occupied_units=int(occupied_units),
            maintenance_units=int(maintenance_units),
            unavailable_units=int(unavailable_units),
            total_monthly_rent=Decimal(
                str(total_monthly_rent)
            ),
            occupied_monthly_rent=Decimal(
                str(occupied_monthly_rent)
            ),
            potential_monthly_rent=Decimal(
                str(potential_monthly_rent)
            ),
        )

    # ----------------------------------------------------------------------
    # Audit logging
    # ----------------------------------------------------------------------

    @staticmethod
    def hash_request_ip(
        request: Optional[Request],
    ) -> Optional[str]:
        """Create a keyed hash of the request IP address."""

        if request is None:
            return None

        forwarded_for = request.headers.get(
            "x-forwarded-for",
            "",
        )

        if forwarded_for:
            client_address = (
                forwarded_for.split(",")[0].strip()
            )
        elif request.client:
            client_address = request.client.host
        else:
            client_address = ""

        if not client_address:
            return None

        return hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            client_address.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def create_audit_log(
        self,
        current_user: User,
        action: str,
        result: str,
        unit_id: Optional[str] = None,
        property_id: Optional[str] = None,
        details: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """Create an apartment-unit audit record."""

        safe_details = details

        if property_id:
            property_reference = (
                f"Property ID: {property_id}."
            )

            safe_details = (
                f"{details} {property_reference}"
                if details
                else property_reference
            )

        audit_log = AuditLog(
            user_id=current_user.id,
            action=action,
            resource_type="unit",
            resource_id=unit_id,
            result=result,
            details=safe_details,
            ip_hash=self.hash_request_ip(request),
        )

        self.db.add(audit_log)

        return audit_log