/*
 * Smart Property AI
 * File: static/js/contact.js
 *
 * Contact form enhancements:
 * - Scoped to .contact-wrapper
 * - Accessible client-side validation
 * - Character counter
 * - Duplicate-submission protection
 * - Safe form reset
 *
 * Important:
 * The FastAPI backend must still perform complete server-side
 * validation and CSRF verification.
 */

(() => {
    "use strict";

    function initializeContactPage() {
        const wrapper =
            document.querySelector(
                ".contact-wrapper"
            );

        if (
            !wrapper ||
            wrapper.dataset.contactInitialized ===
                "true"
        ) {
            return;
        }

        const form =
            wrapper.querySelector(
                "#contact-form"
            );

        if (!form) {
            return;
        }

        wrapper.dataset.contactInitialized =
            "true";

        const submitButton =
            form.querySelector(
                "[data-submit-button]"
            );

        const resetButton =
            form.querySelector(
                "button[type='reset']"
            );

        const fullNameInput =
            form.querySelector(
                "#full_name"
            );

        const emailInput =
            form.querySelector(
                "#email"
            );

        const phoneInput =
            form.querySelector(
                "#phone_number"
            );

        const languageSelect =
            form.querySelector(
                "#preferred_language"
            );

        const categorySelect =
            form.querySelector(
                "#category"
            );

        const subjectInput =
            form.querySelector(
                "#subject"
            );

        const messageInput =
            form.querySelector(
                "#message"
            );

        const privacyInput =
            form.querySelector(
                "#privacy_consent"
            );

        const csrfInput =
            form.querySelector(
                "input[name='csrf_token']"
            );

        let submitting = false;
        let errorSummary = null;
        let characterCounter = null;

        const allowedCategories = new Set([
            "apartment_search",
            "rental_application",
            "tenant_support",
            "landlord_support",
            "maintenance",
            "payment",
            "accessibility",
            "privacy",
            "technical_support",
            "other"
        ]);

        const allowedLanguages = new Set([
            "en",
            "de",
            "fr",
            "es",
            "it",
            "pt",
            "ar",
            "tr",
            "pl",
            "uk"
        ]);

        function cleanValue(element) {
            if (
                !element ||
                typeof element.value !==
                    "string"
            ) {
                return "";
            }

            return element.value.trim();
        }

        function createErrorSummary() {
            const summary =
                document.createElement("div");

            summary.className =
                "contact-wrapper__alert " +
                "contact-wrapper__alert--error " +
                "contact-wrapper__client-errors";

            summary.setAttribute(
                "role",
                "alert"
            );

            summary.setAttribute(
                "aria-live",
                "assertive"
            );

            summary.setAttribute(
                "aria-atomic",
                "true"
            );

            summary.tabIndex = -1;
            summary.hidden = true;

            form.before(summary);

            return summary;
        }

        function getErrorSummary() {
            if (!errorSummary) {
                errorSummary =
                    createErrorSummary();
            }

            return errorSummary;
        }

        function clearErrorSummary() {
            const summary =
                getErrorSummary();

            summary.replaceChildren();
            summary.hidden = true;
        }

        function clearFieldError(field) {
            if (!field) {
                return;
            }

            field.removeAttribute(
                "aria-invalid"
            );

            const errorId =
                field.dataset.errorId;

            if (errorId) {
                document
                    .getElementById(errorId)
                    ?.remove();

                delete field.dataset.errorId;
            }
        }

        function showFieldError(
            field,
            message
        ) {
            if (!field) {
                return;
            }

            clearFieldError(field);

            const errorElement =
                document.createElement("small");

            const errorId =
                `${field.id || field.name}-client-error`;

            errorElement.id = errorId;

            errorElement.className =
                "contact-wrapper__field-error";

            errorElement.textContent =
                message;

            errorElement.setAttribute(
                "role",
                "alert"
            );

            field.setAttribute(
                "aria-invalid",
                "true"
            );

            const currentDescription =
                field
                    .getAttribute(
                        "aria-describedby"
                    )
                    ?.split(/\s+/)
                    .filter(Boolean) || [];

            if (
                !currentDescription.includes(
                    errorId
                )
            ) {
                currentDescription.push(
                    errorId
                );
            }

            field.setAttribute(
                "aria-describedby",
                currentDescription.join(" ")
            );

            field.dataset.errorId =
                errorId;

            const group =
                field.closest(
                    ".contact-wrapper__form-group, " +
                    ".contact-wrapper__form-check"
                );

            if (group) {
                group.appendChild(
                    errorElement
                );
            } else {
                field.insertAdjacentElement(
                    "afterend",
                    errorElement
                );
            }
        }

        function clearAllFieldErrors() {
            form
                .querySelectorAll(
                    "[aria-invalid='true']"
                )
                .forEach((field) => {
                    clearFieldError(field);
                });

            form
                .querySelectorAll(
                    ".contact-wrapper__field-error"
                )
                .forEach((error) => {
                    error.remove();
                });
        }

        function isValidEmail(value) {
            if (!value) {
                return false;
            }

            /*
             * Browser email validation handles the detailed format.
             */
            emailInput.value = value;

            return emailInput.validity.valid;
        }

        function isValidPhone(value) {
            if (!value) {
                return true;
            }

            /*
             * Allows international prefixes, spaces,
             * parentheses, periods, and hyphens.
             */
            return /^[+]?[\d\s().-]{6,40}$/.test(
                value
            );
        }

        function validateForm() {
            clearAllFieldErrors();
            clearErrorSummary();

            const errors = [];

            const fullName =
                cleanValue(fullNameInput);

            const email =
                cleanValue(emailInput);

            const phone =
                cleanValue(phoneInput);

            const language =
                cleanValue(languageSelect);

            const category =
                cleanValue(categorySelect);

            const subject =
                cleanValue(subjectInput);

            const message =
                cleanValue(messageInput);

            const csrfToken =
                cleanValue(csrfInput);

            if (fullName.length < 2) {
                errors.push({
                    field: fullNameInput,
                    message:
                        "Enter your full name using at least 2 characters."
                });
            } else if (
                fullName.length > 150
            ) {
                errors.push({
                    field: fullNameInput,
                    message:
                        "Your full name must not exceed 150 characters."
                });
            }

            if (!email) {
                errors.push({
                    field: emailInput,
                    message:
                        "Enter your email address."
                });
            } else if (
                !isValidEmail(email)
            ) {
                errors.push({
                    field: emailInput,
                    message:
                        "Enter a valid email address."
                });
            }

            if (!isValidPhone(phone)) {
                errors.push({
                    field: phoneInput,
                    message:
                        "Enter a valid telephone number or leave this field empty."
                });
            }

            if (
                language &&
                !allowedLanguages.has(language)
            ) {
                errors.push({
                    field: languageSelect,
                    message:
                        "Select a supported language."
                });
            }

            if (!category) {
                errors.push({
                    field: categorySelect,
                    message:
                        "Select a help category."
                });
            } else if (
                !allowedCategories.has(category)
            ) {
                errors.push({
                    field: categorySelect,
                    message:
                        "Select a valid help category."
                });
            }

            if (subject.length < 3) {
                errors.push({
                    field: subjectInput,
                    message:
                        "Enter a subject using at least 3 characters."
                });
            } else if (
                subject.length > 200
            ) {
                errors.push({
                    field: subjectInput,
                    message:
                        "The subject must not exceed 200 characters."
                });
            }

            if (message.length < 10) {
                errors.push({
                    field: messageInput,
                    message:
                        "Enter a message using at least 10 characters."
                });
            } else if (
                message.length > 5000
            ) {
                errors.push({
                    field: messageInput,
                    message:
                        "The message must not exceed 5,000 characters."
                });
            }

            if (
                !privacyInput ||
                !privacyInput.checked
            ) {
                errors.push({
                    field: privacyInput,
                    message:
                        "You must accept the privacy information before sending your message."
                });
            }

            if (!csrfToken) {
                errors.push({
                    field: null,
                    message:
                        "The security token is missing. Refresh the page and try again."
                });
            }

            errors.forEach((error) => {
                if (error.field) {
                    showFieldError(
                        error.field,
                        error.message
                    );
                }
            });

            return errors;
        }

        function displayErrorSummary(errors) {
            const summary =
                getErrorSummary();

            const heading =
                document.createElement("strong");

            heading.textContent =
                "Please correct the following:";

            const list =
                document.createElement("ul");

            errors.forEach((error) => {
                const item =
                    document.createElement("li");

                if (
                    error.field &&
                    error.field.id
                ) {
                    const link =
                        document.createElement("a");

                    link.href =
                        `#${error.field.id}`;

                    link.textContent =
                        error.message;

                    link.addEventListener(
                        "click",
                        () => {
                            window.setTimeout(
                                () =>
                                    error.field.focus(),
                                0
                            );
                        }
                    );

                    item.appendChild(link);
                } else {
                    item.textContent =
                        error.message;
                }

                list.appendChild(item);
            });

            summary.replaceChildren(
                heading,
                list
            );

            summary.hidden = false;
            summary.focus();
        }

        function setSubmitting(state) {
            submitting = state;

            if (!submitButton) {
                return;
            }

            if (
                !submitButton.dataset
                    .originalText
            ) {
                submitButton.dataset.originalText =
                    submitButton.textContent.trim() ||
                    "Send message";
            }

            submitButton.disabled = state;

            submitButton.setAttribute(
                "aria-disabled",
                String(state)
            );

            submitButton.textContent =
                state
                    ? "Sending…"
                    : submitButton.dataset
                          .originalText;

            form.setAttribute(
                "aria-busy",
                String(state)
            );
        }

        function updateCharacterCounter() {
            if (
                !messageInput ||
                !characterCounter
            ) {
                return;
            }

            const length =
                messageInput.value.length;

            const maximum =
                Number.parseInt(
                    messageInput.maxLength,
                    10
                ) || 5000;

            const remaining =
                Math.max(
                    maximum - length,
                    0
                );

            characterCounter.textContent =
                `${length.toLocaleString()} of ` +
                `${maximum.toLocaleString()} characters used. ` +
                `${remaining.toLocaleString()} remaining.`;

            characterCounter.classList.toggle(
                "is-near-limit",
                remaining <= 500
            );

            characterCounter.classList.toggle(
                "is-at-limit",
                remaining === 0
            );
        }

        function createCharacterCounter() {
            if (!messageInput) {
                return;
            }

            characterCounter =
                document.createElement("small");

            characterCounter.id =
                "message-character-count";

            characterCounter.className =
                "contact-wrapper__character-count";

            characterCounter.setAttribute(
                "aria-live",
                "polite"
            );

            messageInput.insertAdjacentElement(
                "afterend",
                characterCounter
            );

            const describedBy =
                messageInput
                    .getAttribute(
                        "aria-describedby"
                    )
                    ?.split(/\s+/)
                    .filter(Boolean) || [];

            if (
                !describedBy.includes(
                    characterCounter.id
                )
            ) {
                describedBy.push(
                    characterCounter.id
                );
            }

            messageInput.setAttribute(
                "aria-describedby",
                describedBy.join(" ")
            );

            updateCharacterCounter();
        }

        function clearServerAlerts() {
            wrapper
                .querySelectorAll(
                    ".contact-wrapper__alert"
                )
                .forEach((alert) => {
                    /*
                     * Keep the JavaScript error summary.
                     * It is cleared separately.
                     */
                    if (
                        !alert.classList.contains(
                            "contact-wrapper__client-errors"
                        )
                    ) {
                        alert.remove();
                    }
                });
        }

        form.addEventListener(
            "submit",
            (event) => {
                if (submitting) {
                    event.preventDefault();
                    return;
                }

                const errors =
                    validateForm();

                if (errors.length) {
                    event.preventDefault();

                    displayErrorSummary(
                        errors
                    );

                    return;
                }

                /*
                 * Permit the normal browser POST request.
                 * The server remains responsible for:
                 * - CSRF verification
                 * - validation
                 * - message storage or secure delivery
                 *
                 * Do not log form content here.
                 */
                setSubmitting(true);
            }
        );

        form.addEventListener(
            "input",
            (event) => {
                const field =
                    event.target;

                if (
                    field instanceof
                        HTMLInputElement ||
                    field instanceof
                        HTMLTextAreaElement ||
                    field instanceof
                        HTMLSelectElement
                ) {
                    clearFieldError(field);
                }

                if (field === messageInput) {
                    updateCharacterCounter();
                }
            }
        );

        form.addEventListener(
            "change",
            (event) => {
                const field =
                    event.target;

                if (
                    field instanceof
                        HTMLInputElement ||
                    field instanceof
                        HTMLSelectElement
                ) {
                    clearFieldError(field);
                }
            }
        );

        form.addEventListener(
            "reset",
            () => {
                window.setTimeout(() => {
                    clearAllFieldErrors();
                    clearErrorSummary();
                    clearServerAlerts();
                    setSubmitting(false);
                    updateCharacterCounter();

                    fullNameInput?.focus();
                }, 0);
            }
        );

        /*
         * Restore the send button if the browser returns
         * to this page from its back-forward cache.
         */
        window.addEventListener(
            "pageshow",
            () => {
                setSubmitting(false);
            }
        );

        /*
         * Optional reset-button confirmation.
         */
        resetButton?.addEventListener(
            "click",
            (event) => {
                const formHasContent = [
                    fullNameInput,
                    emailInput,
                    phoneInput,
                    subjectInput,
                    messageInput
                ].some(
                    (field) =>
                        cleanValue(field).length > 0
                );

                if (
                    formHasContent &&
                    !window.confirm(
                        "Clear all information entered in this form?"
                    )
                ) {
                    event.preventDefault();
                }
            }
        );

        createCharacterCounter();
    }

    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initializeContactPage,
            { once: true }
        );
    } else {
        initializeContactPage();
    }
})();