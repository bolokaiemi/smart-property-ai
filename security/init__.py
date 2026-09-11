"""
Smart Property AI security package.

This package provides password security and reusable
authorization dependencies.
"""

from security.passwords import (
    PasswordValidationError,
    hash_password,
    password_needs_rehash,
    validate_password,
    verify_password,
)

from security.permissions import (
    PermissionDeniedError,
    ensure_property_access,
    get_authenticated_user,
    has_any_role,
    is_administrator,
    is_landlord_or_manager,
    require_admin,
    require_authenticated_user,
    require_landlord,
    require_landlord_or_manager,
    require_maintenance_staff,
    require_property_access,
    require_roles,
    require_tenant,
)

__all__ = [
    "PasswordValidationError",
    "hash_password",
    "verify_password",
    "validate_password",
    "password_needs_rehash",
    "PermissionDeniedError",
    "get_authenticated_user",
    "require_authenticated_user",
    "require_roles",
    "require_admin",
    "require_landlord",
    "require_landlord_or_manager",
    "require_tenant",
    "require_maintenance_staff",
    "require_property_access",
    "ensure_property_access",
    "has_any_role",
    "is_administrator",
    "is_landlord_or_manager",
]