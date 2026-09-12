/*
 * Smart Property AI
 * Accessible text-to-speech output
 *
 * Uses the browser SpeechSynthesis API.
 *
 * Supported attributes:
 *   data-speech-target="element-id"
 *   data-speech-text="Text to read"
 *   data-speech-stop
 *   data-speech-pause
 *   data-speech-resume
 *   data-speech-status
 *
 * Optional attributes:
 *   data-speech-rate="1"
 *   data-speech-pitch="1"
 *   data-speech-volume="1"
 *   data-speech-language="en-US"
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const speechSynthesisSupported =
        "speechSynthesis" in window &&
        "SpeechSynthesisUtterance" in window;

    const speechButtons = document.querySelectorAll(
        "[data-speech-target], [data-speech-text]"
    );

    const stopButtons = document.querySelectorAll("[data-speech-stop]");
    const pauseButtons = document.querySelectorAll("[data-speech-pause]");
    const resumeButtons = document.querySelectorAll("[data-speech-resume]");

    const statusRegions = document.querySelectorAll(
        "[data-speech-status], #speech-status"
    );

    let currentButton = null;
    let currentUtterance = null;
    let availableVoices = [];

    const messages = {
        ready: "Text-to-speech is ready.",
        unsupported:
            "Text-to-speech is not supported by this browser.",
        speaking: "Reading the selected content aloud.",
        paused: "Speech output paused.",
        resumed: "Speech output resumed.",
        stopped: "Speech output stopped.",
        finished: "Speech output finished.",
        empty: "There is no readable content in the selected area.",
        error: "The selected content could not be read aloud."
    };

    function announce(message, type = "info") {
        statusRegions.forEach((region) => {
            region.textContent = message;
            region.dataset.statusType = type;

            if (!region.hasAttribute("role")) {
                region.setAttribute("role", "status");
            }

            if (!region.hasAttribute("aria-live")) {
                region.setAttribute("aria-live", "polite");
            }

            region.setAttribute("aria-atomic", "true");
        });
    }

    function clamp(value, minimum, maximum, fallback) {
        const number = Number.parseFloat(value);

        if (!Number.isFinite(number)) {
            return fallback;
        }

        return Math.min(maximum, Math.max(minimum, number));
    }

    function normalizeLanguage(language) {
        if (!language || typeof language !== "string") {
            return "en-US";
        }

        const normalized = language.trim().replace("_", "-");

        const languageMap = {
            en: "en-US",
            de: "de-DE",
            fr: "fr-FR",
            es: "es-ES",
            it: "it-IT",
            pt: "pt-PT",
            nl: "nl-NL",
            pl: "pl-PL",
            tr: "tr-TR",
            ar: "ar-SA",
            fa: "fa-IR",
            ur: "ur-PK",
            he: "he-IL",
            hi: "hi-IN",
            zh: "zh-CN",
            ja: "ja-JP",
            ko: "ko-KR",
            ru: "ru-RU",
            uk: "uk-UA",
            sw: "sw-KE"
        };

        if (normalized.includes("-")) {
            return normalized;
        }

        return languageMap[normalized.toLowerCase()] || normalized;
    }

    function getCurrentLanguage(button = null, target = null) {
        return normalizeLanguage(
            button?.dataset.speechLanguage ||
            target?.getAttribute("lang") ||
            document.documentElement.lang ||
            navigator.language ||
            "en-US"
        );
    }

    function loadVoices() {
        if (!speechSynthesisSupported) {
            return;
        }

        availableVoices = window.speechSynthesis.getVoices();
    }

    function findBestVoice(language) {
        if (!availableVoices.length) {
            loadVoices();
        }

        const normalizedLanguage = language.toLowerCase();
        const baseLanguage = normalizedLanguage.split("-")[0];

        return (
            availableVoices.find(
                (voice) =>
                    voice.lang.toLowerCase() === normalizedLanguage
            ) ||
            availableVoices.find(
                (voice) =>
                    voice.lang.toLowerCase().split("-")[0] ===
                    baseLanguage
            ) ||
            availableVoices.find((voice) => voice.default) ||
            null
        );
    }

    function resolveTarget(button) {
        const targetReference = button.dataset.speechTarget;

        if (!targetReference) {
            return null;
        }

        const targetId = targetReference.replace(/^#/, "");

        return (
            document.getElementById(targetId) ||
            document.querySelector(targetReference)
        );
    }

    function isHidden(element) {
        if (!(element instanceof HTMLElement)) {
            return false;
        }

        return (
            element.hidden ||
            element.getAttribute("aria-hidden") === "true" ||
            window.getComputedStyle(element).display === "none" ||
            window.getComputedStyle(element).visibility === "hidden"
        );
    }

    function sanitizeText(text) {
        return String(text || "")
            .replace(/\s+/g, " ")
            .replace(/\s+([,.!?;:])/g, "$1")
            .trim();
    }

    /*
     * Creates readable text without reading buttons, navigation,
     * scripts, hidden content, passwords or marked private content.
     */
    function extractReadableText(target) {
        if (!target) {
            return "";
        }

        if (
            target instanceof HTMLInputElement ||
            target instanceof HTMLTextAreaElement
        ) {
            if (
                target.type === "password" ||
                target.dataset.speechPrivate !== undefined ||
                target.getAttribute("autocomplete") ===
                    "current-password"
            ) {
                return "";
            }

            return sanitizeText(target.value);
        }

        const clone = target.cloneNode(true);

        clone.querySelectorAll(
            [
                "script",
                "style",
                "noscript",
                "nav",
                "button",
                "input",
                "select",
                "textarea",
                "[hidden]",
                "[aria-hidden='true']",
                "[data-speech-ignore]",
                "[data-speech-private]",
                ".sr-only",
                ".visually-hidden"
            ].join(",")
        ).forEach((element) => element.remove());

        clone.querySelectorAll("img").forEach((image) => {
            const alternativeText = image.getAttribute("alt");

            if (alternativeText) {
                image.replaceWith(
                    document.createTextNode(` ${alternativeText}. `)
                );
            } else {
                image.remove();
            }
        });

        clone.querySelectorAll("abbr[title]").forEach((abbreviation) => {
            abbreviation.textContent =
                abbreviation.getAttribute("title") ||
                abbreviation.textContent;
        });

        return sanitizeText(
            clone.innerText ||
            clone.textContent ||
            ""
        );
    }

    function getSpeechText(button) {
        const directText = button.dataset.speechText;

        if (directText) {
            return sanitizeText(directText);
        }

        const target = resolveTarget(button);

        if (!target || isHidden(target)) {
            return "";
        }

        return extractReadableText(target);
    }

    function updateSpeechButton(button, speaking) {
        if (!button) {
            return;
        }

        button.classList.toggle("is-speaking", speaking);
        button.setAttribute("aria-pressed", String(speaking));
        button.setAttribute(
            "aria-label",
            speaking ? "Stop reading aloud" : "Read aloud"
        );

        const label = button.querySelector("[data-speech-label]");

        if (label) {
            label.textContent = speaking
                ? "Stop reading"
                : "Read aloud";
        }
    }

    function updateControlStates() {
        const speaking =
            speechSynthesisSupported &&
            window.speechSynthesis.speaking;

        const paused =
            speechSynthesisSupported &&
            window.speechSynthesis.paused;

        pauseButtons.forEach((button) => {
            button.disabled = !speaking || paused;
            button.setAttribute(
                "aria-disabled",
                String(!speaking || paused)
            );
        });

        resumeButtons.forEach((button) => {
            button.disabled = !speaking || !paused;
            button.setAttribute(
                "aria-disabled",
                String(!speaking || !paused)
            );
        });

        stopButtons.forEach((button) => {
            button.disabled = !speaking;
            button.setAttribute(
                "aria-disabled",
                String(!speaking)
            );
        });
    }

    function clearSpeechState() {
        updateSpeechButton(currentButton, false);
        currentButton = null;
        currentUtterance = null;
        updateControlStates();
    }

    function stopSpeech(announceStatus = true) {
        if (!speechSynthesisSupported) {
            return;
        }

        window.speechSynthesis.cancel();
        clearSpeechState();

        if (announceStatus) {
            announce(messages.stopped);
        }
    }

    function pauseSpeech() {
        if (
            !speechSynthesisSupported ||
            !window.speechSynthesis.speaking ||
            window.speechSynthesis.paused
        ) {
            return;
        }

        window.speechSynthesis.pause();
        announce(messages.paused);
        updateControlStates();
    }

    function resumeSpeech() {
        if (
            !speechSynthesisSupported ||
            !window.speechSynthesis.paused
        ) {
            return;
        }

        window.speechSynthesis.resume();
        announce(messages.resumed);
        updateControlStates();
    }

    function speakText(text, options = {}) {
        if (!speechSynthesisSupported) {
            announce(messages.unsupported, "error");
            return false;
        }

        const readableText = sanitizeText(text);

        if (!readableText) {
            announce(messages.empty, "error");
            return false;
        }

        stopSpeech(false);

        const language = normalizeLanguage(
            options.language ||
            document.documentElement.lang ||
            navigator.language
        );

        const utterance = new SpeechSynthesisUtterance(
            readableText
        );

        utterance.lang = language;
        utterance.rate = clamp(options.rate, 0.5, 2, 1);
        utterance.pitch = clamp(options.pitch, 0, 2, 1);
        utterance.volume = clamp(options.volume, 0, 1, 1);

        const voice = findBestVoice(language);

        if (voice) {
            utterance.voice = voice;
        }

        utterance.onstart = () => {
            announce(messages.speaking);
            updateSpeechButton(currentButton, true);
            updateControlStates();
        };

        utterance.onpause = () => {
            announce(messages.paused);
            updateControlStates();
        };

        utterance.onresume = () => {
            announce(messages.resumed);
            updateControlStates();
        };

        utterance.onend = () => {
            announce(messages.finished);
            clearSpeechState();
        };

        utterance.onerror = (event) => {
            /*
             * "canceled" and "interrupted" are expected when users
             * deliberately stop or replace speech.
             */
            if (
                event.error !== "canceled" &&
                event.error !== "interrupted"
            ) {
                console.error(
                    "Speech synthesis error:",
                    event.error
                );

                announce(messages.error, "error");
            }

            clearSpeechState();
        };

        currentUtterance = utterance;
        window.speechSynthesis.speak(utterance);

        return true;
    }

    function speakFromButton(button) {
        if (!speechSynthesisSupported) {
            announce(messages.unsupported, "error");
            return;
        }

        if (
            currentButton === button &&
            window.speechSynthesis.speaking
        ) {
            stopSpeech();
            return;
        }

        const target = resolveTarget(button);
        const text = getSpeechText(button);

        if (!text) {
            announce(messages.empty, "error");
            return;
        }

        currentButton = button;

        const started = speakText(text, {
            language: getCurrentLanguage(button, target),
            rate: button.dataset.speechRate,
            pitch: button.dataset.speechPitch,
            volume: button.dataset.speechVolume
        });

        if (!started) {
            currentButton = null;
        }
    }

    function initializeSpeechButton(button) {
        button.setAttribute("type", "button");
        button.setAttribute("aria-pressed", "false");

        if (!button.getAttribute("aria-label")) {
            button.setAttribute("aria-label", "Read aloud");
        }

        const target = resolveTarget(button);

        if (target) {
            if (!target.id) {
                target.id =
                    `speech-target-${Date.now()}-` +
                    Math.random().toString(36).slice(2);
            }

            button.setAttribute("aria-controls", target.id);
        }

        if (!speechSynthesisSupported) {
            button.disabled = true;
            button.setAttribute("aria-disabled", "true");
            button.title = messages.unsupported;
        }

        button.addEventListener("click", () => {
            speakFromButton(button);
        });
    }

    speechButtons.forEach(initializeSpeechButton);

    stopButtons.forEach((button) => {
        button.setAttribute("type", "button");

        button.addEventListener("click", () => {
            stopSpeech();
        });
    });

    pauseButtons.forEach((button) => {
        button.setAttribute("type", "button");

        button.addEventListener("click", pauseSpeech);
    });

    resumeButtons.forEach((button) => {
        button.setAttribute("type", "button");

        button.addEventListener("click", resumeSpeech);
    });

    if (speechSynthesisSupported) {
        loadVoices();

        window.speechSynthesis.addEventListener(
            "voiceschanged",
            loadVoices
        );

        announce(messages.ready);
    } else if (speechButtons.length > 0) {
        announce(messages.unsupported, "error");
    }

    updateControlStates();

    document.addEventListener(
        "smartproperty:languagechange",
        () => {
            if (window.speechSynthesis.speaking) {
                stopSpeech();
            }

            loadVoices();
        }
    );

    document.addEventListener("visibilitychange", () => {
        if (
            document.hidden &&
            speechSynthesisSupported &&
            window.speechSynthesis.speaking
        ) {
            pauseSpeech();
        }
    });

    window.addEventListener("beforeunload", () => {
        if (speechSynthesisSupported) {
            window.speechSynthesis.cancel();
        }
    });

    /*
     * Public API:
     *
     * SmartPropertySpeech.speak("Welcome");
     * SmartPropertySpeech.pause();
     * SmartPropertySpeech.resume();
     * SmartPropertySpeech.stop();
     */
    window.SmartPropertySpeech = {
        isSupported() {
            return speechSynthesisSupported;
        },

        speak(text, options = {}) {
            return speakText(text, options);
        },

        readElement(elementOrSelector, options = {}) {
            const element =
                typeof elementOrSelector === "string"
                    ? document.querySelector(elementOrSelector)
                    : elementOrSelector;

            if (!element) {
                announce(messages.empty, "error");
                return false;
            }

            return speakText(
                extractReadableText(element),
                {
                    language:
                        options.language ||
                        getCurrentLanguage(null, element),
                    rate: options.rate,
                    pitch: options.pitch,
                    volume: options.volume
                }
            );
        },

        pause: pauseSpeech,
        resume: resumeSpeech,
        stop: stopSpeech,

        isSpeaking() {
            return (
                speechSynthesisSupported &&
                window.speechSynthesis.speaking
            );
        },

        isPaused() {
            return (
                speechSynthesisSupported &&
                window.speechSynthesis.paused
            );
        },

        getVoices() {
            return [...availableVoices];
        }
    };
});