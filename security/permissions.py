"""
Authentication and authorization helpers.

File:
    security/permissions.py
"""

from collections.abc import Callable
from typing import Annotated, Optional

from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import (
    AccountStatus,
    Lease,
    LeaseStatus,
    MaintenanceRequest,
    Property,
    User,
    UserRole,
)


DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]


class PermissionDeniedError(Exception):
    """Internal permission-check failure."""

    pass


# ==========================================================================
# Authentication helpers
# ==========================================================================

def clear_invalid_session(
    request: Request,
) -> None:
    """
    Clear an invalid session while preserving the selected language.
    """

    language = request.session.get(
        "language",
        "en",
    )

    request.session.clear()
    request.session["language"] = language


def get_authenticated_user(
    request: Request,
    db: Session,
) -> Optional[User]:
    """
    Return the current active user.

    Returns None when the user is not authenticated or the
    session no longer matches an active database account.
    """

    user_id = request.session.get(
        "user_id"
    )

    if not user_id:
        return None

    user = db.get(
        User,
        user_id,
    )

    if (
        user is None
        or user.status != AccountStatus.ACTIVE
    ):
        clear_invalid_session(request)
        return None

    session_username = request.session.get(
        "username"
    )

    if (
        session_username
        and session_username != user.username
    ):
        clear_invalid_session(request)
        return None

    return user


def require_authenticated_user(
    request: Request,
    db: DatabaseSession,
) -> User:
    """
    FastAPI dependency requiring an authenticated active user.

    Usage:

        @router.get("/dashboard")
        async def dashboard(
            current_user: User = Depends(
                require_authenticated_user
            ),
        ):
            ...
    """

    user = get_authenticated_user(
        request=request,
        db=db,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={
                "WWW-Authenticate": "Session",
            },
        )

    return user


CurrentUser = Annotated[
    User,
    Depends(require_authenticated_user),
]


# ==========================================================================
# Role checks
# ==========================================================================

def has_any_role(
    user: User,
    *allowed_roles: UserRole,
) -> bool:
    """Return True if the user has an allowed role."""

    return user.role in set(allowed_roles)


def is_administrator(
    user: User,
) -> bool:
    """Return True if the user is an administrator."""

    return user.role == UserRole.ADMINISTRATOR


def is_landlord_or_manager(
    user: User,
) -> bool:
    """Return True for landlords and property managers."""

    return user.role in {
        UserRole.LANDLORD,
        UserRole.PROPERTY_MANAGER,
    }


def require_roles(
    *allowed_roles: UserRole,
) -> Callable:
    """
    Create a FastAPI dependency requiring one of the
    specified roles.

    Example:

        landlord_or_manager = require_roles(
            UserRole.LANDLORD,
            UserRole.PROPERTY_MANAGER,
        )

        @router.get("/landlord/dashboard")
        async def dashboard(
            user: User = Depends(landlord_or_manager),
        ):
            ...
    """

    allowed_role_set = set(
        allowed_roles
    )

    def role_dependency(
        current_user: CurrentUser,
    ) -> User:
        if current_user.role not in allowed_role_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You do not have permission "
                    "to access this resource."
                ),
            )

        return current_user

    return role_dependency


require_admin = require_roles(
    UserRole.ADMINISTRATOR,
)

require_landlord = require_roles(
    UserRole.LANDLORD,
)

require_landlord_or_manager = require_roles(
    UserRole.LANDLORD,
    UserRole.PROPERTY_MANAGER,
    UserRole.ADMINISTRATOR,
)

require_tenant = require_roles(
    UserRole.TENANT,
)

require_maintenance_staff = require_roles(
    UserRole.MAINTENANCE_STAFF,
    UserRole.PROPERTY_MANAGER,
    UserRole.LANDLORD,
    UserRole.ADMINISTRATOR,
)


AdministratorUser = Annotated[
    User,
    Depends(require_admin),
]

LandlordUser = Annotated[
    User,
    Depends(require_landlord),
]

LandlordOrManagerUser = Annotated[
    User,
    Depends(require_landlord_or_manager),
]

TenantUser = Annotated[
    User,
    Depends(require_tenant),
]

MaintenanceUser = Annotated[
    User,
    Depends(require_maintenance_staff),
]


# ==========================================================================
# Property access
# ==========================================================================

