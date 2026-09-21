/*
 * Smart Property AI
 * Main frontend functionality
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const root = document.documentElement;
    const body = document.body;

    const STORAGE_KEYS = {
        theme: "smart_property_theme",
        contrast: "smart_property_contrast",
        fontSize: "smart_property_font_size",
        reducedMotion: "smart_property_reduced_motion"
    };

    /* =====================================================
       Safe storage helpers
       ===================================================== */

    function getStoredValue(key, fallback = null) {
        try {
            return localStorage.getItem(key) ?? fallback;
        } catch (error) {
            console.warn(
                `Could not read ${key} from local storage.`,
                error
            );

            return fallback;
        }
    }

    function setStoredValue(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (error) {
            console.warn(
                `Could not save ${key} to local storage.`,
                error
            );
        }
    }

    function removeStoredValue(key) {
        try {
            localStorage.removeItem(key);
        } catch (error) {
            console.warn(
                `Could not remove ${key} from local storage.`,
                error
            );
        }
    }

    /* =====================================================
       Live announcements
       ===================================================== */

    function getGlobalStatusRegion() {
        let region = document.querySelector(
            "[data-global-status]"
        );

        if (region) {
            return region;
        }

        region = document.createElement("div");
        region.className = "sr-only";
        region.dataset.globalStatus = "";
        region.setAttribute("role", "status");
        region.setAttribute("aria-live", "polite");
        region.setAttribute("aria-atomic", "true");

        body.appendChild(region);

        return region;
    }

    function announce(message, type = "info") {
        const region = getGlobalStatusRegion();

        region.setAttribute(
            "role",
            type === "error" ? "alert" : "status"
        );

        region.setAttribute(
            "aria-live",
            type === "error" ? "assertive" : "polite"
        );

        /*
         * Clear the region first so repeated messages are announced.
         */
        region.textContent = "";

        window.setTimeout(() => {
            region.textContent = message;
        }, 50);
    }

    /* =====================================================
       Mobile navigation
       ===================================================== */

    const menuButtons = document.querySelectorAll(
        "[data-menu-toggle], .menu-toggle, .mobile-menu-toggle"
    );

    function findNavigation(button) {
        const controls = button.getAttribute("aria-controls");

        if (controls) {
            const controlledNavigation =
                document.getElementById(controls);

            if (controlledNavigation) {
                return controlledNavigation;
            }
        }

        const navigationContainer = button.closest(
            ".navbar, .nav-container, header"
        );

        return (
            navigationContainer?.querySelector(
                ".nav-links, .navbar-nav, .navigation-menu"
            ) ||
            document.querySelector(
                ".nav-links, .navbar-nav, .navigation-menu"
            )
        );
    }

    function closeNavigation(button, navigation) {
        button.setAttribute("aria-expanded", "false");

        navigation.classList.remove(
            "is-open",
            "active"
        );

        body.classList.remove("navigation-open");
    }

    function openNavigation(button, navigation) {
        button.setAttribute("aria-expanded", "true");
        navigation.classList.add("is-open");
        body.classList.add("navigation-open");
    }

    menuButtons.forEach((button, index) => {
        const navigation = findNavigation(button);

        if (!navigation) {
            return;
        }

        if (!navigation.id) {
            navigation.id = `main-navigation-${index + 1}`;
        }

        button.type = "button";
        button.setAttribute(
            "aria-controls",
            navigation.id
        );

        if (!button.hasAttribute("aria-expanded")) {
            button.setAttribute("aria-expanded", "false");
        }

        button.addEventListener("click", () => {
            const expanded =
                button.getAttribute("aria-expanded") === "true";

            if (expanded) {
                closeNavigation(button, navigation);
            } else {
                openNavigation(button, navigation);
            }
        });

        navigation.addEventListener("click", (event) => {
            if (
                event.target.closest("a") &&
                window.matchMedia("(max-width: 991px)").matches
            ) {
                closeNavigation(button, navigation);
            }
        });

        document.addEventListener("click", (event) => {
            if (
                button.getAttribute("aria-expanded") !== "true"
            ) {
                return;
            }

            if (
                !button.contains(event.target) &&
                !navigation.contains(event.target)
            ) {
                closeNavigation(button, navigation);
            }
        });

        document.addEventListener("keydown", (event) => {
            if (
                event.key === "Escape" &&
                button.getAttribute("aria-expanded") === "true"
            ) {
                closeNavigation(button, navigation);
                button.focus();
            }
        });
    });

    window.addEventListener("resize", () => {
        if (!window.matchMedia("(min-width: 992px)").matches) {
            return;
        }

        menuButtons.forEach((button) => {
            const navigation = findNavigation(button);

            if (navigation) {
                closeNavigation(button, navigation);
            }
        });
    });

    /* =====================================================
       Dropdown menus
       ===================================================== */

    const dropdownButtons = document.querySelectorAll(
        "[data-dropdown-toggle]"
    );

    function closeAllDropdowns(exceptButton = null) {
        dropdownButtons.forEach((button) => {
            if (button === exceptButton) {
                return;
            }

            const menuId =
                button.getAttribute("aria-controls");

            const menu = menuId
                ? document.getElementById(menuId)
                : null;

            button.setAttribute("aria-expanded", "false");

            if (menu) {
                menu.hidden = true;
                menu.classList.remove("is-open");
            }
        });
    }

    dropdownButtons.forEach((button, index) => {
        let menuId = button.getAttribute("aria-controls");

        let menu = menuId
            ? document.getElementById(menuId)
            : button.nextElementSibling;

        if (!menu) {
            return;
        }

        if (!menu.id) {
            menu.id = `dropdown-menu-${index + 1}`;
        }

        menuId = menu.id;

        button.type = "button";
        button.setAttribute("aria-controls", menuId);
        button.setAttribute("aria-expanded", "false");

        menu.hidden = true;

        button.addEventListener("click", () => {
            const expanded =
                button.getAttribute("aria-expanded") === "true";

            closeAllDropdowns(button);

            button.setAttribute(
                "aria-expanded",
                String(!expanded)
            );

            menu.hidden = expanded;
            menu.classList.toggle("is-open", !expanded);
        });

        menu.addEventListener("keydown", (event) => {
            if (event.key !== "Escape") {
                return;
            }

            menu.hidden = true;
            menu.classList.remove("is-open");
            button.setAttribute("aria-expanded", "false");
            button.focus();
        });
    });

    document.addEventListener("click", (event) => {
        if (
            !event.target.closest("[data-dropdown-toggle]") &&
            !event.target.closest(".dropdown-menu")
        ) {
            closeAllDropdowns();
        }
    });

    /* =====================================================
       Theme controls
       ===================================================== */

    const themeButtons = document.querySelectorAll(
        "[data-theme-toggle]"
    );

    function preferredTheme() {
        const storedTheme = getStoredValue(
            STORAGE_KEYS.theme
        );

        if (
            storedTheme === "light" ||
            storedTheme === "dark"
        ) {
            return storedTheme;
        }

        return window.matchMedia(
            "(prefers-color-scheme: dark)"
        ).matches
            ? "dark"
            : "light";
    }

    function applyTheme(theme, save = true) {
        const selectedTheme =
            theme === "dark" ? "dark" : "light";

        root.dataset.theme = selectedTheme;
        root.style.colorScheme = selectedTheme;

        themeButtons.forEach((button) => {
            const isDark = selectedTheme === "dark";

            button.setAttribute(
                "aria-pressed",
                String(isDark)
            );

            button.setAttribute(
                "aria-label",
                isDark
                    ? "Switch to light mode"
                    : "Switch to dark mode"
            );

            const label = button.querySelector(
                "[data-theme-label]"
            );

            if (label) {
                label.textContent = isDark
                    ? "Light mode"
                    : "Dark mode";
            }

            const icon = button.querySelector(
                "[data-theme-icon]"
            );

            if (icon) {
                icon.textContent = isDark ? "☀️" : "🌙";
            }
        });

        if (save) {
            setStoredValue(
                STORAGE_KEYS.theme,
                selectedTheme
            );
        }
    }

    applyTheme(preferredTheme(), false);

    themeButtons.forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            const currentTheme =
                root.dataset.theme || "light";

            const nextTheme =
                currentTheme === "dark"
                    ? "light"
                    : "dark";

            applyTheme(nextTheme);
            announce(`${nextTheme} theme enabled.`);
        });
    });

    /* =====================================================
       High-contrast controls
       ===================================================== */

    const contrastButtons = document.querySelectorAll(
        "[data-contrast-toggle]"
    );

    function applyContrast(enabled, save = true) {
        root.classList.toggle(
            "high-contrast",
            enabled
        );

        body.classList.toggle(
            "high-contrast",
            enabled
        );

        root.dataset.contrast =
            enabled ? "high" : "normal";

        contrastButtons.forEach((button) => {
            button.setAttribute(
                "aria-pressed",
                String(enabled)
            );
        });

        if (save) {
            setStoredValue(
                STORAGE_KEYS.contrast,
                enabled ? "high" : "normal"
            );
        }
    }

    const savedContrast =
        getStoredValue(STORAGE_KEYS.contrast) === "high";

    applyContrast(savedContrast, false);

    contrastButtons.forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            const enabled =
                root.dataset.contrast !== "high";

            applyContrast(enabled);

            announce(
                enabled
                    ? "High contrast enabled."
                    : "High contrast disabled."
            );
        });
    });

    /* =====================================================
       Font-size controls
       ===================================================== */

    const increaseTextButtons = document.querySelectorAll(
        "[data-font-increase], [data-text-increase]"
    );

    const decreaseTextButtons = document.querySelectorAll(
        "[data-font-decrease], [data-text-decrease]"
    );

    const resetTextButtons = document.querySelectorAll(
        "[data-font-reset], [data-text-reset]"
    );

    const fontSizes = [
        "normal",
        "large",
        "extra-large"
    ];

    function applyFontSize(size, save = true) {
        const selectedSize = fontSizes.includes(size)
            ? size
            : "normal";

        if (selectedSize === "normal") {
            delete root.dataset.fontSize;
        } else {
            root.dataset.fontSize = selectedSize;
        }

        if (save) {
            setStoredValue(
                STORAGE_KEYS.fontSize,
                selectedSize
            );
        }
    }

    function currentFontSizeIndex() {
        const current =
            root.dataset.fontSize || "normal";

        const index = fontSizes.indexOf(current);

        return index >= 0 ? index : 0;
    }

    applyFontSize(
        getStoredValue(
            STORAGE_KEYS.fontSize,
            "normal"
        ),
        false
    );

    increaseTextButtons.forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            const nextIndex = Math.min(
                currentFontSizeIndex() + 1,
                fontSizes.length - 1
            );

            applyFontSize(fontSizes[nextIndex]);
            announce("Text size increased.");
        });
    });

    decreaseTextButtons.forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            const nextIndex = Math.max(
                currentFontSizeIndex() - 1,
                0
            );

            applyFontSize(fontSizes[nextIndex]);
            announce("Text size decreased.");
        });
    });

    resetTextButtons.forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            applyFontSize("normal");
            announce("Text size reset.");
        });
    });

    /* =====================================================
       Reduced-motion controls
       ===================================================== */

    const motionButtons = document.querySelectorAll(
        "[data-motion-toggle]"
    );

    function applyReducedMotion(enabled, save = true) {
        root.classList.toggle(
            "reduce-motion",
            enabled
        );

        body.classList.toggle(
            "reduce-motion",
            enabled
        );

        root.dataset.reduceMotion = String(enabled);

        motionButtons.forEach((button) => {
            button.setAttribute(
                "aria-pressed",
                String(enabled)
            );
        });

        if (save) {
            setStoredValue(
                STORAGE_KEYS.reducedMotion,
                String(enabled)
            );
        }
    }

    const systemReducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;

    const savedMotion = getStoredValue(
        STORAGE_KEYS.reducedMotion
    );

    applyReducedMotion(
        savedMotion === null
            ? systemReducedMotion
            : savedMotion === "true",
        false
    );

    motionButtons.forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            const enabled =
                root.dataset.reduceMotion !== "true";

            applyReducedMotion(enabled);

            announce(
                enabled
                    ? "Reduced motion enabled."
                    : "Reduced motion disabled."
            );
        });
    });

    /* =====================================================
       Reset accessibility settings
       ===================================================== */

    const resetAccessibilityButtons =
        document.querySelectorAll(
            "[data-accessibility-reset]"
        );

    resetAccessibilityButtons.forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            removeStoredValue(STORAGE_KEYS.theme);
            removeStoredValue(STORAGE_KEYS.contrast);
            removeStoredValue(STORAGE_KEYS.fontSize);
            removeStoredValue(
                STORAGE_KEYS.reducedMotion
            );

            applyTheme(preferredTheme(), false);
            applyContrast(false, false);
            applyFontSize("normal", false);
            applyReducedMotion(
                systemReducedMotion,
                false
            );

            announce(
                "Accessibility settings reset."
            );
        });
    });

    /* =====================================================
       Dismissible messages
       ===================================================== */

    const dismissButtons = document.querySelectorAll(
        "[data-dismiss-alert], .alert-close"
    );

    dismissButtons.forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            const alert = button.closest(
                ".alert, .notification, .toast"
            );

            if (!alert) {
                return;
            }

            alert.remove();
            announce("Message dismissed.");
        });
    });

    document.querySelectorAll(
        "[data-auto-dismiss]"
    ).forEach((alert) => {
        const delay = Number.parseInt(
            alert.dataset.autoDismiss || "5000",
            10
        );

        if (!Number.isFinite(delay) || delay < 0) {
            return;
        }

        window.setTimeout(() => {
            if (alert.isConnected) {
                alert.remove();
            }
        }, delay);
    });

    /* =====================================================
       Password visibility
       ===================================================== */

    const passwordButtons = document.querySelectorAll(
        "[data-password-toggle]"
    );

    passwordButtons.forEach((button) => {
        const targetReference =
            button.dataset.passwordToggle;

        const input =
            document.getElementById(targetReference) ||
            document.querySelector(targetReference);

        if (
            !(input instanceof HTMLInputElement)
        ) {
            return;
        }

        button.type = "button";
        button.setAttribute("aria-pressed", "false");

        button.addEventListener("click", () => {
            const showPassword =
                input.type === "password";

            input.type = showPassword
                ? "text"
                : "password";

            button.setAttribute(
                "aria-pressed",
                String(showPassword)
            );

            button.setAttribute(
                "aria-label",
                showPassword
                    ? "Hide password"
                    : "Show password"
            );

            const label = button.querySelector(
                "[data-password-label]"
            );

            if (label) {
                label.textContent = showPassword
                    ? "Hide"
                    : "Show";
            }

            input.focus();
        });
    });

    /* =====================================================
       Confirm actions
       ===================================================== */

    document.querySelectorAll(
        "[data-confirm]"
    ).forEach((element) => {
        element.addEventListener("click", (event) => {
            const message =
                element.dataset.confirm ||
                "Are you sure you want to continue?";

            if (!window.confirm(message)) {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        });
    });

    /* =====================================================
       Disable forms during submission
       ===================================================== */

    document.querySelectorAll(
        "form[data-disable-on-submit]"
    ).forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (!form.checkValidity()) {
                return;
            }

            if (form.dataset.submitting === "true") {
                event.preventDefault();
                return;
            }

            form.dataset.submitting = "true";
            form.setAttribute("aria-busy", "true");

            form.querySelectorAll(
                "button[type='submit'], input[type='submit']"
            ).forEach((button) => {
                button.disabled = true;

                if (button instanceof HTMLButtonElement) {
                    button.dataset.originalText =
                        button.textContent;

                    button.textContent =
                        button.dataset.loadingText ||
                        "Please wait…";
                }
            });
        });
    });

    /* =====================================================
       Character counters
       ===================================================== */

    document.querySelectorAll(
        "[data-character-count]"
    ).forEach((counter) => {
        const targetReference =
            counter.dataset.characterCount;

        const field =
            document.getElementById(targetReference);

        if (
            !(field instanceof HTMLInputElement) &&
            !(field instanceof HTMLTextAreaElement)
        ) {
            return;
        }

        function updateCounter() {
            const length = field.value.length;
            const maximum = field.maxLength;

            counter.textContent =
                maximum > 0
                    ? `${length} of ${maximum} characters used.`
                    : `${length} characters used.`;
        }

        field.addEventListener("input", updateCounter);
        updateCounter();
    });

    /* =====================================================
       Date validation
       ===================================================== */

    document.querySelectorAll(
        "input[type='date'][data-future-date]"
    ).forEach((input) => {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(
            today.getMonth() + 1
        ).padStart(2, "0");

        const day = String(
            today.getDate()
        ).padStart(2, "0");

        const minimumDate = `${year}-${month}-${day}`;

        if (!input.min) {
            input.min = minimumDate;
        }

        input.addEventListener("change", () => {
            if (
                input.value &&
                input.value < minimumDate
            ) {
                input.setCustomValidity(
                    "Select today or a future date."
                );
            } else {
                input.setCustomValidity("");
            }
        });
    });

    /* =====================================================
       Dialog controls
       ===================================================== */

    document.querySelectorAll(
        "[data-dialog-open]"
    ).forEach((button) => {
        const dialogId = button.dataset.dialogOpen;
        const dialog = document.getElementById(dialogId);

        if (!(dialog instanceof HTMLDialogElement)) {
            return;
        }

        button.type = "button";

        button.addEventListener("click", () => {
            dialog.showModal();
        });
    });

    document.querySelectorAll(
        "[data-dialog-close]"
    ).forEach((button) => {
        const dialog = button.closest("dialog");

        if (!(dialog instanceof HTMLDialogElement)) {
            return;
        }

        button.type = "button";

        button.addEventListener("click", () => {
            dialog.close();
        });
    });

    document.querySelectorAll("dialog").forEach((dialog) => {
        dialog.addEventListener("click", (event) => {
            if (event.target === dialog) {
                dialog.close();
            }
        });
    });

    /* =====================================================
       Smooth internal links
       ===================================================== */

    document.querySelectorAll(
        "a[href^='#']:not([href='#'])"
    ).forEach((link) => {
        link.addEventListener("click", (event) => {
            const targetId =
                link.getAttribute("href").slice(1);

            const target =
                document.getElementById(targetId);

            if (!target) {
                return;
            }

            event.preventDefault();

            target.scrollIntoView({
                behavior:
                    root.dataset.reduceMotion === "true"
                        ? "auto"
                        : "smooth",
                block: "start"
            });

            if (!target.hasAttribute("tabindex")) {
                target.setAttribute("tabindex", "-1");
            }

            target.focus({
                preventScroll: true
            });

            window.history.pushState(
                null,
                "",
                `#${targetId}`
            );
        });
    });

    /* =====================================================
       External-link accessibility
       ===================================================== */

    document.querySelectorAll(
        "a[target='_blank']"
    ).forEach((link) => {
        const currentRel = new Set(
            (link.getAttribute("rel") || "")
                .split(/\s+/)
                .filter(Boolean)
        );

        currentRel.add("noopener");
        currentRel.add("noreferrer");

        link.setAttribute(
            "rel",
            Array.from(currentRel).join(" ")
        );
    });

    /* =====================================================
       Global API
       ===================================================== */

    window.SmartProperty = {
        announce,

        setTheme(theme) {
            applyTheme(theme);
        },

        enableHighContrast(enabled = true) {
            applyContrast(Boolean(enabled));
        },

        setFontSize(size) {
            applyFontSize(size);
        },

        setReducedMotion(enabled = true) {
            applyReducedMotion(Boolean(enabled));
        },

        resetAccessibility() {
            removeStoredValue(STORAGE_KEYS.theme);
            removeStoredValue(STORAGE_KEYS.contrast);
            removeStoredValue(STORAGE_KEYS.fontSize);
            removeStoredValue(
                STORAGE_KEYS.reducedMotion
            );

            applyTheme(preferredTheme(), false);
            applyContrast(false, false);
            applyFontSize("normal", false);
            applyReducedMotion(
                systemReducedMotion,
                false
            );
        }
    };
});
//Backtop or scroll to top
const scrollButton = document.getElementById("scroll-button");
scrollButton.addEventListener('click', function() {
    document.querySelector('.scroll-container').scrollTo({
        top: 0,
        behavior: 'smooth'
    });
});

//3 mins time out

let inactivityTime = function () {
    let time;

    window.onload = resetTimer;
    document.onmousemove = resetTimer;
    document.onkeypress = resetTimer;
    document.ontouchstart = resetTimer;

    function logout() {
        window.location.href = '/logout';
    }

    function resetTimer() {
        clearTimeout(time);
        time = setTimeout(logout, 5000);
        console.log("interaction detected")
    }
};

inactivityTime();
