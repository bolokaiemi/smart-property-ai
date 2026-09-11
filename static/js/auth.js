"use strict";

/*
|--------------------------------------------------------------------------
| Smart Property AI Authentication
|--------------------------------------------------------------------------
| Features:
| - Show and hide password
| - Password strength feedback
| - Password confirmation feedback
| - Registration validation
| - Remember username
| - Submit-button loading state
| - Accessible validation messages
|--------------------------------------------------------------------------
*/

document.addEventListener("DOMContentLoaded", () => {
    initializePasswordToggles();
    initializePasswordStrength();
    initializePasswordConfirmation();
    initializeLoginForm();
    initializeRegistrationForm();
    initializeResetPasswordForm();
    initializeGeneralAuthForms();
});


/* ==========================================================================
   Safe browser storage
   ========================================================================== */

function getStoredAuthValue(key, fallback = "") {
    try {
        const value = window.localStorage.getItem(key);

        return value === null
            ? fallback
            : value;
    } catch (error) {
        return fallback;
    }
}


function setStoredAuthValue(key, value) {
    try {
        window.localStorage.setItem(key, value);
    } catch (error) {
        console.warn(
            "Browser storage is unavailable."
        );
    }
}


function removeStoredAuthValue(key) {
    try {
        window.localStorage.removeItem(key);
    } catch (error) {
        console.warn(
            "Browser storage is unavailable."
        );
    }
}


/* ==========================================================================
   Password visibility
   ========================================================================== */

function initializePasswordToggles() {
    const passwordToggles = document.querySelectorAll(
        "[data-password-toggle]"
    );

    passwordToggles.forEach((toggleButton) => {
        const targetId = toggleButton.dataset.passwordToggle;
        const passwordInput = document.getElementById(targetId);

        if (!passwordInput) {
            return;
        }

        toggleButton.addEventListener("click", () => {
            const passwordIsVisible =
                passwordInput.type === "text";

            passwordInput.type = passwordIsVisible
                ? "password"
                : "text";

            toggleButton.textContent = passwordIsVisible
                ? "Show"
                : "Hide";

            toggleButton.setAttribute(
                "aria-pressed",
                String(!passwordIsVisible)
            );

            toggleButton.setAttribute(
                "aria-label",
                passwordIsVisible
                    ? "Show password"
                    : "Hide password"
            );

            passwordInput.focus();

            const inputLength = passwordInput.value.length;

            try {
                passwordInput.setSelectionRange(
                    inputLength,
                    inputLength
                );
            } catch (error) {
                // Some input implementations may not support this.
            }
        });
    });
}


/* ==========================================================================
   Password strength
   ========================================================================== */

function initializePasswordStrength() {
    const passwordInput =
        document.getElementById("register-password") ||
        document.getElementById("reset-password");

    const strengthContainer = document.getElementById(
        "password-strength"
    );

    if (!passwordInput || !strengthContainer) {
        return;
    }

    const updateStrength = () => {
        const result = calculatePasswordStrength(
            passwordInput.value
        );

        if (!passwordInput.value) {
            strengthContainer.innerHTML = "";
            return;
        }

        strengthContainer.className =
            `auth-password-strength auth-strength--${result.level}`;

        strengthContainer.innerHTML = `
            <div
                class="auth-strength-meter"
                aria-hidden="true"
            >
                <div class="auth-strength-meter__bar"></div>
            </div>

            <span>
                Password strength: ${result.label}
            </span>
        `;
    };

    passwordInput.addEventListener(
        "input",
        updateStrength
    );

    updateStrength();
}


function calculatePasswordStrength(password) {
    let score = 0;

    if (password.length >= 10) {
        score += 1;
    }

    if (password.length >= 14) {
        score += 1;
    }

    if (/[a-z]/.test(password)) {
        score += 1;
    }

    if (/[A-Z]/.test(password)) {
        score += 1;
    }

    if (/[0-9]/.test(password)) {
        score += 1;
    }

    if (/[^A-Za-z0-9\s]/.test(password)) {
        score += 1;
    }

    if (/\s/.test(password)) {
        score -= 1;
    }

    if (
        /(.)\1{2,}/.test(password) ||
        /12345|password|qwerty|admin/i.test(password)
    ) {
        score -= 2;
    }

    if (score <= 2) {
        return {
            level: "weak",
            label: "Weak"
        };
    }

    if (score <= 4) {
        return {
            level: "fair",
            label: "Fair"
        };
    }

    if (score === 5) {
        return {
            level: "good",
            label: "Good"
        };
    }

    return {
        level: "strong",
        label: "Strong"
    };
}


/* ==========================================================================
   Password confirmation
   ========================================================================== */

