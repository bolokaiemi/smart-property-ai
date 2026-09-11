"""
Smart Property AI authentication service.

File:
    services/auth_service.py

This service contains reusable business logic for:

- Password hashing and verification
- Registration
- Login authentication
- Session creation and removal
- Email verification
- Password-reset tokens
- Consent recording
- Authentication audit logs
"""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from email_validator import EmailNotValidError, validate_email
from fastapi import Request
from itsdangerous import (
    BadSignature,
    SignatureExpired,
    URLSafeTimedSerializer,
)
from passlib.context import CryptContext
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database.models import (
    AccountStatus,
    AuditLog,
    ConsentRecord,
    ConsentType,
    User,
    UserRole,
)


# ==========================================================================
# Authentication constants
# ==========================================================================

PASSWORD_RESET_SALT = "smart-property-password-reset"
EMAIL_VERIFICATION_SALT = "smart-property-email-verification"

PASSWORD_RESET_MAX_AGE = 60 * 60
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 24

MINIMUM_PASSWORD_LENGTH = 10
MAXIMUM_PASSWORD_LENGTH = 128

PUBLIC_REGISTRATION_ROLES = {
    UserRole.APPLICANT.value: UserRole.APPLICANT,
    UserRole.TENANT.value: UserRole.TENANT,
    UserRole.LANDLORD.value: UserRole.LANDLORD,
}


# ==========================================================================
# Exceptions
# ==========================================================================

class AuthenticationError(Exception):
    """Raised when login authentication fails."""

    pass


class DuplicateUserError(Exception):
    """Raised when a username or email already exists."""

    pass


class InvalidTokenError(Exception):
    """Raised when a signed authentication token is invalid."""

    pass


class ValidationError(Exception):
    """Raised when registration or password data is invalid."""

    def __init__(
        self,
        errors: list[str],
    ):
        self.errors = errors

        super().__init__(
            " ".join(errors)
        )


# ==========================================================================
# Registration data
# ==========================================================================

@dataclass
class RegistrationData:
    """Validated values required to create a user."""

    full_name: str
    username: str
    email: str
    password: str
    phone_number: Optional[str] = None
    role: str = UserRole.APPLICANT.value
    preferred_language: str = "en"
    privacy_accepted: bool = False
    terms_accepted: bool = False
    model_training_consent: bool = False


# ==========================================================================
# Authentication service
# ==========================================================================

