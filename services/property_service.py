"""
Smart Property AI property service.

File:
    services/property_service.py
"""

import hashlib
import hmac
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database.models import (
    AccountStatus,
    AuditLog,
    Listing,
    ListingStatus,
    Property,
    PropertyStatus,
    Unit,
    UnitStatus,
    User,
    UserRole,
)
from security.permissions import (
    ensure_landlord_owns_property,
    ensure_property_access,
    ensure_property_can_be_managed,
)


# ==========================================================================
# Exceptions
# ==========================================================================

class PropertyServiceError(Exception):
    """Base property-service exception."""

    pass


class PropertyValidationError(PropertyServiceError):
    """Raised when property information is invalid."""

    def __init__(
        self,
        errors: list[str],
    ):
        self.errors = errors
        super().__init__(" ".join(errors))


class PropertyNotFoundError(PropertyServiceError):
    """Raised when a property cannot be found."""

    pass


class PropertyPermissionError(PropertyServiceError):
    """Raised when a property action is not permitted."""

    pass


class PropertyConflictError(PropertyServiceError):
    """Raised when property information conflicts with saved data."""

    pass


# ==========================================================================
# Data classes
# ==========================================================================

@dataclass
class PropertyData:
    """Information used to create or update a property."""

    name: str
    property_type: str
    street_address: str
    postal_code: str
    city: str
    country: str = "Germany"
    state: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[str | float | Decimal] = None
    longitude: Optional[str | float | Decimal] = None


@dataclass
class PropertyStatistics:
    """Property unit and listing statistics."""

    total_units: int
    vacant_units: int
    occupied_units: int
    maintenance_units: int
    unavailable_units: int
    total_listings: int
    published_listings: int


# ==========================================================================
# Property service
# ==========================================================================

