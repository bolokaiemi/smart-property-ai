"""
Smart Property AI authentication routes.

File:
    routes/auth_routes.py
"""

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
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
from database.database import get_db
from database.models import (
    AccountStatus,
    AuditLog,
    ConsentRecord,
    ConsentType,
    User,
    UserRole,
)


router = APIRouter(
    tags=["Authentication"],
)

templates = Jinja2Templates(
    directory=str(settings.TEMPLATES_DIR)
)


# PBKDF2 avoids storing readable passwords and does not depend
# on the system bcrypt library.
password_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


token_serializer = URLSafeTimedSerializer(
    secret_key=settings.SECRET_KEY
)


PASSWORD_RESET_SALT = "smart-property-password-reset"
EMAIL_VERIFICATION_SALT = "smart-property-email-verification"

PASSWORD_RESET_MAX_AGE = 60 * 60
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 24

PUBLIC_REGISTRATION_ROLES = {
    UserRole.APPLICANT.value: UserRole.APPLICANT,
    UserRole.TENANT.value: UserRole.TENANT,
    UserRole.LANDLORD.value: UserRole.LANDLORD,
}


# ==========================================================================
# General helper functions
# ==========================================================================

def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(timezone.utc)


def template_context(
    request: Request,
    **extra_context,
) -> dict:
    """Create context shared by authentication templates."""

    context = {
        "request": request,
        "current_year": utc_now().year,
        "current_language": request.session.get(
            "language",
            settings.DEFAULT_LANGUAGE,
        ),
    }

    context.update(extra_context)

    return context


def normalize_email(email: str) -> str:
    """Validate and normalize an email address."""

    validated = validate_email(
        email.strip(),
        check_deliverability=False,
    )

    return validated.normalized.lower()


def normalize_username(username: str) -> str:
    """Normalize a username for storage and comparison."""

    return username.strip().lower()


def hash_password(password: str) -> str:
    """Create a secure PBKDF2 password hash."""

    return password_context.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """Check a password against its saved hash."""

    try:
        return password_context.verify(
            password,
            password_hash,
        )
    except (ValueError, TypeError):
        return False


def validate_password(password: str) -> list[str]:
    """
    Validate password strength.

    Passwords must:
    - contain at least 10 characters;
    - contain an uppercase letter;
    - contain a lowercase letter;
    - contain a number;
    - contain a special character.
    """

    errors = []

    if len(password) < 10:
        errors.append(
            "Password must contain at least 10 characters."
        )

    if len(password) > 128:
        errors.append(
            "Password must not exceed 128 characters."
        )

    if not any(character.isupper() for character in password):
        errors.append(
            "Password must contain an uppercase letter."
        )

    if not any(character.islower() for character in password):
        errors.append(
            "Password must contain a lowercase letter."
        )

    if not any(character.isdigit() for character in password):
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


def validate_username(username: str) -> list[str]:
    """Validate the username."""

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
        character.isalnum() or character in {"_", "-", "."}
        for character in username
    ):
        errors.append(
            "Username may contain only letters, numbers, "
            "periods, hyphens and underscores."
        )

    return errors


def safe_next_url(
    next_url: Optional[str],
    fallback: str = "/",
) -> str:
    """
    Allow redirects only to local paths.

    This prevents malicious external redirects.
    """

    if not next_url:
        return fallback

    parsed_url = urlparse(next_url)

    if parsed_url.scheme or parsed_url.netloc:
        return fallback

    if not next_url.startswith("/"):
        return fallback

    if next_url.startswith("//"):
        return fallback

    return next_url


def dashboard_for_role(role: UserRole) -> str:
    """Return the appropriate dashboard URL for a role."""

    if role in {
        UserRole.LANDLORD,
        UserRole.PROPERTY_MANAGER,
    }:
        return "/landlord/dashboard"

    if role == UserRole.TENANT:
        return "/tenant/dashboard"

    if role == UserRole.ADMINISTRATOR:
        return "/admin/dashboard"

    return "/listings"


