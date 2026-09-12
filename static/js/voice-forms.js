/*
 * Smart Property AI
 * Voice-enabled form controls
 *
 * Required:
 *   data-voice-input="target-field-id"
 *
 * Optional:
 *   data-voice-stop
 *   data-voice-clear="target-field-id"
 *   data-voice-status
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    const voiceButtons = document.querySelectorAll("[data-voice-input]");
    const stopButtons = document.querySelectorAll("[data-voice-stop]");
    const clearButtons = document.querySelectorAll("[data-voice-clear]");
    const statusRegions = document.querySelectorAll(
        "[data-voice-status], #voice-status"
    );

    let recognition = null;
    let activeButton = null;
    let activeField = null;
    let originalValue = "";
    let finalTranscript = "";
    let intentionallyStopped = false;

    const messages = {
        ready: "Voice input is ready.",
        listening: "Listening. Start speaking.",
        stopped: "Voice input stopped.",
        saved: "Voice input added.",
        cleared: "The field has been cleared.",
        unsupported:
            "Voice input is not supported by this browser. Please type your response.",
        denied:
            "Microphone access was denied. Allow microphone access and try again.",
        noSpeech: "No speech was detected. Please try again.",
        unavailable:
            "The microphone or speech recognition service is unavailable.",
        missingField: "The requested form field could not be found."
    };

    function announce(message, type = "info") {
        statusRegions.forEach((region) => {
            region.textContent = message;
            region.dataset.statusType = type;
            region.setAttribute(
                "role",
                type === "error" ? "alert" : "status"
            );
            region.setAttribute(
                "aria-live",
                type === "error" ? "assertive" : "polite"
            );
            region.setAttribute("aria-atomic", "true");
        });
    }

    function normalizeLanguage(language) {
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

        if (!language) {
            return "en-US";
        }

        const normalized = String(language)
            .trim()
            .replace("_", "-");

        if (normalized.includes("-")) {
            return normalized;
        }

        return languageMap[normalized.toLowerCase()] || normalized;
    }

    function getLanguage(button, field) {
        return normalizeLanguage(
            button?.dataset.voiceLanguage ||
            field?.getAttribute("lang") ||
            document.documentElement.lang ||
            navigator.language
        );
    }

    function escapeSelector(value) {
        if (
            window.CSS &&
            typeof window.CSS.escape === "function"
        ) {
            return CSS.escape(value);
        }

        return value.replace(
            /([ !"#$%&'()*+,./:;<=>?@[\\\]^`{|}~])/g,
            "\\$1"
        );
    }

    function findField(reference) {
        if (!reference) {
            return null;
        }

        const id = reference.replace(/^#/, "");

        return (
            document.getElementById(id) ||
            document.querySelector(
                `[name="${escapeSelector(id)}"]`
            )
        );
    }

    function isSupportedField(field) {
        if (field instanceof HTMLTextAreaElement) {
            return true;
        }

        if (!(field instanceof HTMLInputElement)) {
            return false;
        }

        const supportedTypes = [
            "text",
            "search",
            "email",
            "tel",
            "url"
        ];

        return supportedTypes.includes(
            (field.type || "text").toLowerCase()
        );
    }

    function dispatchFieldEvents(field) {
        field.dispatchEvent(
            new Event("input", {
                bubbles: true
            })
        );

        field.dispatchEvent(
            new Event("change", {
                bubbles: true
            })
        );
    }

    function joinText(existingText, newText) {
        const existing = String(existingText || "").trim();
        const spoken = String(newText || "").trim();

        if (!existing) {
            return spoken;
        }

        if (!spoken) {
            return existing;
        }

        const separator = /[\s,.!?;:]$/.test(existing)
            ? " "
            : ". ";

        return `${existing}${separator}${spoken}`;
    }

    function updateButton(button, listening) {
        if (!button) {
            return;
        }

        button.classList.toggle("is-listening", listening);
        button.setAttribute("aria-pressed", String(listening));
        button.setAttribute(
            "aria-label",
            listening ? "Stop voice input" : "Start voice input"
        );

        const label = button.querySelector("[data-voice-label]");

        if (label) {
            label.textContent = listening
                ? "Stop listening"
                : "Use voice";
        }
    }

    function clearActiveState() {
        updateButton(activeButton, false);

        if (activeField) {
            activeField.removeAttribute("data-voice-active");
        }

        activeButton = null;
        activeField = null;
        originalValue = "";
        finalTranscript = "";
    }

    function stopListening(message = messages.stopped) {
        intentionallyStopped = true;

        if (recognition) {
            try {
                recognition.stop();
            } catch (error) {
                console.debug(
                    "Voice recognition was already stopped.",
                    error
                );
            }
        }

        clearActiveState();
        announce(message);
    }

    function handleCommand(transcript) {
        const command = transcript
            .trim()
            .toLowerCase()
            .replace(/[.!?]+$/g, "");

        if (
            command === "clear field" ||
            command === "clear input" ||
            command === "delete text"
        ) {
            if (activeField) {
                activeField.value = "";
                originalValue = "";
                finalTranscript = "";
                dispatchFieldEvents(activeField);
                announce(messages.cleared);
            }

            return true;
        }

        if (
            command === "stop listening" ||
            command === "stop voice input"
        ) {
            stopListening();
            return true;
        }

        if (
            command === "submit form" ||
            command === "send form"
        ) {
            const form = activeField?.closest("form");

            stopListening();

            if (form) {
                if (form.checkValidity()) {
                    form.requestSubmit();
                } else {
                    form.reportValidity();
                }
            }

            return true;
        }

        return false;
    }

    function createRecognition() {
        if (!SpeechRecognition) {
            return null;
        }

        const instance = new SpeechRecognition();

        instance.continuous = true;
        instance.interimResults = true;
        instance.maxAlternatives = 1;

        instance.onstart = () => {
            updateButton(activeButton, true);

            if (activeField) {
                activeField.setAttribute(
                    "data-voice-active",
                    "true"
                );
            }

            announce(messages.listening);
        };

        instance.onresult = (event) => {
            let interimText = "";
            let completedText = "";

            for (
                let index = event.resultIndex;
                index < event.results.length;
                index += 1
            ) {
                const result = event.results[index];
                const transcript = result[0].transcript;

                if (result.isFinal) {
                    completedText += transcript;
                } else {
                    interimText += transcript;
                }
            }

            if (completedText.trim()) {
                if (handleCommand(completedText)) {
                    return;
                }

                finalTranscript = joinText(
                    finalTranscript,
                    completedText
                );

                if (activeField) {
                    activeField.value = joinText(
                        originalValue,
                        finalTranscript
                    );

                    dispatchFieldEvents(activeField);
                }

                announce(messages.saved);
                return;
            }

            if (interimText.trim() && activeField) {
                activeField.value = joinText(
                    originalValue,
                    joinText(finalTranscript, interimText)
                );
            }
        };

        instance.onerror = (event) => {
            let message = messages.unavailable;

            switch (event.error) {
                case "no-speech":
                    message = messages.noSpeech;
                    break;

                case "not-allowed":
                case "service-not-allowed":
                    message = messages.denied;
                    break;

                case "audio-capture":
                    message = messages.unavailable;
                    break;

                case "aborted":
                    if (intentionallyStopped) {
                        return;
                    }
                    break;

                default:
                    message = messages.unavailable;
            }

            announce(message, "error");
        };

        instance.onend = () => {
            clearActiveState();
        };

        return instance;
    }

    function startListening(button) {
        if (!SpeechRecognition) {
            announce(messages.unsupported, "error");
            return;
        }

        if (activeButton === button) {
            stopListening();
            return;
        }

        const field = findField(button.dataset.voiceInput);

        if (!field || !isSupportedField(field)) {
            announce(messages.missingField, "error");
            return;
        }

        if (recognition && activeButton) {
            intentionallyStopped = true;

            try {
                recognition.abort();
            } catch (error) {
                console.debug(
                    "The previous voice session was already closed.",
                    error
                );
            }

            clearActiveState();
        }

        recognition = createRecognition();

        if (!recognition) {
            announce(messages.unsupported, "error");
            return;
        }

        activeButton = button;
        activeField = field;
        originalValue = field.value || "";
        finalTranscript = "";
        intentionallyStopped = false;

        recognition.lang = getLanguage(button, field);

        try {
            recognition.start();
        } catch (error) {
            console.error(
                "Voice recognition could not start.",
                error
            );

            clearActiveState();
            announce(messages.unavailable, "error");
        }
    }

    function initializeVoiceButton(button) {
        const field = findField(button.dataset.voiceInput);

        button.type = "button";
        button.setAttribute("aria-pressed", "false");

        if (!button.getAttribute("aria-label")) {
            button.setAttribute(
                "aria-label",
                "Start voice input"
            );
        }

        if (field) {
            if (!field.id) {
                field.id =
                    `voice-field-${Date.now()}-` +
                    Math.random().toString(36).slice(2);
            }

            button.setAttribute("aria-controls", field.id);
        }

        if (!SpeechRecognition) {
            button.disabled = true;
            button.setAttribute("aria-disabled", "true");
            button.title = messages.unsupported;
        }

        button.addEventListener("click", () => {
            startListening(button);
        });
    }

    voiceButtons.forEach(initializeVoiceButton);

    stopButtons.forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            stopListening();
        });
    });

    clearButtons.forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            const field = findField(
                button.dataset.voiceClear
            );

            if (!field || !isSupportedField(field)) {
                announce(messages.missingField, "error");
                return;
            }

            field.value = "";
            dispatchFieldEvents(field);
            field.focus();

            announce(messages.cleared);
        });
    });

    document.addEventListener(
        "smartproperty:languagechange",
        () => {
            if (activeButton) {
                stopListening(
                    "Language changed. Start voice input again."
                );
            }
        }
    );

    document.addEventListener("visibilitychange", () => {
        if (document.hidden && activeButton) {
            stopListening();
        }
    });

    window.addEventListener("beforeunload", () => {
        intentionallyStopped = true;

        if (recognition) {
            try {
                recognition.abort();
            } catch (error) {
                console.debug(
                    "Voice recognition was already closed.",
                    error
                );
            }
        }
    });

    if (!SpeechRecognition && voiceButtons.length) {
        announce(messages.unsupported, "error");
    } else if (voiceButtons.length) {
        announce(messages.ready);
    }

    window.SmartPropertyVoiceForms = {
        isSupported() {
            return Boolean(SpeechRecognition);
        },

        start(buttonOrSelector) {
            const button =
                typeof buttonOrSelector === "string"
                    ? document.querySelector(buttonOrSelector)
                    : buttonOrSelector;

            if (button) {
                startListening(button);
            }
        },

        stop() {
            stopListening();
        },

        isListening() {
            return Boolean(activeButton);
        }
    };
});