class PropertyService:
    """Business logic for property management."""

    ALLOWED_PROPERTY_TYPES = {
        "apartment_building",
        "house",
        "duplex",
        "townhouse",
        "student_housing",
        "senior_housing",
        "commercial",
        "mixed_use",
        "other",
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
    def normalize_property_type(
        property_type: str,
    ) -> str:
        """Normalize the property-type value."""

        return (
            property_type
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

    @staticmethod
    def parse_coordinate(
        value: Optional[str | float | Decimal],
        coordinate_name: str,
    ) -> Optional[Decimal]:
        """Validate a latitude or longitude value."""

        if value is None or value == "":
            return None

        try:
            coordinate = Decimal(
                str(value).strip()
            )
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as error:
            raise PropertyValidationError(
                [
                    f"{coordinate_name} must be a valid number."
                ]
            ) from error

        if not coordinate.is_finite():
            raise PropertyValidationError(
                [
                    f"{coordinate_name} must be a finite number."
                ]
            )

        if coordinate_name == "Latitude":
            if (
                coordinate < Decimal("-90")
                or coordinate > Decimal("90")
            ):
                raise PropertyValidationError(
                    [
                        "Latitude must be between -90 and 90."
                    ]
                )

        if coordinate_name == "Longitude":
            if (
                coordinate < Decimal("-180")
                or coordinate > Decimal("180")
            ):
                raise PropertyValidationError(
                    [
                        "Longitude must be between -180 and 180."
                    ]
                )

        return coordinate

    def validate_property_data(
        self,
        property_data: PropertyData,
    ) -> PropertyData:
        """Normalize and validate all property information."""

        errors = []

        name = property_data.name.strip()

        property_type = self.normalize_property_type(
            property_data.property_type
        )

        street_address = (
            property_data.street_address.strip()
        )

        postal_code = (
            property_data.postal_code.strip()
        )

        city = property_data.city.strip()

        country = (
            property_data.country.strip()
            if property_data.country
            else "Germany"
        )

        state = self.normalize_optional_text(
            property_data.state
        )

        description = self.normalize_optional_text(
            property_data.description
        )

        if len(name) < 2:
            errors.append(
                "Property name must contain at least 2 characters."
            )

        if len(name) > 200:
            errors.append(
                "Property name must not exceed 200 characters."
            )

        if not property_type:
            errors.append(
                "Please select a property type."
            )

        elif property_type not in self.ALLOWED_PROPERTY_TYPES:
            errors.append(
                "The selected property type is not supported."
            )

        if len(street_address) < 4:
            errors.append(
                "Please enter a complete street address."
            )

        if len(street_address) > 255:
            errors.append(
                "Street address must not exceed 255 characters."
            )

        if len(postal_code) < 3:
            errors.append(
                "Please enter a valid postal code."
            )

        if len(postal_code) > 20:
            errors.append(
                "Postal code must not exceed 20 characters."
            )

        if len(city) < 2:
            errors.append(
                "Please enter a valid city."
            )

        if len(city) > 100:
            errors.append(
                "City must not exceed 100 characters."
            )

        if len(country) < 2:
            errors.append(
                "Please enter a valid country."
            )

        if len(country) > 100:
            errors.append(
                "Country must not exceed 100 characters."
            )

        if state and len(state) > 100:
            errors.append(
                "State or region must not exceed 100 characters."
            )

        if description and len(description) > 10_000:
            errors.append(
                "Description must not exceed 10,000 characters."
            )

        latitude = None
        longitude = None

        try:
            latitude = self.parse_coordinate(
                property_data.latitude,
                "Latitude",
            )
        except PropertyValidationError as error:
            errors.extend(error.errors)

        try:
            longitude = self.parse_coordinate(
                property_data.longitude,
                "Longitude",
            )
        except PropertyValidationError as error:
            errors.extend(error.errors)

        if errors:
            raise PropertyValidationError(errors)

        return PropertyData(
            name=name,
            property_type=property_type,
            street_address=street_address,
            postal_code=postal_code,
            city=city,
            country=country,
            state=state,
            description=description,
            latitude=latitude,
            longitude=longitude,
        )

    # ----------------------------------------------------------------------
    # Create property
    # ----------------------------------------------------------------------

    def create_property(
        self,
        current_user: User,
        property_data: PropertyData,
        request: Optional[Request] = None,
    ) -> Property:
        """Create a property for a landlord or administrator."""

        if current_user.role not in {
            UserRole.LANDLORD,
            UserRole.ADMINISTRATOR,
        }:
            raise PropertyPermissionError(
                "Only landlords and administrators can "
                "create properties."
            )

        validated_data = self.validate_property_data(
            property_data
        )

        duplicate_property = self.db.scalar(
            select(Property).where(
                Property.owner_id == current_user.id,
                func.lower(Property.street_address)
                == validated_data.street_address.lower(),
                func.lower(Property.postal_code)
                == validated_data.postal_code.lower(),
                func.lower(Property.city)
                == validated_data.city.lower(),
            )
        )

        if duplicate_property:
            raise PropertyConflictError(
                "A property with this address is already "
                "registered in your account."
            )

        property_record = Property(
            owner_id=current_user.id,
            manager_id=None,
            name=validated_data.name,
            property_type=validated_data.property_type,
            description=validated_data.description,
            street_address=validated_data.street_address,
            postal_code=validated_data.postal_code,
            city=validated_data.city,
            state=validated_data.state,
            country=validated_data.country,
            latitude=validated_data.latitude,
            longitude=validated_data.longitude,
            status=PropertyStatus.DRAFT,
        )

        try:
            self.db.add(property_record)
            self.db.flush()

            self.create_audit_log(
                current_user=current_user,
                action="property.created",
                result="success",
                property_id=property_record.id,
                details=(
                    "Property created with draft status."
                ),
                request=request,
            )

            self.db.commit()
            self.db.refresh(property_record)

            return property_record

        except IntegrityError as error:
            self.db.rollback()

            raise PropertyConflictError(
                "The property could not be created because "
                "its information conflicts with an existing record."
            ) from error

        except Exception:
            self.db.rollback()
            raise

    # ----------------------------------------------------------------------
    # Retrieve properties
    # ----------------------------------------------------------------------

    def get_property_by_id(
        self,
        property_id: str,
    ) -> Optional[Property]:
        """Return a property without applying permission checks."""

        return self.db.get(
            Property,
            property_id,
        )

    def get_accessible_property(
        self,
        current_user: User,
        property_id: str,
    ) -> Property:
        """Return a property after checking general access."""

        ensure_property_access(
            db=self.db,
            user=current_user,
            property_id=property_id,
        )

        property_record = self.get_property_by_id(
            property_id
        )

        if property_record is None:
            raise PropertyNotFoundError(
                "The requested property was not found."
            )

        return property_record

    def get_manageable_property(
        self,
        current_user: User,
        property_id: str,
    ) -> Property:
        """Return a property the user is authorized to manage."""

        return ensure_property_can_be_managed(
            db=self.db,
            user=current_user,
            property_id=property_id,
        )

    def get_owned_property(
        self,
        current_user: User,
        property_id: str,
    ) -> Property:
        """Return a property owned by the landlord."""

        return ensure_landlord_owns_property(
            db=self.db,
            user=current_user,
            property_id=property_id,
        )

    def list_properties(
        self,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        property_status: Optional[PropertyStatus] = None,
    ) -> list[Property]:
        """List properties visible to a management user."""

        page = max(page, 1)
        page_size = max(
            1,
            min(page_size, 100),
        )

        query = select(Property)

        if current_user.role == UserRole.ADMINISTRATOR:
            pass

        elif current_user.role == UserRole.LANDLORD:
            query = query.where(
                Property.owner_id == current_user.id
            )

        elif current_user.role == UserRole.PROPERTY_MANAGER:
            query = query.where(
                Property.manager_id == current_user.id
            )

        else:
            raise PropertyPermissionError(
                "You do not have permission to view "
                "the property-management list."
            )

        if search:
            search_term = (
                f"%{search.strip().lower()}%"
            )

            query = query.where(
                or_(
                    func.lower(Property.name).like(search_term),
                    func.lower(
                        Property.street_address
                    ).like(search_term),
                    func.lower(Property.city).like(search_term),
                    func.lower(
                        Property.postal_code
                    ).like(search_term),
                )
            )

        if property_status:
            query = query.where(
                Property.status == property_status
            )

        query = (
            query
            .order_by(Property.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        return list(
            self.db.scalars(query).all()
        )

    def get_dashboard_statistics(self, db: Session, landlord_id: str) -> dict[str, int]:
        """Return dashboard statistics for the given landlord.

        Delegates to the high‑level function in ``services.landlord_service`` which
        aggregates property, unit, maintenance, and application counts.
        """
        from services.landlord_service import get_dashboard_statistics as _get_stats
        return _get_stats(db=db, landlord_id=landlord_id)

    def count_properties(
        self,
        current_user: User,
        search: Optional[str] = None,
        property_status: Optional[PropertyStatus] = None,
    ) -> int:
        """Count properties visible to a management user."""

        query = select(
            func.count(Property.id)
        )

        if current_user.role == UserRole.ADMINISTRATOR:
            pass

        elif current_user.role == UserRole.LANDLORD:
            query = query.where(
                Property.owner_id == current_user.id
            )

        elif current_user.role == UserRole.PROPERTY_MANAGER:
            query = query.where(
                Property.manager_id == current_user.id
            )

        else:
            return 0

        if search:
            search_term = (
                f"%{search.strip().lower()}%"
            )

            query = query.where(
                or_(
                    func.lower(Property.name).like(search_term),
                    func.lower(
                        Property.street_address
                    ).like(search_term),
                    func.lower(Property.city).like(search_term),
                    func.lower(
                        Property.postal_code
                    ).like(search_term),
                )
            )

        if property_status:
            query = query.where(
                Property.status == property_status
            )

        return int(
            self.db.scalar(query) or 0
        )

    # ----------------------------------------------------------------------
    # Update property
    # ----------------------------------------------------------------------

    def update_property(
        self,
        current_user: User,
        property_id: str,
        property_data: PropertyData,
        request: Optional[Request] = None,
    ) -> Property:
        """Update an authorized property."""

        property_record = self.get_manageable_property(
            current_user=current_user,
            property_id=property_id,
        )

        validated_data = self.validate_property_data(
            property_data
        )

        duplicate_property = self.db.scalar(
            select(Property).where(
                Property.id != property_id,
                Property.owner_id == property_record.owner_id,
                func.lower(Property.street_address)
                == validated_data.street_address.lower(),
                func.lower(Property.postal_code)
                == validated_data.postal_code.lower(),
                func.lower(Property.city)
                == validated_data.city.lower(),
            )
        )

        if duplicate_property:
            raise PropertyConflictError(
                "Another property with this address is "
                "already registered."
            )

        property_record.name = validated_data.name
        property_record.property_type = (
            validated_data.property_type
        )
        property_record.description = (
            validated_data.description
        )
        property_record.street_address = (
            validated_data.street_address
        )
        property_record.postal_code = (
            validated_data.postal_code
        )
        property_record.city = validated_data.city
        property_record.state = validated_data.state
        property_record.country = validated_data.country
        property_record.latitude = validated_data.latitude
        property_record.longitude = validated_data.longitude

        try:
            self.create_audit_log(
                current_user=current_user,
                action="property.updated",
                result="success",
                property_id=property_record.id,
                details="Property information updated.",
                request=request,
            )

            self.db.commit()
            self.db.refresh(property_record)

            return property_record

        except IntegrityError as error:
            self.db.rollback()

            raise PropertyConflictError(
                "The property could not be updated because "
                "its information conflicts with another record."
            ) from error

        except Exception:
            self.db.rollback()
            raise

    # ----------------------------------------------------------------------
    # Status changes
    # ----------------------------------------------------------------------

    def change_property_status(
        self,
        current_user: User,
        property_id: str,
        new_status: PropertyStatus | str,
        request: Optional[Request] = None,
    ) -> Property:
        """Change a property's status."""

        property_record = self.get_manageable_property(
            current_user=current_user,
            property_id=property_id,
        )

        if not isinstance(
            new_status,
            PropertyStatus,
        ):
            try:
                new_status = PropertyStatus(
                    str(new_status).strip().lower()
                )
            except ValueError as error:
                raise PropertyValidationError(
                    [
                        "The selected property status is invalid."
                    ]
                ) from error

        previous_status = property_record.status

        if previous_status == new_status:
            return property_record

        property_record.status = new_status

        self.create_audit_log(
            current_user=current_user,
            action="property.status_changed",
            result="success",
            property_id=property_record.id,
            details=(
                f"Property status changed from "
                f"{previous_status.value} to "
                f"{new_status.value}."
            ),
            request=request,
        )

        self.db.commit()
        self.db.refresh(property_record)

        return property_record

    def activate_property(
        self,
        current_user: User,
        property_id: str,
        request: Optional[Request] = None,
    ) -> Property:
        """Activate a property."""

        return self.change_property_status(
            current_user=current_user,
            property_id=property_id,
            new_status=PropertyStatus.ACTIVE,
            request=request,
        )

    def deactivate_property(
        self,
        current_user: User,
        property_id: str,
        request: Optional[Request] = None,
    ) -> Property:
        """
        Deactivate a property and pause its published listings.
        """

        property_record = self.get_manageable_property(
            current_user=current_user,
            property_id=property_id,
        )

        previous_status = property_record.status
        property_record.status = PropertyStatus.INACTIVE

        published_listings = list(
            self.db.scalars(
                select(Listing).where(
                    Listing.property_id == property_id,
                    Listing.status == ListingStatus.PUBLISHED,
                )
            ).all()
        )

        for listing in published_listings:
            listing.status = ListingStatus.PAUSED

        self.create_audit_log(
            current_user=current_user,
            action="property.deactivated",
            result="success",
            property_id=property_record.id,
            details=(
                f"Property status changed from "
                f"{previous_status.value} to inactive. "
                f"{len(published_listings)} listings were paused."
            ),
            request=request,
        )

        self.db.commit()
        self.db.refresh(property_record)

        return property_record

    # ----------------------------------------------------------------------
    # Manager assignment
    # ----------------------------------------------------------------------

    def assign_manager(
        self,
        current_user: User,
        property_id: str,
        manager_id: str,
        request: Optional[Request] = None,
    ) -> Property:
        """Assign an active property manager to a property."""

        property_record = self.get_owned_property(
            current_user=current_user,
            property_id=property_id,
        )

        manager = self.db.get(
            User,
            manager_id,
        )

        if manager is None:
            raise PropertyValidationError(
                [
                    "The selected property manager was not found."
                ]
            )

        if manager.status != AccountStatus.ACTIVE:
            raise PropertyValidationError(
                [
                    "The selected property manager is not active."
                ]
            )

        if manager.role != UserRole.PROPERTY_MANAGER:
            raise PropertyValidationError(
                [
                    "The selected user does not have the "
                    "property-manager role."
                ]
            )

        property_record.manager_id = manager.id

        self.create_audit_log(
            current_user=current_user,
            action="property.manager_assigned",
            result="success",
            property_id=property_record.id,
            details=(
                f"Manager user ID {manager.id} was assigned."
            ),
            request=request,
        )

        self.db.commit()
        self.db.refresh(property_record)

        return property_record

    def remove_manager(
        self,
        current_user: User,
        property_id: str,
        request: Optional[Request] = None,
    ) -> Property:
        """Remove the currently assigned property manager."""

        property_record = self.get_owned_property(
            current_user=current_user,
            property_id=property_id,
        )

        previous_manager_id = property_record.manager_id

        if previous_manager_id is None:
            return property_record

        property_record.manager_id = None

        self.create_audit_log(
            current_user=current_user,
            action="property.manager_removed",
            result="success",
            property_id=property_record.id,
            details=(
                f"Manager user ID {previous_manager_id} "
                "was removed."
            ),
            request=request,
        )

        self.db.commit()
        self.db.refresh(property_record)

        return property_record

    def list_available_managers(
        self,
    ) -> list[User]:
        """Return all active property managers."""

        query = (
            select(User)
            .where(
                User.role == UserRole.PROPERTY_MANAGER,
                User.status == AccountStatus.ACTIVE,
            )
            .order_by(User.full_name.asc())
        )

        return list(
            self.db.scalars(query).all()
        )

    # ----------------------------------------------------------------------
    # Statistics
    # ----------------------------------------------------------------------

    def get_property_statistics(
        self,
        current_user: User,
        property_id: str,
    ) -> PropertyStatistics:
        """Return unit and listing totals for a property."""

        self.get_accessible_property(
            current_user=current_user,
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

        total_listings = self.db.scalar(
            select(func.count(Listing.id)).where(
                Listing.property_id == property_id
            )
        ) or 0

        published_listings = self.db.scalar(
            select(func.count(Listing.id)).where(
                Listing.property_id == property_id,
                Listing.status == ListingStatus.PUBLISHED,
            )
        ) or 0

        return PropertyStatistics(
            total_units=int(total_units),
            vacant_units=int(vacant_units),
            occupied_units=int(occupied_units),
            maintenance_units=int(maintenance_units),
            unavailable_units=int(unavailable_units),
            total_listings=int(total_listings),
            published_listings=int(published_listings),
        )

    def get_management_summary(
        self,
        current_user: User,
    ) -> dict:
        """Return totals across all manageable properties."""

        property_query = select(Property.id)

        if current_user.role == UserRole.ADMINISTRATOR:
            pass

        elif current_user.role == UserRole.LANDLORD:
            property_query = property_query.where(
                Property.owner_id == current_user.id
            )

        elif current_user.role == UserRole.PROPERTY_MANAGER:
            property_query = property_query.where(
                Property.manager_id == current_user.id
            )

        else:
            raise PropertyPermissionError(
                "You do not have access to property statistics."
            )

        property_ids = list(
            self.db.scalars(property_query).all()
        )

        if not property_ids:
            return {
                "total_properties": 0,
                "active_properties": 0,
                "total_units": 0,
                "vacant_units": 0,
                "occupied_units": 0,
                "maintenance_units": 0,
            }

        active_properties = self.db.scalar(
            select(func.count(Property.id)).where(
                Property.id.in_(property_ids),
                Property.status == PropertyStatus.ACTIVE,
            )
        ) or 0

        total_units = self.db.scalar(
            select(func.count(Unit.id)).where(
                Unit.property_id.in_(property_ids)
            )
        ) or 0

        vacant_units = self.db.scalar(
            select(func.count(Unit.id)).where(
                Unit.property_id.in_(property_ids),
                Unit.status == UnitStatus.VACANT,
            )
        ) or 0

        occupied_units = self.db.scalar(
            select(func.count(Unit.id)).where(
                Unit.property_id.in_(property_ids),
                Unit.status == UnitStatus.OCCUPIED,
            )
        ) or 0

        maintenance_units = self.db.scalar(
            select(func.count(Unit.id)).where(
                Unit.property_id.in_(property_ids),
                Unit.status == UnitStatus.MAINTENANCE,
            )
        ) or 0

        return {
            "total_properties": len(property_ids),
            "active_properties": int(active_properties),
            "total_units": int(total_units),
            "vacant_units": int(vacant_units),
            "occupied_units": int(occupied_units),
            "maintenance_units": int(maintenance_units),
        }

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
        property_id: Optional[str] = None,
        details: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """Add a property-management audit record."""

        audit_log = AuditLog(
            user_id=current_user.id,
            action=action,
            resource_type="property",
            resource_id=property_id,
            result=result,
            details=details,
            ip_hash=self.hash_request_ip(request),
        )

        self.db.add(audit_log)

        return audit_log