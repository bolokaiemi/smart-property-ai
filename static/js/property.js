"use strict";

/*
|--------------------------------------------------------------------------
| Smart Property AI — Property Management
|--------------------------------------------------------------------------
*/

document.addEventListener("DOMContentLoaded", () => {
    initializeConfirmationForms();
    initializeDescriptionCounter();
    initializeCurrentLocation();
    initializeUnitMenus();
    initializeDeleteUnitDialog();
    initializePropertyForms();
    initializeUnitForms();
});


/* ==========================================================================
   Confirmation forms
   ========================================================================== */

function initializeConfirmationForms() {
    document.querySelectorAll(
        "[data-confirm-form]"
    ).forEach((form) => {
        form.addEventListener("submit", (event) => {
            const message =
                form.dataset.confirmMessage ||
                "Are you sure you want to continue?";

            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });
}


/* ==========================================================================
   Description character counter
   ========================================================================== */

function initializeDescriptionCounter() {
    const description = document.getElementById(
        "property-description"
    );

    const counter = document.getElementById(
        "description-counter"
    );

    if (!description || !counter) {
        return;
    }

    const maximumLength = Number(
        description.getAttribute("maxlength")
    ) || 10000;

    const updateCounter = () => {
        const currentLength = description.value.length;

        counter.textContent =
            `${currentLength.toLocaleString()} / ` +
            `${maximumLength.toLocaleString()}`;

        counter.classList.toggle(
            "text-error",
            currentLength >= maximumLength
        );
    };

    description.addEventListener(
        "input",
        updateCounter
    );

    updateCounter();
}


/* ==========================================================================
   Browser geolocation
   ========================================================================== */

function initializeCurrentLocation() {
    const locationButton = document.getElementById(
        "use-current-location"
    );

    const latitudeInput = document.getElementById(
        "property-latitude"
    );

    const longitudeInput = document.getElementById(
        "property-longitude"
    );

    const locationStatus = document.getElementById(
        "location-status"
    );

    if (
        !locationButton ||
        !latitudeInput ||
        !longitudeInput
    ) {
        return;
    }

    locationButton.addEventListener("click", () => {
        if (!navigator.geolocation) {
            setLocationStatus(
                locationStatus,
                "Location services are not supported by this browser.",
                true
            );

            return;
        }

        locationButton.disabled = true;

        setLocationStatus(
            locationStatus,
            "Requesting your current location...",
            false
        );

        navigator.geolocation.getCurrentPosition(
            (position) => {
                latitudeInput.value =
                    position.coords.latitude.toFixed(7);

                longitudeInput.value =
                    position.coords.longitude.toFixed(7);

                setLocationStatus(
                    locationStatus,
                    "The coordinates have been added. " +
                    "Please confirm that they identify the property.",
                    false
                );

                locationButton.disabled = false;
                latitudeInput.focus();
            },

            (error) => {
                const errorMessages = {
                    1: "Location permission was not granted.",
                    2: "Your location could not be determined.",
                    3: "The location request timed out."
                };

                setLocationStatus(
                    locationStatus,
                    errorMessages[error.code] ||
                    "The location could not be retrieved.",
                    true
                );

                locationButton.disabled = false;
            },

            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 60000
            }
        );
    });
}


function setLocationStatus(
    statusElement,
    message,
    isError
) {
    if (!statusElement) {
        return;
    }

    statusElement.textContent = message;

    statusElement.classList.toggle(
        "text-error",
        isError
    );

    statusElement.classList.toggle(
        "text-success",
        !isError
    );
}


/* ==========================================================================
   Unit action menus
   ========================================================================== */

function initializeUnitMenus() {
    const menuButtons = document.querySelectorAll(
        "[data-unit-menu-button]"
    );

    const closeAllMenus = (
        exceptionButton = null
    ) => {
        menuButtons.forEach((button) => {
            if (button === exceptionButton) {
                return;
            }

            const menuId = button.getAttribute(
                "aria-controls"
            );

            const menu = document.getElementById(
                menuId
            );

            button.setAttribute(
                "aria-expanded",
                "false"
            );

            if (menu) {
                menu.hidden = true;
            }
        });
    };

    menuButtons.forEach((button) => {
        const menuId = button.getAttribute(
            "aria-controls"
        );

        const menu = document.getElementById(
            menuId
        );

        if (!menu) {
            return;
        }

        button.addEventListener("click", (event) => {
            event.stopPropagation();

            const isOpen =
                button.getAttribute("aria-expanded") === "true";

            closeAllMenus(button);

            button.setAttribute(
                "aria-expanded",
                String(!isOpen)
            );

            menu.hidden = isOpen;
        });

        menu.addEventListener("click", (event) => {
            event.stopPropagation();
        });
    });

    document.addEventListener("click", () => {
        closeAllMenus();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") {
            return;
        }

        const openButton = document.querySelector(
            '[data-unit-menu-button][aria-expanded="true"]'
        );

        closeAllMenus();

        if (openButton) {
            openButton.focus();
        }
    });
}


