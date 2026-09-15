/*
 * Smart Property AI
 * Tenant portal interactions
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const tenantStatus =
        document.querySelector("[data-tenant-status]");

    const tenantForms =
        document.querySelectorAll(".tenant-form");

    const filterInputs =
        document.querySelectorAll("[data-tenant-filter]");

    const statusFilters =
        document.querySelectorAll("[data-status-filter]");

    const searchRows =
        document.querySelectorAll("[data-tenant-search-item]");

    const propertySelectors =
        document.querySelectorAll("[data-property-select]");

    const unitSelectors =
        document.querySelectorAll("[data-unit-select]");

    function announce(message, type = "info") {
        if (window.SmartProperty?.announce) {
            window.SmartProperty.announce(
                message,
                type
            );
        }

        if (!tenantStatus) {
            return;
        }

        tenantStatus.textContent = message;
        tenantStatus.dataset.statusType = type;
        tenantStatus.setAttribute(
            "role",
            type === "error" ? "alert" : "status"
        );
        tenantStatus.setAttribute(
            "aria-live",
            type === "error"
                ? "assertive"
                : "polite"
        );
    }

    function normalizeText(value) {
        return String(value || "")
            .trim()
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "");
    }

    function debounce(callback, delay = 250) {
        let timeoutId;

        return (...argumentsList) => {
            window.clearTimeout(timeoutId);

            timeoutId = window.setTimeout(() => {
                callback(...argumentsList);
            }, delay);
        };
    }

    /* =====================================================
       Tenant navigation
       ===================================================== */

    const tenantNavigation =
        document.querySelector(
            ".tenant-dashboard-navigation"
        );

    if (tenantNavigation) {
        const currentLink =
            tenantNavigation.querySelector(
                "a[aria-current='page'], a.active"
            );

        currentLink?.scrollIntoView({
            behavior: "auto",
            block: "nearest",
            inline: "center"
        });
    }

    /* =====================================================
       Search and status filtering
       ===================================================== */

    function filterItems() {
        const searchValues = Array.from(
            filterInputs
        )
            .map((input) => normalizeText(input.value))
            .filter(Boolean);

        const selectedStatuses = Array.from(
            statusFilters
        )
            .map((select) =>
                normalizeText(select.value)
            )
            .filter(Boolean);

        let visibleCount = 0;

        searchRows.forEach((item) => {
            const searchableText = normalizeText(
                item.dataset.searchText ||
                item.textContent
            );

            const itemStatus = normalizeText(
                item.dataset.status
            );

            const matchesSearch =
                searchValues.length === 0 ||
                searchValues.every((value) =>
                    searchableText.includes(value)
                );

            const matchesStatus =
                selectedStatuses.length === 0 ||
                selectedStatuses.includes(itemStatus);

            const visible =
                matchesSearch && matchesStatus;

            item.hidden = !visible;

            if (visible) {
                visibleCount += 1;
            }
        });

        const resultCounter =
            document.querySelector(
                "[data-filter-result-count]"
            );

        if (resultCounter) {
            resultCounter.textContent =
                visibleCount === 1
                    ? "1 result"
                    : `${visibleCount} results`;
        }

        const emptyResult =
            document.querySelector(
                "[data-filter-empty]"
            );

        if (emptyResult) {
            emptyResult.hidden =
                visibleCount !== 0;
        }
    }

    const debouncedFilter =
        debounce(filterItems);

    filterInputs.forEach((input) => {
        input.addEventListener(
            "input",
            debouncedFilter
        );
    });

    statusFilters.forEach((select) => {
        select.addEventListener(
            "change",
            filterItems
        );
    });

    /* =====================================================
       Property and unit selectors
       ===================================================== */

    function updateAvailableUnits(
        propertySelector,
        unitSelector
    ) {
        const propertyId =
            propertySelector.value;

        let availableOptions = 0;

        Array.from(unitSelector.options).forEach(
            (option) => {
                if (!option.value) {
                    option.hidden = false;
                    option.disabled = false;
                    return;
                }

                const optionProperty =
                    option.dataset.propertyId;

                const visible =
                    !propertyId ||
                    !optionProperty ||
                    optionProperty === propertyId;

                option.hidden = !visible;
                option.disabled = !visible;

                if (visible) {
                    availableOptions += 1;
                }

                if (
                    option.selected &&
                    !visible
                ) {
                    unitSelector.value = "";
                }
            }
        );

        unitSelector.disabled =
            Boolean(propertyId) &&
            availableOptions === 0;

        if (
            propertyId &&
            availableOptions === 0
        ) {
            announce(
                "No selectable unit was found for this property.",
                "error"
            );
        }
    }

    propertySelectors.forEach(
        (propertySelector) => {
            const form =
                propertySelector.closest("form");

            const unitSelector =
                form?.querySelector(
                    "[data-unit-select]"
                ) ||
                (
                    unitSelectors.length === 1
                        ? unitSelectors[0]
                        : null
                );

            if (!unitSelector) {
                return;
            }

            propertySelector.addEventListener(
                "change",
                () => {
                    updateAvailableUnits(
                        propertySelector,
                        unitSelector
                    );
                }
            );

            updateAvailableUnits(
                propertySelector,
                unitSelector
            );
        }
    );

    /* =====================================================
       Form validation
       ===================================================== */

    tenantForms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (!form.checkValidity()) {
                event.preventDefault();

                const invalidField =
                    form.querySelector(":invalid");

                invalidField?.focus();
                invalidField?.reportValidity();

                announce(
                    "Complete the required fields before submitting.",
                    "error"
                );

                return;
            }

            if (
                form.dataset.submitting === "true"
            ) {
                event.preventDefault();
                return;
            }

            form.dataset.submitting = "true";
            form.setAttribute(
                "aria-busy",
                "true"
            );

            form.querySelectorAll(
                "button[type='submit'], input[type='submit']"
            ).forEach((button) => {
                button.disabled = true;

                if (
                    button instanceof
                    HTMLButtonElement
                ) {
                    button.dataset.originalText =
                        button.textContent;

                    button.textContent =
                        button.dataset.loadingText ||
                        "Submitting…";
                }
            });

            announce(
                "Your request is being submitted."
            );
        });
    });

    /* =====================================================
       Confirmation forms
       ===================================================== */

    document.querySelectorAll(
        "form[data-tenant-confirm]"
    ).forEach((form) => {
        form.addEventListener("submit", (event) => {
            const message =
                form.dataset.tenantConfirm ||
                "Are you sure you want to continue?";

            if (!window.confirm(message)) {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        });
    });

    /* =====================================================
       Priority warnings
       ===================================================== */

    document.querySelectorAll(
        "select[name='priority']"
    ).forEach((prioritySelector) => {
        const warning =
            prioritySelector
                .closest("form")
                ?.querySelector(
                    "[data-priority-warning]"
                );

        function updatePriorityWarning() {
            const priority =
                prioritySelector.value;

            const urgent =
                priority === "urgent" ||
                priority === "emergency";

            if (warning) {
                warning.hidden = !urgent;
            }

            if (priority === "emergency") {
                announce(
                    "For an immediate emergency, leave the dangerous area and contact emergency services. Do not wait for a maintenance response.",
                    "error"
                );
            }
        }

        prioritySelector.addEventListener(
            "change",
            updatePriorityWarning
        );

        updatePriorityWarning();
    });

    /* =====================================================
       Character counters
       ===================================================== */

    document.querySelectorAll(
        "[data-tenant-character-count]"
    ).forEach((counter) => {
        const fieldId =
            counter.dataset.tenantCharacterCount;

        const field =
            document.getElementById(fieldId);

        if (
            !(field instanceof HTMLInputElement) &&
            !(field instanceof HTMLTextAreaElement)
        ) {
            return;
        }

        function updateCounter() {
            const length = field.value.length;
            const maximum =
                field.maxLength > 0
                    ? field.maxLength
                    : null;

            counter.textContent = maximum
                ? `${length} of ${maximum} characters used.`
                : `${length} characters used.`;
        }

        field.addEventListener(
            "input",
            updateCounter
        );

        updateCounter();
    });

    /* =====================================================
       Status controls and details
       ===================================================== */

    document.querySelectorAll(
        "[data-details-toggle]"
    ).forEach((button) => {
        const targetId =
            button.dataset.detailsToggle;

        const target =
            document.getElementById(targetId);

        if (!target) {
            return;
        }

        button.type = "button";
        button.setAttribute(
            "aria-controls",
            targetId
        );

        if (
            !button.hasAttribute("aria-expanded")
        ) {
            button.setAttribute(
                "aria-expanded",
                "false"
            );
        }

        button.addEventListener("click", () => {
            const expanded =
                button.getAttribute(
                    "aria-expanded"
                ) === "true";

            button.setAttribute(
                "aria-expanded",
                String(!expanded)
            );

            target.hidden = expanded;
        });
    });

    /* =====================================================
       Mark notifications read
       ===================================================== */

    document.querySelectorAll(
        "[data-notification-item]"
    ).forEach((notification) => {
        const link = notification.querySelector(
            "a[data-notification-link]"
        );

        const form = notification.querySelector(
            "form[data-mark-read-form]"
        );

        if (!link || !form) {
            return;
        }

        link.addEventListener("click", () => {
            if (
                notification.dataset.read ===
                "true"
            ) {
                return;
            }

            /*
             * The server form remains the authoritative update.
             * JavaScript only improves the visual response.
             */
            notification.classList.remove(
                "unread"
            );

            notification.dataset.read = "true";
        });
    });

    /* =====================================================
       Print controls
       ===================================================== */

    document.querySelectorAll(
        "[data-tenant-print]"
    ).forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            window.print();
        });
    });

    /* =====================================================
       Copy reference numbers
       ===================================================== */

    async function copyText(value) {
        if (
            navigator.clipboard &&
            window.isSecureContext
        ) {
            await navigator.clipboard.writeText(
                value
            );

            return;
        }

        const textarea =
            document.createElement("textarea");

        textarea.value = value;
        textarea.setAttribute(
            "readonly",
            ""
        );

        textarea.style.position = "fixed";
        textarea.style.opacity = "0";

        document.body.appendChild(textarea);
        textarea.select();

        const successful =
            document.execCommand("copy");

        textarea.remove();

        if (!successful) {
            throw new Error(
                "Clipboard copy failed."
            );
        }
    }

    document.querySelectorAll(
        "[data-copy-reference]"
    ).forEach((button) => {
        button.type = "button";

        button.addEventListener(
            "click",
            async () => {
                const reference =
                    button.dataset.copyReference;

                if (!reference) {
                    return;
                }

                try {
                    await copyText(reference);

                    announce(
                        "Reference number copied."
                    );
                } catch (error) {
                    console.error(
                        "Reference could not be copied.",
                        error
                    );

                    announce(
                        "The reference number could not be copied.",
                        "error"
                    );
                }
            }
        );
    });

    /* =====================================================
       Accessible page announcements
       ===================================================== */

    const pageHeading =
        document.querySelector(
            "#main-content h1"
        );

    if (pageHeading) {
        document.title =
            document.title.trim() ||
            `${pageHeading.textContent.trim()} | Smart Property AI`;
    }

    /* =====================================================
       Public tenant API
       ===================================================== */

    window.SmartPropertyTenant = {
        announce,

        filter() {
            filterItems();
        },

        copyReference(reference) {
            return copyText(reference);
        },

        print() {
            window.print();
        }
    };
});