def add_audit_log(
    db: Session,
    request: Request,
    action: str,
    result: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[str] = None,
) -> None:
    """
    Add an audit event.

    Passwords, tokens and private message content must never
    be included in details.
    """

    forwarded_for = request.headers.get(
        "x-forwarded-for",
        "",
    )

    client_address = (
        forwarded_for.split(",")[0].strip()
        if forwarded_for
        else (
            request.client.host
            if request.client
            else ""
        )
    )

    # A production application should use an HMAC hash with
    # a dedicated secret rather than saving a raw IP address.
    ip_hash = None

    if client_address:
        import hashlib
        import hmac

        ip_hash = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            client_address.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        details=details,
        ip_hash=ip_hash,
    )

    db.add(audit_log)


def create_password_reset_token(
    user: User,
) -> str:
    """
    Create a signed password-reset token.

    Including the current password hash makes the token invalid
    immediately after the password is changed.
    """

    return token_serializer.dumps(
        {
            "purpose": "password_reset",
            "user_id": user.id,
            "email": user.email,
            "password_hash": user.password_hash,
        },
        salt=PASSWORD_RESET_SALT,
    )


def read_password_reset_token(
    token: str,
) -> Optional[dict]:
    """Validate and decode a password-reset token."""

    try:
        payload = token_serializer.loads(
            token,
            salt=PASSWORD_RESET_SALT,
            max_age=PASSWORD_RESET_MAX_AGE,
        )
    except (
        SignatureExpired,
        BadSignature,
    ):
        return None

    if payload.get("purpose") != "password_reset":
        return None

    return payload


def create_email_verification_token(
    user: User,
) -> str:
    """Create a signed email-verification token."""

    return token_serializer.dumps(
        {
            "purpose": "email_verification",
            "user_id": user.id,
            "email": user.email,
        },
        salt=EMAIL_VERIFICATION_SALT,
    )


def read_email_verification_token(
    token: str,
) -> Optional[dict]:
    """Validate and decode an email-verification token."""

    try:
        payload = token_serializer.loads(
            token,
            salt=EMAIL_VERIFICATION_SALT,
            max_age=EMAIL_VERIFICATION_MAX_AGE,
        )
    except (
        SignatureExpired,
        BadSignature,
    ):
        return None

    if payload.get("purpose") != "email_verification":
        return None

    return payload


# ==========================================================================
# Login
# ==========================================================================

