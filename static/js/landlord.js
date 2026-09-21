/*
 * Smart Property AI — Landlord Dashboard
 * File: static/js/landlord.js
 *
 * All selectors are restricted to [data-sp-landlord-dashboard]
 * to prevent conflicts with other pages.
 */

(function () {
    "use strict";

    const dashboard = document.querySelector(
        "[data-sp-landlord-dashboard]"
    );

    /*
     * Stop immediately when the current page is not the
     * landlord dashboard.
     */
    if (!dashboard) {
        return;
    }

    /*
     * Prevent duplicate initialization if this script is
     * accidentally included more than once.
     */
    if (dashboard.dataset.spLandlordReady === "true") {
        return;
    }

    dashboard.dataset.spLandlordReady = "true";

    const announcer = dashboard.querySelector(
        "[data-sp-landlord-announcer]"
    );

    /**
     * Announce dashboard changes to screen readers.
     *
     * @param {string} message
     */
    function announce(message) {
        if (!announcer) {
            return;
        }

        announcer.textContent = "";

        window.setTimeout(function () {
            announcer.textContent = message;
        }, 30);
    }

    /**
     * Initialize the responsive dashboard navigation.
     */
    function initializeNavigation() {
        const toggleButton = dashboard.querySelector(
            "[data-sp-landlord-nav-toggle]"
        );

        const navigationList = dashboard.querySelector(
            "[data-sp-landlord-nav-list]"
        );

        const navigation = toggleButton
            ? toggleButton.closest(".sp-landlord-dashboard__nav")
            : null;

        if (!toggleButton || !navigationList || !navigation) {
            return;
        }

        /**
         * Open or close the mobile navigation.
         *
         * @param {boolean} open
         */
        function setNavigationOpen(open) {
            navigation.classList.toggle("is-open", open);

            toggleButton.setAttribute(
                "aria-expanded",
                String(open)
            );

            announce(
                open
                    ? "Dashboard menu opened."
                    : "Dashboard menu closed."
            );
        }

        toggleButton.addEventListener("click", function () {
            const isOpen =
                toggleButton.getAttribute("aria-expanded") === "true";

            setNavigationOpen(!isOpen);
        });

        navigationList.addEventListener("click", function (event) {
            const selectedLink = event.target.closest("a");

            if (
                selectedLink &&
                window.matchMedia("(max-width: 680px)").matches
            ) {
                setNavigationOpen(false);
            }
        });

        document.addEventListener("keydown", function (event) {
            if (
                event.key === "Escape" &&
                navigation.classList.contains("is-open")
            ) {
                setNavigationOpen(false);
                toggleButton.focus();
            }
        });

        window.addEventListener("resize", function () {
            if (window.innerWidth > 680) {
                setNavigationOpen(false);
            }
        });
    }

    /**
     * Initialize dismissible success and error messages.
     */
    function initializeDismissibleNotices() {
        const notices = dashboard.querySelectorAll(
            "[data-sp-landlord-dismissible]"
        );

        notices.forEach(function (notice) {
            const dismissButton = notice.querySelector(
                "[data-sp-landlord-dismiss]"
            );

            if (!dismissButton) {
                return;
            }

            dismissButton.addEventListener("click", function () {
                notice.remove();
                announce("Message dismissed.");
            });
        });
    }

    /**
     * Convert server dates into the visitor's local date and time.
     */
    function initializeLocalDates() {
        const language =
            document.documentElement.lang ||
            navigator.language ||
            "en";

        let formatter;

        try {
            formatter = new Intl.DateTimeFormat(language, {
                dateStyle: "medium",
                timeStyle: "short"
            });
        } catch (error) {
            console.warn(
                "The browser could not create the date formatter.",
                error
            );

            return;
        }

        const dateElements = dashboard.querySelectorAll(
            "[data-sp-local-date]"
        );

        dateElements.forEach(function (element) {
            const dateValue = element.getAttribute(
                "data-sp-local-date"
            );

            if (!dateValue) {
                return;
            }

            const date = new Date(dateValue);

            if (Number.isNaN(date.getTime())) {
                return;
            }

            element.textContent = formatter.format(date);
            element.setAttribute("title", date.toISOString());
        });
    }

    /**
     * Refresh the dashboard safely.
     */
    function initializeRefreshButton() {
        const refreshButton = dashboard.querySelector(
            "[data-sp-landlord-refresh]"
        );

        if (!refreshButton) {
            return;
        }

        refreshButton.addEventListener("click", function () {
            if (refreshButton.disabled) {
                return;
            }

            refreshButton.disabled = true;
            refreshButton.setAttribute("aria-busy", "true");

            refreshButton.innerHTML = `
                <span aria-hidden="true">↻</span>
                <span>Refreshing…</span>
            `;

            announce("Refreshing landlord dashboard.");

            window.location.reload();
        });
    }

    /**
     * Display the time at which the current dashboard loaded.
     */
    function setUpdatedTime() {
        const updatedElement = dashboard.querySelector(
            "[data-sp-landlord-updated]"
        );

        if (!updatedElement) {
            return;
        }

        const language =
            document.documentElement.lang ||
            navigator.language ||
            "en";

        try {
            const formattedTime = new Intl.DateTimeFormat(
                language,
                {
                    hour: "2-digit",
                    minute: "2-digit"
                }
            ).format(new Date());

            updatedElement.textContent =
                "Updated at " + formattedTime;
        } catch (error) {
            updatedElement.textContent =
                "Updated when this page loaded";
        }
    }

    /**
     * Prevent repeated form submission on forms contained within
     * the landlord dashboard.
     */
    function initializeFormProtection() {
        const forms = dashboard.querySelectorAll("form");

        forms.forEach(function (form) {
            form.addEventListener("submit", function (event) {
                if (!form.checkValidity()) {
                    event.preventDefault();
                    form.reportValidity();

                    announce(
                        "Please correct the highlighted form fields."
                    );

                    return;
                }

                if (form.dataset.spLandlordSubmitting === "true") {
                    event.preventDefault();
                    return;
                }

                form.dataset.spLandlordSubmitting = "true";

                const submitButton = form.querySelector(
                    'button[type="submit"], input[type="submit"]'
                );

                if (!submitButton) {
                    return;
                }

                submitButton.disabled = true;
                submitButton.setAttribute("aria-busy", "true");

                if (submitButton.tagName === "INPUT") {
                    submitButton.dataset.originalValue =
                        submitButton.value;

                    submitButton.value = "Processing…";
                } else {
                    submitButton.dataset.originalText =
                        submitButton.textContent;

                    submitButton.textContent = "Processing…";
                }
            });
        });
    }

    /**
     * Add confirmation handling to dangerous actions.
     *
     * Example:
     * data-sp-landlord-confirm="Delete this property?"
     */
    function initializeConfirmationActions() {
        const confirmationElements = dashboard.querySelectorAll(
            "[data-sp-landlord-confirm]"
        );

        confirmationElements.forEach(function (element) {
            element.addEventListener("click", function (event) {
                const confirmationMessage =
                    element.getAttribute(
                        "data-sp-landlord-confirm"
                    ) ||
                    "Are you sure you want to continue?";

                if (!window.confirm(confirmationMessage)) {
                    event.preventDefault();
                    event.stopPropagation();

                    announce("Action cancelled.");
                }
            });
        });
    }

    /**
     * Initialize client-side filtering for supported lists or tables.
     *
     * Search field:
     * data-sp-landlord-filter="property-list"
     *
     * Filtered element:
     * data-sp-landlord-filter-item="property-list"
     */
    function initializeContentFilters() {
        const filterInputs = dashboard.querySelectorAll(
            "[data-sp-landlord-filter]"
        );

        filterInputs.forEach(function (input) {
            const filterName = input.getAttribute(
                "data-sp-landlord-filter"
            );

            if (!filterName) {
                return;
            }

            const items = dashboard.querySelectorAll(
                `[data-sp-landlord-filter-item="${filterName}"]`
            );

            if (!items.length) {
                return;
            }

            input.addEventListener("input", function () {
                const searchTerm = input.value
                    .trim()
                    .toLocaleLowerCase();

                let visibleCount = 0;

                items.forEach(function (item) {
                    const content = item.textContent
                        .toLocaleLowerCase();

                    const matches =
                        !searchTerm ||
                        content.includes(searchTerm);

                    item.hidden = !matches;

                    if (matches) {
                        visibleCount += 1;
                    }
                });

                announce(
                    visibleCount +
                    (visibleCount === 1
                        ? " result available."
                        : " results available.")
                );
            });
        });
    }

    /**
     * Initialize character counters.
     *
     * Textarea/input:
     * data-sp-landlord-count="description-counter"
     *
     * Counter:
     * data-sp-landlord-count-output="description-counter"
     */
    function initializeCharacterCounters() {
        const fields = dashboard.querySelectorAll(
            "[data-sp-landlord-count]"
        );

        fields.forEach(function (field) {
            const counterName = field.getAttribute(
                "data-sp-landlord-count"
            );

            if (!counterName) {
                return;
            }

            const output = dashboard.querySelector(
                `[data-sp-landlord-count-output="${counterName}"]`
            );

            if (!output) {
                return;
            }

            function updateCounter() {
                const currentLength = field.value.length;
                const maximumLength = field.maxLength;

                output.textContent =
                    maximumLength > 0
                        ? `${currentLength} / ${maximumLength}`
                        : String(currentLength);
            }

            field.addEventListener("input", updateCounter);
            updateCounter();
        });
    }

    /**
     * Show selected filenames for dashboard file inputs.
     *
     * Input:
     * data-sp-landlord-file-input="document-file"
     *
     * Output:
     * data-sp-landlord-file-output="document-file"
     */
    function initializeFileInputs() {
        const fileInputs = dashboard.querySelectorAll(
            "[data-sp-landlord-file-input]"
        );

        fileInputs.forEach(function (input) {
            const inputName = input.getAttribute(
                "data-sp-landlord-file-input"
            );

            if (!inputName) {
                return;
            }

            const output = dashboard.querySelector(
                `[data-sp-landlord-file-output="${inputName}"]`
            );

            if (!output) {
                return;
            }

            input.addEventListener("change", function () {
                const selectedFiles = Array.from(
                    input.files || []
                );

                if (!selectedFiles.length) {
                    output.textContent = "No file selected.";
                    return;
                }

                output.textContent = selectedFiles
                    .map(function (file) {
                        return file.name;
                    })
                    .join(", ");

                announce(
                    selectedFiles.length === 1
                        ? "One file selected."
                        : `${selectedFiles.length} files selected.`
                );
            });
        });
    }

    /**
     * Initialize copy-to-clipboard controls.
     *
     * Button:
     * data-sp-landlord-copy="property-reference"
     *
     * Source:
     * data-sp-landlord-copy-source="property-reference"
     */
    function initializeClipboardButtons() {
        const copyButtons = dashboard.querySelectorAll(
            "[data-sp-landlord-copy]"
        );

        copyButtons.forEach(function (button) {
            button.addEventListener("click", async function () {
                const copyName = button.getAttribute(
                    "data-sp-landlord-copy"
                );

                const source = dashboard.querySelector(
                    `[data-sp-landlord-copy-source="${copyName}"]`
                );

                if (!source) {
                    return;
                }

                const text =
                    source.value !== undefined
                        ? source.value
                        : source.textContent;

                try {
                    await navigator.clipboard.writeText(
                        text.trim()
                    );

                    announce("Copied to clipboard.");
                } catch (error) {
                    console.warn(
                        "Clipboard access was unavailable.",
                        error
                    );

                    announce(
                        "The information could not be copied."
                    );
                }
            });
        });
    }

    /**
     * Initialize print buttons.
     */
    function initializePrintButtons() {
        const printButtons = dashboard.querySelectorAll(
            "[data-sp-landlord-print]"
        );

        printButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                window.print();
            });
        });
    }

    /**
     * Initialize the dashboard after the HTML is available.
     */
    function initializeLandlordDashboard() {
        initializeNavigation();
        initializeDismissibleNotices();
        initializeLocalDates();
        initializeRefreshButton();
        initializeFormProtection();
        initializeConfirmationActions();
        initializeContentFilters();
        initializeCharacterCounters();
        initializeFileInputs();
        initializeClipboardButtons();
        initializePrintButtons();
        setUpdatedTime();
    }

    initializeLandlordDashboard();
})();