function initializePasswordConfirmation() {
    const passwordInput =
        document.getElementById("register-password") ||
        document.getElementById("reset-password");

    const confirmPasswordInput =
        document.getElementById("confirm-password") ||
        document.getElementById("reset-confirm-password");

    const matchStatus = document.getElementById(
        "password-match-status"
    );

    if (
        !passwordInput ||
        !confirmPasswordInput ||
        !matchStatus
    ) {
        return;
    }

    const updateMatchStatus = () => {
        const password = passwordInput.value;
        const confirmation = confirmPasswordInput.value;

        confirmPasswordInput.removeAttribute(
            "aria-invalid"
        );

        matchStatus.classList.remove(
            "auth-help--valid",
            "auth-help--error"
        );

        if (!confirmation) {
            matchStatus.textContent = "";
            return;
        }

        if (password === confirmation) {
            matchStatus.textContent =
                "The passwords match.";

            matchStatus.classList.add(
                "auth-help--valid"
            );
        } else {
            matchStatus.textContent =
                "The passwords do not match.";

            matchStatus.classList.add(
                "auth-help--error"
            );

            confirmPasswordInput.setAttribute(
                "aria-invalid",
                "true"
            );
        }
    };

    passwordInput.addEventListener(
        "input",
        updateMatchStatus
    );

    confirmPasswordInput.addEventListener(
        "input",
        updateMatchStatus
    );
}


/* ==========================================================================
   Login form and Remember Me
   ========================================================================== */

function initializeLoginForm() {
    const loginForm = document.getElementById(
        "login-form"
    );

    if (!loginForm) {
        return;
    }

    const identifierInput = loginForm.querySelector(
        '[name="username_or_email"]'
    );

    const rememberCheckbox = loginForm.querySelector(
        '[name="remember_me"]'
    );

    if (!identifierInput || !rememberCheckbox) {
        return;
    }

    const rememberedIdentifier = getStoredAuthValue(
        "smartPropertyRememberedIdentifier"
    );

    if (
        rememberedIdentifier &&
        !identifierInput.value
    ) {
        identifierInput.value = rememberedIdentifier;
        rememberCheckbox.checked = true;
    }

    loginForm.addEventListener("submit", () => {
        const identifier = identifierInput.value.trim();

        if (
            rememberCheckbox.checked &&
            identifier
        ) {
            setStoredAuthValue(
                "smartPropertyRememberedIdentifier",
                identifier
            );
        } else {
            removeStoredAuthValue(
                "smartPropertyRememberedIdentifier"
            );
        }
    });
}


/* ==========================================================================
   Registration validation
   ========================================================================== */

function initializeRegistrationForm() {
    const registrationForm = document.getElementById(
        "registration-form"
    );

    if (!registrationForm) {
        return;
    }

    registrationForm.addEventListener(
        "submit",
        (event) => {
            clearClientValidationErrors(
                registrationForm
            );

            const errors = [];

            const fullName = registrationForm.querySelector(
                '[name="full_name"]'
            );

            const username = registrationForm.querySelector(
                '[name="username"]'
            );

            const email = registrationForm.querySelector(
                '[name="email"]'
            );

            const role = registrationForm.querySelector(
                '[name="role"]'
            );

            const password = registrationForm.querySelector(
                '[name="password"]'
            );

            const confirmPassword =
                registrationForm.querySelector(
                    '[name="confirm_password"]'
                );

            const privacy = registrationForm.querySelector(
                '[name="accept_privacy"]'
            );

            const terms = registrationForm.querySelector(
                '[name="accept_terms"]'
            );

            if (
                !fullName ||
                fullName.value.trim().length < 2
            ) {
                errors.push(
                    "Please enter your full name."
                );

                markFieldInvalid(fullName);
            }

            if (
                !username ||
                !/^[A-Za-z0-9._-]{3,100}$/.test(
                    username.value.trim()
                )
            ) {
                errors.push(
                    "Enter a valid username using letters, " +
                    "numbers, periods, hyphens or underscores."
                );

                markFieldInvalid(username);
            }

            if (
                !email ||
                !email.validity.valid
            ) {
                errors.push(
                    "Please enter a valid email address."
                );

                markFieldInvalid(email);
            }

            if (!role || !role.value) {
                errors.push(
                    "Please select an account type."
                );

                markFieldInvalid(role);
            }

            const passwordErrors =
                validatePasswordOnClient(
                    password ? password.value : ""
                );

            passwordErrors.forEach((error) => {
                errors.push(error);
            });

            if (passwordErrors.length > 0) {
                markFieldInvalid(password);
            }

            if (
                !password ||
                !confirmPassword ||
                password.value !== confirmPassword.value
            ) {
                errors.push(
                    "The password confirmation does not match."
                );

                markFieldInvalid(confirmPassword);
            }

            if (!privacy || !privacy.checked) {
                errors.push(
                    "You must acknowledge the Privacy Policy."
                );

                markFieldInvalid(privacy);
            }

            if (!terms || !terms.checked) {
                errors.push(
                    "You must accept the Terms of Use."
                );

                markFieldInvalid(terms);
            }

            if (errors.length > 0) {
                event.preventDefault();

                showClientValidationErrors(
                    registrationForm,
                    errors
                );

                return;
            }

            setFormSubmitting(
                registrationForm,
                true
            );
        }
    );
}


