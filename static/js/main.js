"use strict";

/*
|--------------------------------------------------------------------------
| Smart Property AI
|--------------------------------------------------------------------------
| Navigation, accessibility, language and voice controls.
|--------------------------------------------------------------------------
*/

document.addEventListener("DOMContentLoaded", () => {
    initializeNavigation();
    initializeTextSizeControls();
    initializeContrastControl();
    initializeReadAloud();
    initializeLanguageSelector();
    initializeHeroVoiceButton();
    initializeExternalLinkSecurity();
});


/* ==========================================================================
   Helpers
   ========================================================================== */

function getStoredValue(key, fallback = null) {
    try {
        const value = localStorage.getItem(key);
        return value === null ? fallback : value;
    } catch (error) {
        return fallback;
    }
}


function setStoredValue(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch (error) {
        console.warn("Browser storage is unavailable.");
    }
}


function updateStatus(message) {
    const statusElement = document.getElementById("voice-status");

    if (statusElement) {
        statusElement.textContent = message;
    }
}


/* ==========================================================================
   Responsive navigation
   ========================================================================== */

function initializeNavigation() {
    const navigationToggle = document.getElementById(
        "navigation-toggle"
    );

    const primaryNavigation = document.getElementById(
        "primary-navigation"
    );

    if (!navigationToggle || !primaryNavigation) {
        return;
    }

    const closeNavigation = () => {
        navigationToggle.setAttribute(
            "aria-expanded",
            "false"
        );

        navigationToggle.setAttribute(
            "aria-label",
            "Open navigation menu"
        );

        primaryNavigation.classList.remove("is-open");
        document.body.classList.remove("navigation-open");
    };

    const openNavigation = () => {
        navigationToggle.setAttribute(
            "aria-expanded",
            "true"
        );

        navigationToggle.setAttribute(
            "aria-label",
            "Close navigation menu"
        );

        primaryNavigation.classList.add("is-open");
        document.body.classList.add("navigation-open");
    };

    navigationToggle.addEventListener("click", () => {
        const isExpanded =
            navigationToggle.getAttribute("aria-expanded") === "true";

        if (isExpanded) {
            closeNavigation();
        } else {
            openNavigation();
        }
    });

    primaryNavigation.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", closeNavigation);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeNavigation();
            navigationToggle.focus();
        }
    });

    document.addEventListener("click", (event) => {
        const clickedInsideNavigation =
            primaryNavigation.contains(event.target);

        const clickedToggle =
            navigationToggle.contains(event.target);

        if (!clickedInsideNavigation && !clickedToggle) {
            closeNavigation();
        }
    });

    window.addEventListener("resize", () => {
        if (window.innerWidth > 1050) {
            closeNavigation();
        }
    });
}


/* ==========================================================================
   Text-size controls
   ========================================================================== */

function initializeTextSizeControls() {
    const decreaseButton = document.getElementById(
        "decrease-text"
    );

    const increaseButton = document.getElementById(
        "increase-text"
    );

    const availableSizes = [
        "normal",
        "large",
        "extra-large"
    ];

    let currentSize = getStoredValue(
        "smartPropertyTextSize",
        "normal"
    );

    if (!availableSizes.includes(currentSize)) {
        currentSize = "normal";
    }

    const applyTextSize = () => {
        document.body.classList.remove(
            "text-size-large",
            "text-size-extra-large"
        );

        if (currentSize === "large") {
            document.body.classList.add(
                "text-size-large"
            );
        }

        if (currentSize === "extra-large") {
            document.body.classList.add(
                "text-size-extra-large"
            );
        }

        setStoredValue(
            "smartPropertyTextSize",
            currentSize
        );
    };

    applyTextSize();

    if (increaseButton) {
        increaseButton.addEventListener("click", () => {
            const currentIndex =
                availableSizes.indexOf(currentSize);

            const nextIndex = Math.min(
                currentIndex + 1,
                availableSizes.length - 1
            );

            currentSize = availableSizes[nextIndex];
            applyTextSize();
        });
    }

    if (decreaseButton) {
        decreaseButton.addEventListener("click", () => {
            const currentIndex =
                availableSizes.indexOf(currentSize);

            const nextIndex = Math.max(
                currentIndex - 1,
                0
            );

            currentSize = availableSizes[nextIndex];
            applyTextSize();
        });
    }
}


/* ==========================================================================
   High-contrast control
   ========================================================================== */

function initializeContrastControl() {
    const contrastButton = document.getElementById(
        "contrast-toggle"
    );

    if (!contrastButton) {
        return;
    }

    const storedContrast = getStoredValue(
        "smartPropertyHighContrast",
        "false"
    );

    const applyContrast = (enabled) => {
        document.body.classList.toggle(
            "high-contrast",
            enabled
        );

        contrastButton.setAttribute(
            "aria-pressed",
            String(enabled)
        );

        setStoredValue(
            "smartPropertyHighContrast",
            String(enabled)
        );
    };

    applyContrast(storedContrast === "true");

    contrastButton.addEventListener("click", () => {
        const enabled =
            !document.body.classList.contains(
                "high-contrast"
            );

        applyContrast(enabled);
    });
}


/* ==========================================================================
   Read page aloud
   ========================================================================== */