/* ==========================================================================
   Delete-unit dialog
   ========================================================================== */

function initializeDeleteUnitDialog() {
    const dialog = document.getElementById(
        "delete-unit-dialog"
    );

    const deleteForm = document.getElementById(
        "delete-unit-form"
    );

    const unitNumberDisplay = document.getElementById(
        "delete-unit-number"
    );

    const confirmationInput = document.getElementById(
        "confirm-unit-number"
    );

    const cancelButton = document.getElementById(
        "cancel-delete-unit"
    );

    const deleteButtons = document.querySelectorAll(
        "[data-delete-unit-button]"
    );

    if (
        !dialog ||
        !deleteForm ||
        deleteButtons.length === 0
    ) {
        return;
    }

    let previouslyFocusedElement = null;

    deleteButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const unitId =
                button.dataset.deleteUnitButton;

            const unitNumber =
                button.dataset.unitNumber || "";

            previouslyFocusedElement = button;

            if (unitNumberDisplay) {
                unitNumberDisplay.textContent =
                    unitNumber;
            }

            if (confirmationInput) {
                confirmationInput.value = "";
            }

            /*
             * The units list dialog has no fixed action because
             * every row represents a different unit.
             *
             * The unit-details dialog already has the correct
             * action, so it is preserved.
             */
            if (
                unitId &&
                !deleteForm.getAttribute("action")
            ) {
                deleteForm.setAttribute(
                    "action",
                    `/landlord/units/${encodeURIComponent(unitId)}/delete`
                );
            } else if (
                unitId &&
                deleteButtons.length > 1
            ) {
                deleteForm.setAttribute(
                    "action",
                    `/landlord/units/${encodeURIComponent(unitId)}/delete`
                );
            }

            if (typeof dialog.showModal === "function") {
                dialog.showModal();

                window.setTimeout(() => {
                    if (confirmationInput) {
                        confirmationInput.focus();
                    }
                }, 50);
            } else {
                const confirmed = window.confirm(
                    `Permanently delete unit ${unitNumber}?`
                );

                if (confirmed) {
                    const typedUnitNumber = window.prompt(
                        `Enter ${unitNumber} to confirm:`
                    );

                    if (typedUnitNumber === unitNumber) {
                        if (confirmationInput) {
                            confirmationInput.value =
                                typedUnitNumber;
                        }

                        deleteForm.submit();
                    }
                }
            }
        });
    });

    if (cancelButton) {
        cancelButton.addEventListener("click", () => {
            dialog.close();
        });
    }

    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
            dialog.close();
        }
    });

    dialog.addEventListener("close", () => {
        if (confirmationInput) {
            confirmationInput.value = "";
        }

        if (previouslyFocusedElement) {
            previouslyFocusedElement.focus();
        }
    });

    deleteForm.addEventListener("submit", (event) => {
        const requiredUnitNumber =
            unitNumberDisplay
                ? unitNumberDisplay.textContent.trim()
                : "";

        const enteredUnitNumber =
            confirmationInput
                ? confirmationInput.value.trim()
                : "";

        if (
            requiredUnitNumber &&
            enteredUnitNumber.toLowerCase() !==
            requiredUnitNumber.toLowerCase()
        ) {
            event.preventDefault();

            if (confirmationInput) {
                confirmationInput.setAttribute(
                    "aria-invalid",
                    "true"
                );

                confirmationInput.setCustomValidity(
                    "The unit number does not match."
                );

                confirmationInput.reportValidity();
                confirmationInput.focus();
            }
        }
    });

    if (confirmationInput) {
        confirmationInput.addEventListener("input", () => {
            confirmationInput.removeAttribute(
                "aria-invalid"
            );

            confirmationInput.setCustomValidity("");
        });
    }
}


