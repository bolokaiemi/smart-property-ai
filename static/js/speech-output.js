/*
 * Smart Property AI
 * File: static/js/speech-output.js
 *
 * One-button text-to-speech toggle:
 * First click  = read aloud
 * Second click = stop reading
 */

(() => {
    "use strict";

// Track current language for speech synthesis
let currentLanguage = document.documentElement.lang || navigator.language || "en-US";

// Update language when the language selector changes
document.addEventListener("smartproperty:languagechange", (e) => {
    const newLang = e.detail?.language;
    if (newLang) {
        currentLanguage = newLang;
    }
});

    function initializeSpeechOutput() {
        const speechSupported =
            "speechSynthesis" in window &&
            "SpeechSynthesisUtterance" in window;

        const speechButtons = document.querySelectorAll(
            "[data-speech-target], [data-speech-text]"
        );

        const stopButtons = document.querySelectorAll(
            "[data-speech-stop]"
        );

        const pauseButtons = document.querySelectorAll(
            "[data-speech-pause]"
        );

        const resumeButtons = document.querySelectorAll(
            "[data-speech-resume]"
        );

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
            speaking:
                "Reading the selected content aloud.",
            paused:
                "Speech output paused.",
            resumed:
                "Speech output resumed.",
            stopped:
                "Speech output stopped.",
            finished:
                "Speech output finished.",
            empty:
                "There is no readable content in the selected area.",
            error:
                "The selected content could not be read aloud."
        };

        function announce(message, type = "info") {
            statusRegions.forEach((region) => {
                region.textContent = message;
                region.dataset.statusType = type;

                if (!region.hasAttribute("role")) {
                    region.setAttribute(
                        "role",
                        type === "error"
                            ? "alert"
                            : "status"
                    );
                }

                if (!region.hasAttribute("aria-live")) {
                    region.setAttribute(
                        "aria-live",
                        type === "error"
                            ? "assertive"
                            : "polite"
                    );
                }

                region.setAttribute(
                    "aria-atomic",
                    "true"
                );
            });
        }

        function clamp(
            value,
            minimum,
            maximum,
            fallback
        ) {
            const number =
                Number.parseFloat(value);

            if (!Number.isFinite(number)) {
                return fallback;
            }

            return Math.min(
                maximum,
                Math.max(minimum, number)
            );
        }

        function normalizeLanguage(language) {
            if (
                !language ||
                typeof language !== "string"
            ) {
                return "en-US";
            }

            const normalized = language
                .trim()
                .replace("_", "-");

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

            return (
                languageMap[
                    normalized.toLowerCase()
                ] ||
                normalized
            );
        }

        function getCurrentLanguage(
            button = null,
            target = null
        ) {
            return normalizeLanguage(
                button?.dataset.speechLanguage ||
                target?.getAttribute("lang") ||
                document.documentElement.lang ||
                navigator.language ||
                "en-US"
            );
        }

        function loadVoices() {
            if (!speechSupported) {
                return;
            }

            availableVoices =
                window.speechSynthesis.getVoices();
        }

        function findBestVoice(language) {
            if (!availableVoices.length) {
                loadVoices();
            }

            const normalizedLanguage =
                language.toLowerCase();

            const baseLanguage =
                normalizedLanguage.split("-")[0];

            return (
                availableVoices.find(
                    (voice) =>
                        voice.lang.toLowerCase() ===
                        normalizedLanguage
                ) ||
                availableVoices.find(
                    (voice) =>
                        voice.lang
                            .toLowerCase()
                            .split("-")[0] ===
                        baseLanguage
                ) ||
                availableVoices.find(
                    (voice) => voice.default
                ) ||
                null
            );
        }

        function resolveTarget(button) {
            const selector =
                button?.dataset.speechTarget;

            if (!selector) {
                return null;
            }

            try {
                return document.querySelector(
                    selector
                );
            } catch (error) {
                console.error(
                    "Invalid speech target:",
                    selector,
                    error
                );

                return null;
            }
        }

        function isHidden(element) {
            if (!(element instanceof HTMLElement)) {
                return false;
            }

            const styles =
                window.getComputedStyle(element);

            return (
                element.hidden ||
                element.getAttribute(
                    "aria-hidden"
                ) === "true" ||
                styles.display === "none" ||
                styles.visibility === "hidden"
            );
        }

        function sanitizeText(text) {
            return String(text || "")
                .replace(/\s+/g, " ")
                .replace(
                    /\s+([,.!?;:])/g,
                    "$1"
                )
                .trim();
        }

        /*
         * Extract readable text while excluding navigation,
         * buttons, scripts, forms, hidden content, and private data.
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
                    target.hasAttribute(
                        "data-speech-private"
                    ) ||
                    target.getAttribute(
                        "autocomplete"
                    ) === "current-password"
                ) {
                    return "";
                }

                return sanitizeText(
                    target.value
                );
            }

            const clone =
                target.cloneNode(true);

            clone.querySelectorAll(
                [
                    "script",
                    "style",
                    "noscript",
                    "nav",
                    "button",
                    "form",
                    "input",
                    "select",
                    "textarea",
                    "[hidden]",
                    "[aria-hidden='true']",
                    "[data-speech-ignore]",
                    "[data-speech-private]",
                    ".sr-only",
                    ".visually-hidden",
                    "#ai-chat-overlay"
                ].join(",")
            ).forEach((element) => {
                element.remove();
            });

            clone
                .querySelectorAll("img")
                .forEach((image) => {
                    const alternativeText =
                        image.getAttribute("alt");

                    if (alternativeText) {
                        image.replaceWith(
                            document.createTextNode(
                                ` ${alternativeText}. `
                            )
                        );
                    } else {
                        image.remove();
                    }
                });

            clone
                .querySelectorAll("abbr[title]")
                .forEach((abbreviation) => {
                    abbreviation.textContent =
                        abbreviation.getAttribute(
                            "title"
                        ) ||
                        abbreviation.textContent;
                });

            return sanitizeText(
                clone.innerText ||
                clone.textContent ||
                ""
            );
        }

        function getSpeechText(button) {
            const directText =
                button.dataset.speechText;

            if (directText) {
                return sanitizeText(
                    directText
                );
            }

            const target =
                resolveTarget(button);

            if (
                !target ||
                isHidden(target)
            ) {
                return "";
            }

            return extractReadableText(
                target
            );
        }

        /*
         * Save the button's original label only once.
         */
        function rememberButtonState(button) {
            if (!button) {
                return;
            }

            if (
                !button.dataset.speechOriginalText
            ) {
                button.dataset.speechOriginalText =
                    button.textContent.trim() ||
                    "Read aloud";
            }

            if (
                !button.dataset.speechOriginalTitle
            ) {
                button.dataset.speechOriginalTitle =
                    button.title ||
                    "Read aloud";
            }

            if (
                !button.dataset.speechOriginalAriaLabel
            ) {
                button.dataset.speechOriginalAriaLabel =
                    button.getAttribute(
                        "aria-label"
                    ) ||
                    "Read aloud";
            }
        }

        /*
         * Change the same button between:
         * Read aloud <-> Stop reading
         */
        function updateSpeechButton(
            button,
            isSpeaking
        ) {
            if (!button) {
                return;
            }

            rememberButtonState(button);

            const readLabel =
                button.dataset.speechReadLabel ||
                button.dataset.speechOriginalText ||
                "Read aloud";

            const stopLabel =
                button.dataset.speechStopLabel ||
                "Stop reading";

            button.textContent =
                isSpeaking
                    ? stopLabel
                    : readLabel;

            button.setAttribute(
                "aria-pressed",
                String(isSpeaking)
            );

            button.setAttribute(
                "aria-label",
                isSpeaking
                    ? "Stop reading"
                    : (
                        button.dataset
                            .speechOriginalAriaLabel ||
                        "Read aloud"
                    )
            );

            button.title =
                isSpeaking
                    ? "Stop reading"
                    : (
                        button.dataset
                            .speechOriginalTitle ||
                        "Read aloud"
                    );

            button.classList.toggle(
                "is-speaking",
                isSpeaking
            );
        }

        function updateControlStates() {
            const speaking =
                speechSupported &&
                window.speechSynthesis.speaking;

            const paused =
                speechSupported &&
                window.speechSynthesis.paused;

            pauseButtons.forEach((button) => {
                const disabled =
                    !speaking || paused;

                button.disabled = disabled;

                button.setAttribute(
                    "aria-disabled",
                    String(disabled)
                );
            });

            resumeButtons.forEach((button) => {
                const disabled =
                    !speaking || !paused;

                button.disabled = disabled;

                button.setAttribute(
                    "aria-disabled",
                    String(disabled)
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
            if (currentButton) {
                updateSpeechButton(
                    currentButton,
                    false
                );
            }

            currentButton = null;
            currentUtterance = null;

            updateControlStates();
        }

        function stopSpeech(
            announceStatus = true
        ) {
            if (!speechSupported) {
                return;
            }

            const wasActive =
                window.speechSynthesis.speaking ||
                window.speechSynthesis.paused ||
                currentUtterance !== null;

            window.speechSynthesis.cancel();

            clearSpeechState();

            if (
                announceStatus &&
                wasActive
            ) {
                announce(
                    messages.stopped
                );
            }
        }

        function pauseSpeech() {
            if (
                !speechSupported ||
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
                !speechSupported ||
                !window.speechSynthesis.paused
            ) {
                return;
            }

            window.speechSynthesis.resume();

            announce(messages.resumed);
            updateControlStates();
        }

        function speakText(
            text,
            options = {}
        ) {
            if (!speechSupported) {
                announce(
                    messages.unsupported,
                    "error"
                );

                return false;
            }

            const readableText =
                sanitizeText(text);

            if (!readableText) {
                announce(
                    messages.empty,
                    "error"
                );

                return false;
            }

            /*
             * Cancel any speech already running before
             * creating a new utterance.
             */
            window.speechSynthesis.cancel();

            const language =
                normalizeLanguage(
                    options.language ||
                    document.documentElement.lang ||
                    navigator.language ||
                    "en-US"
                );

            const utterance =
                new SpeechSynthesisUtterance(
                    readableText
                );

            utterance.lang = language;

            utterance.rate = clamp(
                options.rate,
                0.5,
                2,
                1
            );

            utterance.pitch = clamp(
                options.pitch,
                0,
                2,
                1
            );

            utterance.volume = clamp(
                options.volume,
                0,
                1,
                1
            );

            const voice =
                findBestVoice(language);

            if (voice) {
                utterance.voice = voice;
            }

            utterance.onstart = () => {
                /*
                 * Ignore old events from an utterance
                 * that has already been replaced.
                 */
                if (
                    currentUtterance !==
                    utterance
                ) {
                    return;
                }

                updateSpeechButton(
                    currentButton,
                    true
                );

                announce(
                    messages.speaking
                );

                updateControlStates();
            };

            utterance.onpause = () => {
                if (
                    currentUtterance !==
                    utterance
                ) {
                    return;
                }

                announce(messages.paused);
                updateControlStates();
            };

            utterance.onresume = () => {
                if (
                    currentUtterance !==
                    utterance
                ) {
                    return;
                }

                announce(messages.resumed);
                updateControlStates();
            };

            utterance.onend = () => {
                if (
                    currentUtterance !==
                    utterance
                ) {
                    return;
                }

                announce(messages.finished);
                clearSpeechState();
            };

            utterance.onerror = (event) => {
                if (
                    currentUtterance !==
                    utterance
                ) {
                    return;
                }

                if (
                    event.error !== "canceled" &&
                    event.error !== "interrupted"
                ) {
                    console.error(
                        "Speech synthesis error:",
                        event.error
                    );

                    announce(
                        messages.error,
                        "error"
                    );
                }

                clearSpeechState();
            };

            currentUtterance = utterance;

            /*
             * Update immediately so rapid second clicks
             * can stop speech before onstart fires.
             */
            updateSpeechButton(
                currentButton,
                true
            );

            window.speechSynthesis.speak(
                utterance
            );

            return true;
        }

        /*
         * This is the single-button toggle.
         */
        function toggleReadAloud(button) {
            if (!speechSupported) {
                announce(
                    messages.unsupported,
                    "error"
                );

                return;
            }

            const thisButtonIsActive =
                currentButton === button &&
                (
                    window.speechSynthesis.speaking ||
                    window.speechSynthesis.paused ||
                    currentUtterance !== null
                );

            /*
             * Second click stops the current reading.
             */
            if (thisButtonIsActive) {
                stopSpeech(true);
                return;
            }

            /*
             * Stop another speech button before starting this one.
             */
            if (
                currentUtterance ||
                window.speechSynthesis.speaking ||
                window.speechSynthesis.paused
            ) {
                stopSpeech(false);
            }

            const target =
                resolveTarget(button);

            const text =
                getSpeechText(button);

            if (!text) {
                announce(
                    messages.empty,
                    "error"
                );

                return;
            }

            currentButton = button;

            const started = speakText(
                text,
                {
                    language:
                        getCurrentLanguage(
                            button,
                            target
                        ),

                    rate:
                        button.dataset.speechRate,

                    pitch:
                        button.dataset.speechPitch,

                    volume:
                        button.dataset.speechVolume
                }
            );

            if (!started) {
                updateSpeechButton(
                    button,
                    false
                );

                currentButton = null;
            }
        }

        function initializeSpeechButton(button) {
            rememberButtonState(button);

            button.setAttribute(
                "type",
                "button"
            );

            button.setAttribute(
                "aria-pressed",
                "false"
            );

            if (
                !button.getAttribute(
                    "aria-label"
                )
            ) {
                button.setAttribute(
                    "aria-label",
                    "Read aloud"
                );
            }

            const target =
                resolveTarget(button);

            if (target) {
                if (!target.id) {
                    target.id =
                        "speech-target-" +
                        Date.now() +
                        "-" +
                        Math.random()
                            .toString(36)
                            .slice(2);
                }

                button.setAttribute(
                    "aria-controls",
                    target.id
                );
            }

            if (!speechSupported) {
                button.disabled = true;

                button.setAttribute(
                    "aria-disabled",
                    "true"
                );

                button.title =
                    messages.unsupported;
            }

            button.addEventListener(
                "click",
                () => {
                    toggleReadAloud(
                        button
                    );
                }
            );
        }

        speechButtons.forEach(
            initializeSpeechButton
        );

        stopButtons.forEach((button) => {
            button.setAttribute(
                "type",
                "button"
            );

            button.addEventListener(
                "click",
                () => {
                    stopSpeech(true);
                }
            );
        });

        pauseButtons.forEach((button) => {
            button.setAttribute(
                "type",
                "button"
            );

            button.addEventListener(
                "click",
                pauseSpeech
            );
        });

        resumeButtons.forEach((button) => {
            button.setAttribute(
                "type",
                "button"
            );

            button.addEventListener(
                "click",
                resumeSpeech
            );
        });

        if (speechSupported) {
            loadVoices();

            window.speechSynthesis.addEventListener(
                "voiceschanged",
                loadVoices
            );

            announce(messages.ready);
        } else if (speechButtons.length) {
            announce(
                messages.unsupported,
                "error"
            );
        }

        updateControlStates();

        /*
         * Stop the old language before changing voices.
         */
        document.addEventListener(
            "smartproperty:languagechange",
            () => {
                if (
                    window.speechSynthesis
                        .speaking ||
                    window.speechSynthesis
                        .paused
                ) {
                    stopSpeech(true);
                }

                loadVoices();
            }
        );

        /*
         * Pause when the browser tab becomes hidden.
         */
        document.addEventListener(
            "visibilitychange",
            () => {
                if (
                    document.hidden &&
                    speechSupported &&
                    window.speechSynthesis
                        .speaking &&
                    !window.speechSynthesis
                        .paused
                ) {
                    pauseSpeech();
                }
            }
        );

        window.addEventListener(
            "beforeunload",
            () => {
                if (speechSupported) {
                    window.speechSynthesis.cancel();
                }
            }
        );

        /*
         * Public API
         */
        window.SmartPropertySpeech = {
            isSupported() {
                return speechSupported;
            },

            speak(text, options = {}) {
                /*
                 * Programmatic speech is not connected
                 * to a particular button.
                 */
                if (
                    currentButton
                ) {
                    updateSpeechButton(
                        currentButton,
                        false
                    );
                }

                currentButton = null;

                return speakText(
                    text,
                    options
                );
            },

            readElement(
                elementOrSelector,
                options = {}
            ) {
                const element =
                    typeof elementOrSelector ===
                    "string"
                        ? document.querySelector(
                              elementOrSelector
                          )
                        : elementOrSelector;

                if (!element) {
                    announce(
                        messages.empty,
                        "error"
                    );

                    return false;
                }

                return speakText(
                    extractReadableText(
                        element
                    ),
                    {
                        language:
                            options.language ||
                            getCurrentLanguage(
                                null,
                                element
                            ),

                        rate:
                            options.rate,

                        pitch:
                            options.pitch,

                        volume:
                            options.volume
                    }
                );
            },

            pause: pauseSpeech,
            resume: resumeSpeech,
            stop: stopSpeech,

            toggle(buttonOrSelector) {
                const button =
                    typeof buttonOrSelector ===
                    "string"
                        ? document.querySelector(
                              buttonOrSelector
                          )
                        : buttonOrSelector;

                if (button) {
                    if (isSpeaking()||isPaused()) {
    stopSpeech(true);
    return false;
}
                    toggleReadAloud(
                        button
                    );
                }
            },

            isSpeaking() {
                return (
                    speechSupported &&
                    window.speechSynthesis
                        .speaking
                );
            },

            isPaused() {
                return (
                    speechSupported &&
                    window.speechSynthesis
                        .cancel()
                );
            },

            getVoices() {
                return [
                    ...availableVoices
                ];
            }
        };
    }

    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initializeSpeechOutput,
            { once: true }
        );
    } else {
        initializeSpeechOutput();
    }
})();