@router.get(
    "/login",
    name="login",
)
async def login(
    request: Request,
    next: Optional[str] = None,
):
    """Display the login page."""

    if request.session.get("user_id"):
        return RedirectResponse(
            url=dashboard_for_role(
                UserRole(
                    request.session.get(
                        "role",
                        UserRole.APPLICANT.value,
                    )
                )
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context=template_context(
            request,
            next_url=safe_next_url(next),
            form_data={},
        ),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/login",
    name="login_submit",
)
async def login_submit(
    request: Request,
    username_or_email: str = Form(...),
    password: str = Form(...),
    remember_me: Optional[str] = Form(default=None),
    next_url: Optional[str] = Form(default="/"),
    db: Session = Depends(get_db),
):
    """Authenticate a user and establish the session."""

    identifier = username_or_email.strip().lower()
    safe_redirect = safe_next_url(next_url)

    user = db.scalar(
        select(User).where(
            or_(
                User.username == identifier,
                User.email == identifier,
            )
        )
    )

    if (
        user is None
        or not verify_password(
            password,
            user.password_hash,
        )
    ):
        add_audit_log(
            db=db,
            request=request,
            action="authentication.login",
            result="failed",
            user_id=user.id if user else None,
            resource_type="user",
            resource_id=user.id if user else None,
            details="Invalid login credentials.",
        )

        db.commit()

        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context=template_context(
                request,
                error=(
                    "The username, email address or password "
                    "is incorrect."
                ),
                next_url=safe_redirect,
                form_data={
                    "username_or_email": identifier,
                    "remember_me": bool(remember_me),
                },
            ),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if user.status != AccountStatus.ACTIVE:
        add_audit_log(
            db=db,
            request=request,
            action="authentication.login",
            result="blocked",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            details=(
                "Login blocked because the account "
                "is not active."
            ),
        )

        db.commit()

        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context=template_context(
                request,
                error=(
                    "This account is not currently active. "
                    "Please contact support."
                ),
                next_url=safe_redirect,
                form_data={
                    "username_or_email": identifier,
                },
            ),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    request.session.clear()

    request.session.update(
        {
            "user_id": user.id,
            "username": user.username,
            "name": user.full_name,
            "email": user.email,
            "role": user.role.value,
            "language": user.preferred_language,
            "remember_me": bool(remember_me),
            "authenticated_at": utc_now().isoformat(),
        }
    )

    user.last_login_at = utc_now()

    add_audit_log(
        db=db,
        request=request,
        action="authentication.login",
        result="success",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
    )

    db.commit()

    if safe_redirect == "/":
        safe_redirect = dashboard_for_role(
            user.role
        )

    return RedirectResponse(
        url=safe_redirect,
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================================================
# Registration
# ==========================================================================

@router.get(
    "/register",
    name="register",
)
async def register(
    request: Request,
):
    """Display the registration form."""

    if request.session.get("user_id"):
        role = UserRole(
            request.session.get(
                "role",
                UserRole.APPLICANT.value,
            )
        )

        return RedirectResponse(
            url=dashboard_for_role(role),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context=template_context(
            request,
            public_roles=PUBLIC_REGISTRATION_ROLES,
            form_data={},
        ),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/register",
    name="register_submit",
)
async def register_submit(
    request: Request,
    full_name: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    phone_number: Optional[str] = Form(default=None),
    role: str = Form(default=UserRole.APPLICANT.value),
    password: str = Form(...),
    confirm_password: str = Form(...),
    accept_privacy: Optional[str] = Form(default=None),
    accept_terms: Optional[str] = Form(default=None),
    model_training_consent: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    """Create a new user account."""

    cleaned_full_name = full_name.strip()
    cleaned_username = normalize_username(
        username
    )

    cleaned_phone = (
        phone_number.strip()
        if phone_number
        else None
    )

    errors = []

    if len(cleaned_full_name) < 2:
        errors.append(
            "Please enter your full name."
        )

    if len(cleaned_full_name) > 150:
        errors.append(
            "Full name must not exceed 150 characters."
        )

    errors.extend(
        validate_username(cleaned_username)
    )

    try:
        cleaned_email = normalize_email(email)
    except EmailNotValidError:
        cleaned_email = email.strip().lower()
        errors.append(
            "Please enter a valid email address."
        )

    if password != confirm_password:
        errors.append(
            "The password confirmation does not match."
        )

    errors.extend(
        validate_password(password)
    )

    selected_role = PUBLIC_REGISTRATION_ROLES.get(
        role
    )

    if selected_role is None:
        selected_role = UserRole.APPLICANT
        errors.append(
            "The selected account type is not available."
        )

    if not accept_privacy:
        errors.append(
            "You must acknowledge the Privacy Policy."
        )

    if not accept_terms:
        errors.append(
            "You must accept the Terms of Use."
        )

    existing_user = db.scalar(
        select(User).where(
            or_(
                User.username == cleaned_username,
                User.email == cleaned_email,
            )
        )
    )

    if existing_user:
        if existing_user.username == cleaned_username:
            errors.append(
                "This username is already registered."
            )

        if existing_user.email == cleaned_email:
            errors.append(
                "This email address is already registered."
            )

    form_data = {
        "full_name": cleaned_full_name,
        "username": cleaned_username,
        "email": cleaned_email,
        "phone_number": cleaned_phone or "",
        "role": selected_role.value,
        "accept_privacy": bool(accept_privacy),
        "accept_terms": bool(accept_terms),
        "model_training_consent": bool(
            model_training_consent
        ),
    }

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context=template_context(
                request,
                errors=errors,
                public_roles=PUBLIC_REGISTRATION_ROLES,
                form_data=form_data,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    user = User(
        full_name=cleaned_full_name,
        username=cleaned_username,
        email=cleaned_email,
        phone_number=cleaned_phone,
        password_hash=hash_password(password),
        role=selected_role,
        status=AccountStatus.ACTIVE,
        preferred_language=request.session.get(
            "language",
            settings.DEFAULT_LANGUAGE,
        ),
        email_verified=False,
        phone_verified=False,
    )

    try:
        db.add(user)
        db.flush()

        privacy_consent = ConsentRecord(
            user_id=user.id,
            consent_type=ConsentType.PRIVACY_POLICY,
            granted=True,
            policy_version="2026-09",
        )

        terms_consent = ConsentRecord(
            user_id=user.id,
            consent_type=ConsentType.TERMS,
            granted=True,
            policy_version="2026-09",
        )

        training_consent = ConsentRecord(
            user_id=user.id,
            consent_type=ConsentType.MODEL_TRAINING,
            granted=bool(model_training_consent),
            policy_version="2026-09",
        )

        db.add_all(
            [
                privacy_consent,
                terms_consent,
                training_consent,
            ]
        )

        add_audit_log(
            db=db,
            request=request,
            action="authentication.registration",
            result="success",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            details=(
                f"Registered public account role: "
                f"{selected_role.value}."
            ),
        )

        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()

        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context=template_context(
                request,
                errors=[
                    (
                        "An account with this username or email "
                        "address already exists."
                    )
                ],
                public_roles=PUBLIC_REGISTRATION_ROLES,
                form_data=form_data,
            ),
            status_code=status.HTTP_409_CONFLICT,
        )

    verification_token = create_email_verification_token(
        user
    )

    verification_link = str(
        request.url_for(
            "verify_email",
            token=verification_token,
        )
    )

    # During development, the link is rendered on the page.
    # In production, send it through the email service.
    return templates.TemplateResponse(
        request=request,
        name="auth/verify_email.html",
        context=template_context(
            request,
            success=(
                "Your account has been created. "
                "Please verify your email address."
            ),
            email=user.email,
            verification_link=(
                verification_link
                if settings.DEBUG
                else None
            ),
        ),
        status_code=status.HTTP_201_CREATED,
    )


# ==========================================================================
# Logout
# ==========================================================================

@router.post(
    "/logout",
    name="logout",
)
async def logout(
    request: Request,
    db: Session = Depends(get_db),
):
    """Record the logout event and clear the session."""

    user_id = request.session.get("user_id")

    if user_id:
        add_audit_log(
            db=db,
            request=request,
            action="authentication.logout",
            result="success",
            user_id=user_id,
            resource_type="user",
            resource_id=user_id,
        )

        db.commit()

    language = request.session.get(
        "language",
        settings.DEFAULT_LANGUAGE,
    )

    request.session.clear()

    # Preserve only the language preference.
    request.session["language"] = language

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================================================
# Forgot password
# ==========================================================================

@router.get(
    "/forgot-password",
    name="forgot_password_page",
)
async def forgot_password_page(
    request: Request,
):
    """Display the forgot-password form."""

    return templates.TemplateResponse(
        request=request,
        name="auth/forgot_password.html",
        context=template_context(
            request,
            form_data={},
        ),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/forgot-password",
    name="forgot_password_submit",
)
async def forgot_password_submit(
    request: Request,
    username_or_email: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Generate a password-reset link.

    The response does not reveal whether an account exists.
    """

    identifier = username_or_email.strip().lower()

    user = db.scalar(
        select(User).where(
            or_(
                User.username == identifier,
                User.email == identifier,
            )
        )
    )

    reset_link = None

    if user and user.status == AccountStatus.ACTIVE:
        reset_token = create_password_reset_token(
            user
        )

        generated_link = str(
            request.url_for(
                "reset_password_page",
                token=reset_token,
            )
        )

        # Show the reset link only during development.
        if settings.DEBUG:
            reset_link = generated_link

        # Production email integration:
        #
        # await email_service.send_password_reset_email(
        #     recipient=user.email,
        #     reset_link=generated_link,
        # )

        add_audit_log(
            db=db,
            request=request,
            action="authentication.password_reset_requested",
            result="success",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
        )

        db.commit()

    return templates.TemplateResponse(
        request=request,
        name="auth/reset_password_sent.html",
        context=template_context(
            request,
            message=(
                "If an active account matches the information "
                "you entered, password-reset instructions have "
                "been prepared."
            ),
            reset_link=reset_link,
        ),
        status_code=status.HTTP_200_OK,
    )


# ==========================================================================
# Reset password
# ==========================================================================

@router.get(
    "/reset-password/{token}",
    name="reset_password_page",
)
async def reset_password_page(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
):
    """Display the new-password form for a valid token."""

    payload = read_password_reset_token(token)

    if payload is None:
        return templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context=template_context(
                request,
                error=(
                    "This password-reset link is invalid or "
                    "has expired."
                ),
                token=None,
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = db.get(
        User,
        payload.get("user_id"),
    )

    token_is_valid = (
        user is not None
        and user.email == payload.get("email")
        and user.password_hash
        == payload.get("password_hash")
        and user.status == AccountStatus.ACTIVE
    )

    if not token_is_valid:
        return templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context=template_context(
                request,
                error=(
                    "This password-reset link is invalid or "
                    "has already been used."
                ),
                token=None,
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return templates.TemplateResponse(
        request=request,
        name="auth/reset_password.html",
        context=template_context(
            request,
            token=token,
        ),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/reset-password/{token}",
    name="reset_password_submit",
)
async def reset_password_submit(
    request: Request,
    token: str,
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Set a new password after validating the signed token."""

    errors = validate_password(password)

    if password != confirm_password:
        errors.append(
            "The password confirmation does not match."
        )

    payload = read_password_reset_token(token)

    if payload is None:
        errors.append(
            "This password-reset link is invalid or has expired."
        )

    user = None

    if payload:
        user = db.get(
            User,
            payload.get("user_id"),
        )

        if (
            user is None
            or user.email != payload.get("email")
            or user.password_hash
            != payload.get("password_hash")
            or user.status != AccountStatus.ACTIVE
        ):
            user = None

            errors.append(
                "This password-reset link is invalid or "
                "has already been used."
            )

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context=template_context(
                request,
                errors=errors,
                token=token if payload else None,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    user.password_hash = hash_password(
        password
    )

    add_audit_log(
        db=db,
        request=request,
        action="authentication.password_reset_completed",
        result="success",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
    )

    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context=template_context(
            request,
            success=(
                "Your password has been updated. "
                "You can now log in."
            ),
            next_url="/",
            form_data={
                "username_or_email": user.email,
            },
        ),
        status_code=status.HTTP_200_OK,
    )


# ==========================================================================
# Email verification
# ==========================================================================

@router.get(
    "/verify-email/{token}",
    name="verify_email",
)
async def verify_email(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
):
    """Verify a registered user's email address."""

    payload = read_email_verification_token(
        token
    )

    if payload is None:
        return templates.TemplateResponse(
            request=request,
            name="auth/verify_email.html",
            context=template_context(
                request,
                error=(
                    "This email-verification link is invalid "
                    "or has expired."
                ),
                verification_link=None,
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = db.get(
        User,
        payload.get("user_id"),
    )

    if (
        user is None
        or user.email != payload.get("email")
    ):
        return templates.TemplateResponse(
            request=request,
            name="auth/verify_email.html",
            context=template_context(
                request,
                error=(
                    "The email-verification link does not "
                    "match an account."
                ),
                verification_link=None,
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not user.email_verified:
        user.email_verified = True

        add_audit_log(
            db=db,
            request=request,
            action="authentication.email_verified",
            result="success",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
        )

        db.commit()

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context=template_context(
            request,
            success=(
                "Your email address has been verified. "
                "You can now log in."
            ),
            next_url="/",
            form_data={
                "username_or_email": user.email,
            },
        ),
        status_code=status.HTTP_200_OK,
    )