function initializeReadAloud() {
    const readButton = document.getElementById(
        "read-page-button"
    );

    const mainContent = document.getElementById(
        "main-content"
    );

    if (!readButton || !mainContent) {
        return;
    }

    if (!("speechSynthesis" in window)) {
        readButton.disabled = true;
        readButton.title =
            "Speech output is not supported by this browser.";
        return;
    }

    const stopReading = () => {
        window.speechSynthesis.cancel();

        readButton.setAttribute(
            "aria-pressed",
            "false"
        );

        readButton.textContent = "Read aloud";
        updateStatus("Reading stopped.");
    };

    const beginReading = () => {
        const readableText = mainContent.innerText
            .replace(/\s+/g, " ")
            .trim();

        if (!readableText) {
            updateStatus("There is no page content to read.");
            return;
        }

        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(
            readableText
        );

        const languageSelect = document.getElementById(
            "language-select"
        );

        const selectedLanguage = languageSelect
            ? languageSelect.value
            : document.documentElement.lang || "en";

        const languageMap = {
            en: "en-US",
            de: "de-DE",
            fr: "fr-FR",
            es: "es-ES",
            it: "it-IT",
            pt: "pt-PT",
            ar: "ar-SA",
            tr: "tr-TR",
            pl: "pl-PL",
            uk: "uk-UA"
        };

        utterance.lang =
            languageMap[selectedLanguage] || selectedLanguage;

        utterance.rate = 0.95;
        utterance.pitch = 1;
        utterance.volume = 1;

        utterance.onstart = () => {
            readButton.setAttribute(
                "aria-pressed",
                "true"
            );

            readButton.textContent = "Stop reading";
            updateStatus("The page is being read aloud.");
        };

        utterance.onend = () => {
            readButton.setAttribute(
                "aria-pressed",
                "false"
            );

            readButton.textContent = "Read aloud";
            updateStatus("Reading completed.");
        };

        utterance.onerror = (event) => {
            readButton.setAttribute(
                "aria-pressed",
                "false"
            );

            readButton.textContent = "Read aloud";

            if (event.error !== "canceled") {
                updateStatus(
                    "The page could not be read aloud."
                );
            }
        };

        window.speechSynthesis.speak(utterance);
    };

    readButton.addEventListener("click", () => {
        const isReading =
            readButton.getAttribute("aria-pressed") === "true";

        if (isReading) {
            stopReading();
        } else {
            beginReading();
        }
    });

    window.addEventListener(
        "beforeunload",
        () => window.speechSynthesis.cancel()
    );
}


/* ==========================================================================
   Language selector
   ========================================================================== */

function initializeLanguageSelector() {
    const languageSelect = document.getElementById(
        "language-select"
    );

    if (!languageSelect) {
        return;
    }

    languageSelect.addEventListener("change", async () => {
        const selectedLanguage = languageSelect.value;

        languageSelect.disabled = true;

        try {
            const response = await fetch(
                "/api/language",
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    credentials: "same-origin",
                    body: JSON.stringify({
                        language: selectedLanguage
                    })
                }
            );

            const result = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(
                    result.error ||
                    "The language could not be changed."
                );
            }

            document.documentElement.lang =
                result.language;

            setStoredValue(
                "smartPropertyLanguage",
                result.language
            );

            window.location.reload();
        } catch (error) {
            console.error(error);

            updateStatus(
                "The selected language could not be saved."
            );

            languageSelect.disabled = false;
        }
    });
}


/* ==========================================================================
   Hero voice assistant
   ========================================================================== */

function initializeHeroVoiceButton() {
    const voiceButton = document.getElementById(
        "hero-voice-button"
    );

    if (!voiceButton) {
        return;
    }

    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        voiceButton.addEventListener("click", () => {
            updateStatus(
                "Voice recognition is not supported by this browser. " +
                "You can continue using the written search form."
            );
        });

        return;
    }

    const recognition = new SpeechRecognition();

    recognition.continuous = false;
    recognition.interimResults = false;

    const languageSelect = document.getElementById(
        "language-select"
    );

    const languageMap = {
        en: "en-US",
        de: "de-DE",
        fr: "fr-FR",
        es: "es-ES",
        it: "it-IT",
        pt: "pt-PT",
        ar: "ar-SA",
        tr: "tr-TR",
        pl: "pl-PL",
        uk: "uk-UA"
    };

    voiceButton.addEventListener("click", () => {
        const isListening =
            voiceButton.getAttribute("aria-pressed") === "true";

        if (isListening) {
            recognition.stop();
            return;
        }

        const selectedLanguage = languageSelect
            ? languageSelect.value
            : "en";

        recognition.lang =
            languageMap[selectedLanguage] || selectedLanguage;

        try {
            recognition.start();
        } catch (error) {
            updateStatus(
                "Voice recognition is already active."
            );
        }
    });

    recognition.onstart = () => {
        voiceButton.setAttribute(
            "aria-pressed",
            "true"
        );

        voiceButton.innerHTML =
            '<span aria-hidden="true">⏹</span> Stop listening';

        updateStatus(
            "Listening. Please describe the apartment you need."
        );
    };

    recognition.onresult = (event) => {
        const transcript =
            event.results[0][0].transcript.trim();

        const locationInput = document.getElementById(
            "search-location"
        );

        if (locationInput) {
            locationInput.value = transcript;
            locationInput.focus();
        }

        updateStatus(
            `We heard: ${transcript}. ` +
            "Please review the information before searching."
        );
    };

    recognition.onerror = (event) => {
        const errorMessages = {
            "not-allowed":
                "Microphone permission was not granted.",
            "no-speech":
                "No speech was detected. Please try again.",
            "audio-capture":
                "No working microphone was detected.",
            "network":
                "Voice recognition could not reach its service."
        };

        updateStatus(
            errorMessages[event.error] ||
            "Voice recognition could not complete the request."
        );
    };

    recognition.onend = () => {
        voiceButton.setAttribute(
            "aria-pressed",
            "false"
        );

        voiceButton.innerHTML =
            '<span aria-hidden="true">🎤</span> Use voice assistance';
    };
}


/* ==========================================================================
   External-link security
   ========================================================================== */

function initializeExternalLinkSecurity() {
    document.querySelectorAll(
        'a[target="_blank"]'
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
}