/* ==========================================================================
   Reset-password validation
   ========================================================================== */

function initializeResetPasswordForm() {
    const resetForm = document.getElementById(
        "reset-password-form"
    );

    if (!resetForm) {
        return;
    }

    resetForm.addEventListener(
        "submit",
        (event) => {
            clearClientValidationErrors(
                resetForm
            );

            const password = resetForm.querySelector(
                '[name="password"]'
            );

            const confirmPassword = resetForm.querySelector(
                '[name="confirm_password"]'
            );

            const errors = validatePasswordOnClient(
                password ? password.value : ""
            );

            if (
                !password ||
                !confirmPassword ||
                password.value !== confirmPassword.value
            ) {
                errors.push(
                    "The password confirmation does not match."
                );

                markFieldInvalid(confirmPassword);
            }

            if (errors.length > 0) {
                event.preventDefault();

                markFieldInvalid(password);

                showClientValidationErrors(
                    resetForm,
                    errors
                );

                return;
            }

            setFormSubmitting(
                resetForm,
                true
            );
        }
    );
}


/* ==========================================================================
   General form submission state
   ========================================================================== */

function initializeGeneralAuthForms() {
    const authForms = document.querySelectorAll(
        ".auth-form"
    );

    authForms.forEach((form) => {
        if (
            form.id === "registration-form" ||
            form.id === "reset-password-form"
        ) {
            return;
        }

        form.addEventListener("submit", (event) => {
            if (!form.checkValidity()) {
                return;
            }

            setFormSubmitting(
                form,
                true
            );
        });
    });
}


function setFormSubmitting(form, submitting) {
    const submitButton = form.querySelector(
        'button[type="submit"]'
    );

    if (!submitButton) {
        return;
    }

    if (submitting) {
        if (!submitButton.dataset.originalText) {
            submitButton.dataset.originalText =
                submitButton.textContent.trim();
        }

        form.classList.add("is-submitting");
        submitButton.disabled = true;

        submitButton.innerHTML = `
            <span
                class="auth-submit-spinner"
                aria-hidden="true"
            ></span>

            <span>Processing...</span>
        `;
    } else {
        form.classList.remove("is-submitting");
        submitButton.disabled = false;

        submitButton.textContent =
            submitButton.dataset.originalText ||
            "Submit";
    }
}


/* ==========================================================================
   Validation helpers
   ========================================================================== */

function validatePasswordOnClient(password) {
    const errors = [];

    if (password.length < 10) {
        errors.push(
            "Password must contain at least 10 characters."
        );
    }

    if (password.length > 128) {
        errors.push(
            "Password must not exceed 128 characters."
        );
    }

    if (!/[A-Z]/.test(password)) {
        errors.push(
            "Password must contain an uppercase letter."
        );
    }

    if (!/[a-z]/.test(password)) {
        errors.push(
            "Password must contain a lowercase letter."
        );
    }

    if (!/[0-9]/.test(password)) {
        errors.push(
            "Password must contain a number."
        );
    }

    if (!/[^A-Za-z0-9\s]/.test(password)) {
        errors.push(
            "Password must contain a special character."
        );
    }

    if (password !== password.trim()) {
        errors.push(
            "Password cannot begin or end with spaces."
        );
    }

    return errors;
}


function markFieldInvalid(field) {
    if (!field) {
        return;
    }

    field.setAttribute(
        "aria-invalid",
        "true"
    );
}


function clearClientValidationErrors(form) {
    form.querySelectorAll(
        '[aria-invalid="true"]'
    ).forEach((field) => {
        field.removeAttribute(
            "aria-invalid"
        );
    });

    const previousSummary = document.getElementById(
        "client-validation-summary"
    );

    if (previousSummary) {
        previousSummary.remove();
    }
}


function showClientValidationErrors(form, errors) {
    const uniqueErrors = Array.from(
        new Set(errors)
    );

    const summary = document.createElement("div");

    summary.id = "client-validation-summary";
    summary.className =
        "auth-alert auth-alert--error";

    summary.setAttribute(
        "role",
        "alert"
    );

    summary.setAttribute(
        "aria-live",
        "assertive"
    );

    const heading = document.createElement("p");
    heading.textContent =
        "Please correct the following:";

    const errorList = document.createElement("ul");

    uniqueErrors.forEach((errorMessage) => {
        const listItem = document.createElement("li");
        listItem.textContent = errorMessage;
        errorList.appendChild(listItem);
    });

    summary.appendChild(heading);
    summary.appendChild(errorList);

    form.insertAdjacentElement(
        "beforebegin",
        summary
    );

    summary.setAttribute(
        "tabindex",
        "-1"
    );

    summary.focus();

    const firstInvalidField = form.querySelector(
        '[aria-invalid="true"]'
    );

    if (firstInvalidField) {
        firstInvalidField.addEventListener(
            "input",
            () => {
                firstInvalidField.removeAttribute(
                    "aria-invalid"
                );
            },
            {
                once: true
            }
        );
    }
}