class AuthService:
    """
    Authentication and account-management service.

    A SQLAlchemy session is supplied when the service is created:

        auth_service = AuthService(db)
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

        self.password_context = CryptContext(
            schemes=["pbkdf2_sha256"],
            deprecated="auto",
        )

        self.token_serializer = URLSafeTimedSerializer(
            secret_key=settings.SECRET_KEY
        )

    # ----------------------------------------------------------------------
    # Time
    # ----------------------------------------------------------------------

    @staticmethod
    def utc_now() -> datetime:
        """Return the current timezone-aware UTC datetime."""

        return datetime.now(timezone.utc)

    # ----------------------------------------------------------------------
    # Normalization
    # ----------------------------------------------------------------------

    @staticmethod
    def normalize_username(
        username: str,
    ) -> str:
        """Normalize a username before saving or searching."""

        return username.strip().lower()

    @staticmethod
    def normalize_email(
        email: str,
    ) -> str:
        """
        Validate and normalize an email address.

        Deliverability is not checked here because that can
        require a network-based DNS lookup.
        """

        try:
            validated_email = validate_email(
                email.strip(),
                check_deliverability=False,
            )
        except EmailNotValidError as error:
            raise ValidationError(
                ["Please enter a valid email address."]
            ) from error

        return validated_email.normalized.lower()

    @staticmethod
    def normalize_phone_number(
        phone_number: Optional[str],
    ) -> Optional[str]:
        """Normalize an optional telephone number."""

        if not phone_number:
            return None

        cleaned_phone = phone_number.strip()

        if not cleaned_phone:
            return None

        return cleaned_phone

    # ----------------------------------------------------------------------
    # Passwords
    # ----------------------------------------------------------------------

    def hash_password(
        self,
        password: str,
    ) -> str:
        """Create a secure PBKDF2 password hash."""

        return self.password_context.hash(
            password
        )

    def verify_password(
        self,
        password: str,
        password_hash: str,
    ) -> bool:
        """Compare a supplied password with a stored hash."""

        if not password or not password_hash:
            return False

        try:
            return self.password_context.verify(
                password,
                password_hash,
            )
        except (
            TypeError,
            ValueError,
        ):
            return False

    @staticmethod
    def validate_password(
        password: str,
    ) -> list[str]:
        """
        Validate password strength.

        Requirements:

        - 10 to 128 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        - At least one special character
        """

        errors = []

        if len(password) < MINIMUM_PASSWORD_LENGTH:
            errors.append(
                "Password must contain at least "
                f"{MINIMUM_PASSWORD_LENGTH} characters."
            )

        if len(password) > MAXIMUM_PASSWORD_LENGTH:
            errors.append(
                "Password must not exceed "
                f"{MAXIMUM_PASSWORD_LENGTH} characters."
            )

        if not any(
            character.isupper()
            for character in password
        ):
            errors.append(
                "Password must contain an uppercase letter."
            )

        if not any(
            character.islower()
            for character in password
        ):
            errors.append(
                "Password must contain a lowercase letter."
            )

        if not any(
            character.isdigit()
            for character in password
        ):
            errors.append(
                "Password must contain a number."
            )

        if not any(
            not character.isalnum()
            for character in password
        ):
            errors.append(
                "Password must contain a special character."
            )

        return errors

    @staticmethod
    def validate_username(
        username: str,
    ) -> list[str]:
        """
        Validate a normalized username.

        Allowed characters:

        - Letters
        - Numbers
        - Periods
        - Hyphens
        - Underscores
        """

        errors = []

        if len(username) < 3:
            errors.append(
                "Username must contain at least 3 characters."
            )

        if len(username) > 100:
            errors.append(
                "Username must not exceed 100 characters."
            )

        if not all(
            character.isalnum()
            or character in {
                "_",
                "-",
                ".",
            }
            for character in username
        ):
            errors.append(
                "Username may contain only letters, numbers, "
                "periods, hyphens and underscores."
            )

        return errors

    # ----------------------------------------------------------------------
    # User queries
    # ----------------------------------------------------------------------

    def get_user_by_id(
        self,
        user_id: str,
    ) -> Optional[User]:
        """Return a user by primary key."""

        return self.db.get(
            User,
            user_id,
        )

    def get_user_by_email(
        self,
        email: str,
    ) -> Optional[User]:
        """Return a user by normalized email address."""

        try:
            normalized_email = self.normalize_email(
                email
            )
        except ValidationError:
            return None

        return self.db.scalar(
            select(User).where(
                User.email == normalized_email
            )
        )

    def get_user_by_username(
        self,
        username: str,
    ) -> Optional[User]:
        """Return a user by normalized username."""

        normalized_username = self.normalize_username(
            username
        )

        return self.db.scalar(
            select(User).where(
                User.username == normalized_username
            )
        )

    def get_user_by_identifier(
        self,
        identifier: str,
    ) -> Optional[User]:
        """
        Search for a user by username or email address.
        """

        normalized_identifier = identifier.strip().lower()

        return self.db.scalar(
            select(User).where(
                or_(
                    User.username == normalized_identifier,
                    User.email == normalized_identifier,
                )
            )
        )

    def username_exists(
        self,
        username: str,
    ) -> bool:
        """Return True when a username already exists."""

        return (
            self.get_user_by_username(username)
            is not None
        )

    def email_exists(
        self,
        email: str,
    ) -> bool:
        """Return True when an email address already exists."""

        return (
            self.get_user_by_email(email)
            is not None
        )

    # ----------------------------------------------------------------------
    # Registration
    # ----------------------------------------------------------------------

    def validate_registration(
        self,
        registration: RegistrationData,
    ) -> RegistrationData:
        """
        Normalize and validate registration information.

        Returns a new normalized RegistrationData instance.
        """

        errors = []

        full_name = registration.full_name.strip()

        username = self.normalize_username(
            registration.username
        )

        phone_number = self.normalize_phone_number(
            registration.phone_number
        )

        if len(full_name) < 2:
            errors.append(
                "Please enter your full name."
            )

        if len(full_name) > 150:
            errors.append(
                "Full name must not exceed 150 characters."
            )

        errors.extend(
            self.validate_username(username)
        )

        try:
            email = self.normalize_email(
                registration.email
            )
        except ValidationError as error:
            email = registration.email.strip().lower()
            errors.extend(error.errors)

        errors.extend(
            self.validate_password(
                registration.password
            )
        )

        role = PUBLIC_REGISTRATION_ROLES.get(
            registration.role
        )

        if role is None:
            role = UserRole.APPLICANT

            errors.append(
                "The selected account type is not available "
                "for public registration."
            )

        preferred_language = (
            registration.preferred_language.strip().lower()
            or settings.DEFAULT_LANGUAGE
        )

        if not registration.privacy_accepted:
            errors.append(
                "You must acknowledge the Privacy Policy."
            )

        if not registration.terms_accepted:
            errors.append(
                "You must accept the Terms of Use."
            )

        if self.username_exists(username):
            errors.append(
                "This username is already registered."
            )

        if self.email_exists(email):
            errors.append(
                "This email address is already registered."
            )

        if errors:
            raise ValidationError(errors)

        return RegistrationData(
            full_name=full_name,
            username=username,
            email=email,
            phone_number=phone_number,
            role=role.value,
            password=registration.password,
            preferred_language=preferred_language,
            privacy_accepted=True,
            terms_accepted=True,
            model_training_consent=(
                registration.model_training_consent
            ),
        )

    def register_user(
        self,
        registration: RegistrationData,
        request: Optional[Request] = None,
    ) -> User:
        """
        Validate registration information and create a user.

        The new user and required consent records are committed
        in one transaction.
        """

        validated_data = self.validate_registration(
            registration
        )

        selected_role = PUBLIC_REGISTRATION_ROLES[
            validated_data.role
        ]

        user = User(
            full_name=validated_data.full_name,
            username=validated_data.username,
            email=validated_data.email,
            phone_number=validated_data.phone_number,
            password_hash=self.hash_password(
                validated_data.password
            ),
            role=selected_role,
            status=AccountStatus.ACTIVE,
            preferred_language=(
                validated_data.preferred_language
            ),
            email_verified=False,
            phone_verified=False,
        )

        try:
            self.db.add(user)
            self.db.flush()

            self.record_consent(
                user_id=user.id,
                consent_type=ConsentType.PRIVACY_POLICY,
                granted=True,
                policy_version="2026-09",
            )

            self.record_consent(
                user_id=user.id,
                consent_type=ConsentType.TERMS,
                granted=True,
                policy_version="2026-09",
            )

            self.record_consent(
                user_id=user.id,
                consent_type=ConsentType.MODEL_TRAINING,
                granted=(
                    validated_data.model_training_consent
                ),
                policy_version="2026-09",
            )

            self.create_audit_log(
                action="authentication.registration",
                result="success",
                user_id=user.id,
                resource_type="user",
                resource_id=user.id,
                details=(
                    "Registered public account with role: "
                    f"{selected_role.value}."
                ),
                request=request,
            )

            self.db.commit()
            self.db.refresh(user)

            return user

        except IntegrityError as error:
            self.db.rollback()

            raise DuplicateUserError(
                "An account with this username or email "
                "address already exists."
            ) from error

        except Exception:
            self.db.rollback()
            raise

    # ----------------------------------------------------------------------
    # Login authentication
    # ----------------------------------------------------------------------

    def authenticate_user(
        self,
        identifier: str,
        password: str,
        request: Optional[Request] = None,
    ) -> User:
        """
        Authenticate a user by username or email address.

        Raises AuthenticationError if authentication fails.
        """

        user = self.get_user_by_identifier(
            identifier
        )

        if (
            user is None
            or not self.verify_password(
                password,
                user.password_hash,
            )
        ):
            self.create_audit_log(
                action="authentication.login",
                result="failed",
                user_id=user.id if user else None,
                resource_type="user",
                resource_id=user.id if user else None,
                details="Invalid login credentials.",
                request=request,
            )

            self.db.commit()

            raise AuthenticationError(
                "The username, email address or password "
                "is incorrect."
            )

        if user.status != AccountStatus.ACTIVE:
            self.create_audit_log(
                action="authentication.login",
                result="blocked",
                user_id=user.id,
                resource_type="user",
                resource_id=user.id,
                details=(
                    "Login blocked because the account "
                    "is not active."
                ),
                request=request,
            )

            self.db.commit()

            raise AuthenticationError(
                "This account is not currently active."
            )

        user.last_login_at = self.utc_now()

        self.create_audit_log(
            action="authentication.login",
            result="success",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            request=request,
        )

        self.db.commit()
        self.db.refresh(user)

        return user

    # ----------------------------------------------------------------------
    # Sessions
    # ----------------------------------------------------------------------

    @staticmethod
    def create_login_session(
        request: Request,
        user: User,
        remember_me: bool = False,
    ) -> None:
        """Store safe user information in the signed session."""

        request.session.clear()

        request.session.update(
            {
                "user_id": user.id,
                "username": user.username,
                "name": user.full_name,
                "email": user.email,
                "role": user.role.value,
                "language": user.preferred_language,
                "remember_me": remember_me,
                "authenticated_at": (
                    AuthService.utc_now().isoformat()
                ),
            }
        )

    def clear_login_session(
        self,
        request: Request,
    ) -> None:
        """
        Record logout and clear the user's session.

        The preferred language is preserved.
        """

        user_id = request.session.get("user_id")

        language = request.session.get(
            "language",
            settings.DEFAULT_LANGUAGE,
        )

        if user_id:
            self.create_audit_log(
                action="authentication.logout",
                result="success",
                user_id=user_id,
                resource_type="user",
                resource_id=user_id,
                request=request,
            )

            self.db.commit()

        request.session.clear()
        request.session["language"] = language

    @staticmethod
    def is_authenticated(
        request: Request,
    ) -> bool:
        """Return True if the session contains an authenticated user."""

        return bool(
            request.session.get("user_id")
        )

    @staticmethod
    def current_user_id(
        request: Request,
    ) -> Optional[str]:
        """Return the authenticated user's ID."""

        return request.session.get("user_id")

    def get_current_user(
        self,
        request: Request,
    ) -> Optional[User]:
        """Return the authenticated user from the database."""

        user_id = self.current_user_id(
            request
        )

        if not user_id:
            return None

        user = self.get_user_by_id(
            user_id
        )

        if (
            user is None
            or user.status != AccountStatus.ACTIVE
        ):
            request.session.clear()
            return None

        return user

    # ----------------------------------------------------------------------
    # Role-based destinations
    # ----------------------------------------------------------------------

    @staticmethod
    def dashboard_for_role(
        role: UserRole,
    ) -> str:
        """Return the default page for a user role."""

        if role in {
            UserRole.LANDLORD,
            UserRole.PROPERTY_MANAGER,
        }:
            return "/landlord/dashboard"

        if role == UserRole.TENANT:
            return "/tenant/dashboard"

        if role == UserRole.ADMINISTRATOR:
            return "/admin/dashboard"

        if role == UserRole.MAINTENANCE_STAFF:
            return "/maintenance/dashboard"

        return "/listings"

    # ----------------------------------------------------------------------
    # Password-reset tokens
    # ----------------------------------------------------------------------

    def create_password_reset_token(
        self,
        user: User,
    ) -> str:
        """
        Create a signed one-hour password-reset token.

        The current password hash is included so the token
        automatically becomes invalid after a password change.
        """

        return self.token_serializer.dumps(
            {
                "purpose": "password_reset",
                "user_id": user.id,
                "email": user.email,
                "password_hash": user.password_hash,
            },
            salt=PASSWORD_RESET_SALT,
        )

    def decode_password_reset_token(
        self,
        token: str,
    ) -> dict:
        """
        Decode a password-reset token.

        Raises InvalidTokenError for an invalid or expired token.
        """

        try:
            payload = self.token_serializer.loads(
                token,
                salt=PASSWORD_RESET_SALT,
                max_age=PASSWORD_RESET_MAX_AGE,
            )
        except SignatureExpired as error:
            raise InvalidTokenError(
                "This password-reset link has expired."
            ) from error
        except BadSignature as error:
            raise InvalidTokenError(
                "This password-reset link is invalid."
            ) from error

        if payload.get("purpose") != "password_reset":
            raise InvalidTokenError(
                "This token cannot be used to reset a password."
            )

        return payload

    def get_user_from_password_reset_token(
        self,
        token: str,
    ) -> User:
        """
        Validate a reset token and return its user.
        """

        payload = self.decode_password_reset_token(
            token
        )

        user = self.get_user_by_id(
            payload.get("user_id", "")
        )

        if user is None:
            raise InvalidTokenError(
                "The account connected to this link no longer exists."
            )

        if user.email != payload.get("email"):
            raise InvalidTokenError(
                "This password-reset link is invalid."
            )

        if user.password_hash != payload.get("password_hash"):
            raise InvalidTokenError(
                "This password-reset link has already been used."
            )

        if user.status != AccountStatus.ACTIVE:
            raise InvalidTokenError(
                "This account is not active."
            )

        return user

    def reset_password(
        self,
        token: str,
        new_password: str,
        confirm_password: str,
        request: Optional[Request] = None,
    ) -> User:
        """Validate a token and save a new password."""

        errors = self.validate_password(
            new_password
        )

        if new_password != confirm_password:
            errors.append(
                "The password confirmation does not match."
            )

        if errors:
            raise ValidationError(errors)

        user = self.get_user_from_password_reset_token(
            token
        )

        user.password_hash = self.hash_password(
            new_password
        )

        self.create_audit_log(
            action="authentication.password_reset_completed",
            result="success",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            request=request,
        )

        self.db.commit()
        self.db.refresh(user)

        return user

    def request_password_reset(
        self,
        identifier: str,
        request: Optional[Request] = None,
    ) -> Optional[tuple[User, str]]:
        """
        Generate a password-reset token for an active user.

        Returns None when there is no matching active account.
        Route responses must not reveal whether the account exists.
        """

        user = self.get_user_by_identifier(
            identifier
        )

        if (
            user is None
            or user.status != AccountStatus.ACTIVE
        ):
            return None

        token = self.create_password_reset_token(
            user
        )

        self.create_audit_log(
            action="authentication.password_reset_requested",
            result="success",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            request=request,
        )

        self.db.commit()

        return user, token

    # ----------------------------------------------------------------------
    # Email verification
    # ----------------------------------------------------------------------

    def create_email_verification_token(
        self,
        user: User,
    ) -> str:
        """Create a signed email-verification token."""

        return self.token_serializer.dumps(
            {
                "purpose": "email_verification",
                "user_id": user.id,
                "email": user.email,
            },
            salt=EMAIL_VERIFICATION_SALT,
        )

    def decode_email_verification_token(
        self,
        token: str,
    ) -> dict:
        """Decode and validate an email-verification token."""

        try:
            payload = self.token_serializer.loads(
                token,
                salt=EMAIL_VERIFICATION_SALT,
                max_age=EMAIL_VERIFICATION_MAX_AGE,
            )
        except SignatureExpired as error:
            raise InvalidTokenError(
                "This email-verification link has expired."
            ) from error
        except BadSignature as error:
            raise InvalidTokenError(
                "This email-verification link is invalid."
            ) from error

        if payload.get("purpose") != "email_verification":
            raise InvalidTokenError(
                "This token cannot verify an email address."
            )

        return payload

    def verify_email(
        self,
        token: str,
        request: Optional[Request] = None,
    ) -> User:
        """Verify the email address connected to a signed token."""

        payload = self.decode_email_verification_token(
            token
        )

        user = self.get_user_by_id(
            payload.get("user_id", "")
        )

        if (
            user is None
            or user.email != payload.get("email")
        ):
            raise InvalidTokenError(
                "This email-verification link does not "
                "match an account."
            )

        if not user.email_verified:
            user.email_verified = True

            self.create_audit_log(
                action="authentication.email_verified",
                result="success",
                user_id=user.id,
                resource_type="user",
                resource_id=user.id,
                request=request,
            )

            self.db.commit()
            self.db.refresh(user)

        return user

    # ----------------------------------------------------------------------
    # Password changes for authenticated users
    # ----------------------------------------------------------------------

    def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
        confirm_password: str,
        request: Optional[Request] = None,
    ) -> None:
        """Change the password of an authenticated user."""

        errors = []

        if not self.verify_password(
            current_password,
            user.password_hash,
        ):
            errors.append(
                "The current password is incorrect."
            )

        errors.extend(
            self.validate_password(
                new_password
            )
        )

        if new_password != confirm_password:
            errors.append(
                "The new-password confirmation does not match."
            )

        if current_password == new_password:
            errors.append(
                "The new password must be different from "
                "the current password."
            )

        if errors:
            raise ValidationError(errors)

        user.password_hash = self.hash_password(
            new_password
        )

        self.create_audit_log(
            action="authentication.password_changed",
            result="success",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            request=request,
        )

        self.db.commit()

    # ----------------------------------------------------------------------
    # Consent
    # ----------------------------------------------------------------------

    def record_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        granted: bool,
        policy_version: str,
        request: Optional[Request] = None,
    ) -> ConsentRecord:
        """Create a consent record."""

        consent = ConsentRecord(
            user_id=user_id,
            consent_type=consent_type,
            granted=granted,
            policy_version=policy_version,
            ip_hash=self.hash_request_ip(request),
            withdrawn_at=(
                None
                if granted
                else self.utc_now()
            ),
        )

        self.db.add(consent)

        return consent

    # ----------------------------------------------------------------------
    # Audit logging
    # ----------------------------------------------------------------------

    @staticmethod
    def hash_request_ip(
        request: Optional[Request],
    ) -> Optional[str]:
        """
        Create a keyed hash of the request IP address.

        The raw address is not stored in the audit record.
        """

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
        action: str,
        result: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Add an authentication audit record.

        Do not pass passwords, tokens or private message
        content through the details argument.
        """

        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            details=details,
            ip_hash=self.hash_request_ip(request),
        )

        self.db.add(audit_log)

        return audit_log