/* ==========================================================================
   Property-form validation
   ========================================================================== */

function initializePropertyForms() {
    const forms = [
        document.getElementById("add-property-form"),
        document.getElementById("edit-property-form")
    ].filter(Boolean);

    forms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            clearFormValidation(form);

            const errors = [];

            const propertyName = form.querySelector(
                '[name="name"]'
            );

            const propertyType = form.querySelector(
                '[name="property_type"]'
            );

            const streetAddress = form.querySelector(
                '[name="street_address"]'
            );

            const postalCode = form.querySelector(
                '[name="postal_code"]'
            );

            const city = form.querySelector(
                '[name="city"]'
            );

            const country = form.querySelector(
                '[name="country"]'
            );

            const latitude = form.querySelector(
                '[name="latitude"]'
            );

            const longitude = form.querySelector(
                '[name="longitude"]'
            );

            if (
                !propertyName ||
                propertyName.value.trim().length < 2
            ) {
                errors.push(
                    "Enter a property name containing at least two characters."
                );

                markInvalid(propertyName);
            }

            if (!propertyType || !propertyType.value) {
                errors.push(
                    "Select a property type."
                );

                markInvalid(propertyType);
            }

            if (
                !streetAddress ||
                streetAddress.value.trim().length < 4
            ) {
                errors.push(
                    "Enter a complete street address."
                );

                markInvalid(streetAddress);
            }

            if (
                !postalCode ||
                postalCode.value.trim().length < 3
            ) {
                errors.push(
                    "Enter a valid postal code."
                );

                markInvalid(postalCode);
            }

            if (
                !city ||
                city.value.trim().length < 2
            ) {
                errors.push(
                    "Enter a valid city."
                );

                markInvalid(city);
            }

            if (
                !country ||
                country.value.trim().length < 2
            ) {
                errors.push(
                    "Enter a valid country."
                );

                markInvalid(country);
            }

            validateCoordinate(
                latitude,
                -90,
                90,
                "Latitude",
                errors
            );

            validateCoordinate(
                longitude,
                -180,
                180,
                "Longitude",
                errors
            );

            if (errors.length > 0) {
                event.preventDefault();

                showValidationSummary(
                    form,
                    errors
                );

                return;
            }

            setSubmitting(form);
        });
    });
}


function validateCoordinate(
    field,
    minimum,
    maximum,
    fieldName,
    errors
) {
    if (!field || field.value.trim() === "") {
        return;
    }

    const value = Number(field.value);

    if (
        !Number.isFinite(value) ||
        value < minimum ||
        value > maximum
    ) {
        errors.push(
            `${fieldName} must be between ${minimum} and ${maximum}.`
        );

        markInvalid(field);
    }
}


/* ==========================================================================
   Unit-form validation
   ========================================================================== */