def user_has_property_access(
    db: Session,
    user: User,
    property_id: str,
) -> bool:
    """
    Determine whether a user can access a property.

    Access rules:

    - Administrators can access all properties.
    - A landlord can access properties they own.
    - A property manager can access assigned properties.
    - A tenant can access a property connected to an active
      or expiring lease.
    - Maintenance staff can access a property only when
      assigned to a maintenance request for that property.
    """

    if user.role == UserRole.ADMINISTRATOR:
        return True

    if user.role in {
        UserRole.LANDLORD,
        UserRole.PROPERTY_MANAGER,
    }:
        property_record = db.scalar(
            select(Property).where(
                and_(
                    Property.id == property_id,
                    or_(
                        Property.owner_id == user.id,
                        Property.manager_id == user.id,
                    ),
                )
            )
        )

        return property_record is not None

    if user.role == UserRole.TENANT:
        tenant_lease = db.scalar(
            select(Lease.id).where(
                and_(
                    Lease.property_id == property_id,
                    Lease.tenant_id == user.id,
                    Lease.status.in_(
                        [
                            LeaseStatus.ACTIVE,
                            LeaseStatus.EXPIRING,
                        ]
                    ),
                )
            )
        )

        return tenant_lease is not None

    if user.role == UserRole.MAINTENANCE_STAFF:
        assigned_request = db.scalar(
            select(
                MaintenanceRequest.id
            ).where(
                and_(
                    MaintenanceRequest.property_id
                    == property_id,
                    MaintenanceRequest.assigned_to_id
                    == user.id,
                    MaintenanceRequest.status.in_(
                        [
                            "open",
                            "acknowledged",
                            "in_progress",
                            "waiting",
                        ]
                    ),
                )
            )
        )

        return assigned_request is not None

    return False


def ensure_property_access(
    db: Session,
    user: User,
    property_id: str,
) -> None:
    """
    Raise HTTP 403 if the user cannot access a property.
    """

    property_exists = db.scalar(
        select(Property.id).where(
            Property.id == property_id
        )
    )

    if property_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested property was not found.",
        )

    if not user_has_property_access(
        db=db,
        user=user,
        property_id=property_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have permission to access "
                "this property."
            ),
        )


def require_property_access(
    property_id: str,
    request: Request,
    db: DatabaseSession,
) -> User:
    """
    FastAPI dependency requiring access to a property.

    FastAPI obtains property_id from the route path.

    Example:

        @router.get(
            "/properties/{property_id}"
        )
        async def property_details(
            property_id: str,
            user: User = Depends(
                require_property_access
            ),
        ):
            ...
    """

    user = require_authenticated_user(
        request=request,
        db=db,
    )

    ensure_property_access(
        db=db,
        user=user,
        property_id=property_id,
    )

    return user


PropertyAuthorizedUser = Annotated[
    User,
    Depends(require_property_access),
]


# ==========================================================================
# Ownership helpers
# ==========================================================================

def ensure_landlord_owns_property(
    db: Session,
    user: User,
    property_id: str,
) -> Property:
    """
    Return a property when the user owns it.

    Administrators are permitted to access any property.
    Property managers are not treated as owners by this check.
    """

    property_record = db.get(
        Property,
        property_id,
    )

    if property_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested property was not found.",
        )

    if user.role == UserRole.ADMINISTRATOR:
        return property_record

    if (
        user.role != UserRole.LANDLORD
        or property_record.owner_id != user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only the property owner can perform "
                "this action."
            ),
        )

    return property_record


def ensure_property_can_be_managed(
    db: Session,
    user: User,
    property_id: str,
) -> Property:
    """
    Return a property when the user is its owner, assigned
    manager or an administrator.
    """

    property_record = db.get(
        Property,
        property_id,
    )

    if property_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested property was not found.",
        )

    if user.role == UserRole.ADMINISTRATOR:
        return property_record

    has_management_access = (
        (
            user.role == UserRole.LANDLORD
            and property_record.owner_id == user.id
        )
        or
        (
            user.role == UserRole.PROPERTY_MANAGER
            and property_record.manager_id == user.id
        )
    )

    if not has_management_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not authorized to manage "
                "this property."
            ),
        )

    return property_record


# ==========================================================================
# Maintenance-request permissions
# ==========================================================================

def ensure_maintenance_request_access(
    db: Session,
    user: User,
    maintenance_request_id: str,
) -> MaintenanceRequest:
    """
    Check access to a maintenance request.

    Access is available to:

    - Administrators
    - The person who submitted the request
    - Assigned maintenance staff
    - The property owner
    - The assigned property manager
    """

    maintenance_request = db.get(
        MaintenanceRequest,
        maintenance_request_id,
    )

    if maintenance_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "The requested maintenance record "
                "was not found."
            ),
        )

    if user.role == UserRole.ADMINISTRATOR:
        return maintenance_request

    if maintenance_request.submitted_by_id == user.id:
        return maintenance_request

    if maintenance_request.assigned_to_id == user.id:
        return maintenance_request

    property_record = db.get(
        Property,
        maintenance_request.property_id,
    )

    if property_record and (
        property_record.owner_id == user.id
        or property_record.manager_id == user.id
    ):
        return maintenance_request

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "You do not have permission to access "
            "this maintenance request."
        ),
    )


# ==========================================================================
# Document permissions
# ==========================================================================

def can_access_property_document(
    db: Session,
    user: User,
    property_id: Optional[str],
    uploaded_by_id: str,
) -> bool:
    """
    Perform a basic document access check.

    More specific lease and document-recipient checks can be
    added in document_service.py.
    """

    if user.role == UserRole.ADMINISTRATOR:
        return True

    if uploaded_by_id == user.id:
        return True

    if not property_id:
        return False

    return user_has_property_access(
        db=db,
        user=user,
        property_id=property_id,
    )