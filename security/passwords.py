"""
Password hashing, verification and validation.

File:
    security/passwords.py
"""

import secrets
from dataclasses import dataclass

from passlib.context import CryptContext


MINIMUM_PASSWORD_LENGTH = 10
MAXIMUM_PASSWORD_LENGTH = 128


password_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


# This hash is used when an account does not exist.
# It helps reduce timing differences between valid and
# invalid username attempts.
DUMMY_PASSWORD_HASH = password_context.hash(
    secrets.token_urlsafe(32)
)


@dataclass
class PasswordValidationResult:
    """Result returned by password validation."""

    valid: bool
    errors: list[str]


class PasswordValidationError(ValueError):
    """Raised when a password does not meet security rules."""

    def __init__(
        self,
        errors: list[str],
    ):
        self.errors = errors

        super().__init__(
            " ".join(errors)
        )


def hash_password(
    password: str,
) -> str:
    """
    Create a secure PBKDF2-SHA256 password hash.

    The returned value includes the salt and algorithm
    parameters required for later verification.
    """

    result = validate_password(password)

    if not result.valid:
        raise PasswordValidationError(
            result.errors
        )

    return password_context.hash(password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    """
    Compare a plain password with a stored password hash.

    Returns False if the input or saved hash is invalid.
    """

    if not plain_password or not password_hash:
        return False

    try:
        return password_context.verify(
            plain_password,
            password_hash,
        )
    except (
        TypeError,
        ValueError,
    ):
        return False


def perform_dummy_password_check(
    plain_password: str,
) -> None:
    """
    Perform a password check even when a user does not exist.

    This can reduce timing differences that might otherwise
    help an attacker discover registered usernames.
    """

    try:
        password_context.verify(
            plain_password or "",
            DUMMY_PASSWORD_HASH,
        )
    except (
        TypeError,
        ValueError,
    ):
        pass


def validate_password(
    password: str,
) -> PasswordValidationResult:
    """
    Validate a password against the application policy.

    Requirements:

    - Between 10 and 128 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    - No surrounding whitespace
    - Not composed entirely of whitespace
    """

    errors = []

    if not isinstance(password, str):
        return PasswordValidationResult(
            valid=False,
            errors=[
                "Password must be text."
            ],
        )

    if not password:
        return PasswordValidationResult(
            valid=False,
            errors=[
                "Password is required."
            ],
        )

    if not password.strip():
        errors.append(
            "Password cannot contain only spaces."
        )

    if password != password.strip():
        errors.append(
            "Password cannot begin or end with spaces."
        )

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
            "Password must contain at least one "
            "uppercase letter."
        )

    if not any(
        character.islower()
        for character in password
    ):
        errors.append(
            "Password must contain at least one "
            "lowercase letter."
        )

    if not any(
        character.isdigit()
        for character in password
    ):
        errors.append(
            "Password must contain at least one number."
        )

    if not any(
        not character.isalnum()
        and not character.isspace()
        for character in password
    ):
        errors.append(
            "Password must contain at least one "
            "special character."
        )

    return PasswordValidationResult(
        valid=not errors,
        errors=errors,
    )


def validate_password_or_raise(
    password: str,
) -> None:
    """
    Validate a password and raise PasswordValidationError
    when it does not meet the policy.
    """

    result = validate_password(password)

    if not result.valid:
        raise PasswordValidationError(
            result.errors
        )


def password_needs_rehash(
    password_hash: str,
) -> bool:
    """
    Return True when a stored password should be rehashed.

    This allows future password-policy upgrades without
    forcing every user to reset their password immediately.
    """

    if not password_hash:
        return True

    try:
        return password_context.needs_update(
            password_hash
        )
    except (
        TypeError,
        ValueError,
    ):
        return True


def verify_and_update_password(
    plain_password: str,
    password_hash: str,
) -> tuple[bool, str | None]:
    """
    Verify a password and optionally return an updated hash.

    Returns:

        (False, None)
            Password verification failed.

        (True, None)
            Verification succeeded and no update is required.

        (True, new_hash)
            Verification succeeded and the stored hash should
            be replaced with new_hash.
    """

    if not verify_password(
        plain_password,
        password_hash,
    ):
        return False, None

    if password_needs_rehash(
        password_hash
    ):
        new_hash = password_context.hash(
            plain_password
        )

        return True, new_hash

    return True, None