function initializeUnitForms() {
    const forms = [
        document.getElementById("add-unit-form"),
        document.getElementById("edit-unit-form")
    ].filter(Boolean);

    forms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            clearFormValidation(form);

            const errors = [];

            const unitNumber = form.querySelector(
                '[name="unit_number"]'
            );

            const rooms = form.querySelector(
                '[name="rooms"]'
            );

            const bedrooms = form.querySelector(
                '[name="bedrooms"]'
            );

            const bathrooms = form.querySelector(
                '[name="bathrooms"]'
            );

            const monthlyRent = form.querySelector(
                '[name="monthly_rent"]'
            );

            const deposit = form.querySelector(
                '[name="deposit_amount"]'
            );

            const currency = form.querySelector(
                '[name="currency"]'
            );

            if (
                !unitNumber ||
                !unitNumber.value.trim()
            ) {
                errors.push(
                    "Enter a unit number or name."
                );

                markInvalid(unitNumber);
            }

            if (
                !rooms ||
                Number(rooms.value) < 0.5
            ) {
                errors.push(
                    "Rooms must be at least 0.5."
                );

                markInvalid(rooms);
            }

            if (
                bedrooms &&
                Number(bedrooms.value) >
                Number(rooms.value)
            ) {
                errors.push(
                    "Bedrooms cannot exceed the total number of rooms."
                );

                markInvalid(bedrooms);
            }

            if (
                bathrooms &&
                Number(bathrooms.value) < 0
            ) {
                errors.push(
                    "Bathrooms cannot be negative."
                );

                markInvalid(bathrooms);
            }

            if (
                !monthlyRent ||
                monthlyRent.value === "" ||
                Number(monthlyRent.value) < 0
            ) {
                errors.push(
                    "Enter a valid monthly rent."
                );

                markInvalid(monthlyRent);
            }

            if (
                deposit &&
                deposit.value !== "" &&
                Number(deposit.value) < 0
            ) {
                errors.push(
                    "Deposit amount cannot be negative."
                );

                markInvalid(deposit);
            }

            if (!currency || !currency.value) {
                errors.push(
                    "Select a currency."
                );

                markInvalid(currency);
            }

            if (errors.length > 0) {
                event.preventDefault();

                showValidationSummary(
                    form,
                    errors
                );

                return;
            }

            setSubmitting(form);
        });
    });
}


/* ==========================================================================
   Shared form helpers
   ========================================================================== */

function markInvalid(field) {
    if (!field) {
        return;
    }

    field.setAttribute(
        "aria-invalid",
        "true"
    );
}


function clearFormValidation(form) {
    form.querySelectorAll(
        '[aria-invalid="true"]'
    ).forEach((field) => {
        field.removeAttribute(
            "aria-invalid"
        );
    });

    const previousSummary = document.getElementById(
        "client-property-error-summary"
    );

    if (previousSummary) {
        previousSummary.remove();
    }
}


function showValidationSummary(form, errors) {
    const uniqueErrors = Array.from(
        new Set(errors)
    );

    const summary = document.createElement("div");

    summary.id = "client-property-error-summary";
    summary.className =
        "property-alert property-alert--error";

    summary.setAttribute(
        "role",
        "alert"
    );

    summary.setAttribute(
        "tabindex",
        "-1"
    );

    const heading = document.createElement("p");
    heading.textContent =
        "Please correct the following:";

    const list = document.createElement("ul");

    uniqueErrors.forEach((message) => {
        const item = document.createElement("li");
        item.textContent = message;
        list.appendChild(item);
    });

    summary.appendChild(heading);
    summary.appendChild(list);

    form.insertAdjacentElement(
        "beforebegin",
        summary
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


function setSubmitting(form) {
    const submitButton = form.querySelector(
        'button[type="submit"]'
    );

    if (!submitButton) {
        return;
    }

    form.classList.add("is-submitting");
    submitButton.disabled = true;

    if (!submitButton.dataset.originalText) {
        submitButton.dataset.originalText =
            submitButton.textContent.trim();
    }

    submitButton.textContent = "Saving...";
}