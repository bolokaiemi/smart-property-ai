(() => {
    "use strict";

    function initializeAssistant() {
        const root = document.querySelector("[data-ai-assistant]");

        if (!root || root.dataset.initialized === "true") {
            return;
        }

        const form = root.querySelector("[data-ai-chat-form]");
        const input = root.querySelector("[data-ai-message]");
        const messages = root.querySelector("[data-ai-messages]");
        const sendButton = root.querySelector("[data-ai-submit]");
        const languageSelect = root.querySelector("[data-ai-language]");
        const statusElement = root.querySelector("[data-ai-status]");
        const csrfInput = form?.querySelector("input[name='csrf_token']");

        /*
         * Stop safely when essential HTML elements are missing.
         * This prevents:
         * Cannot read properties of null (reading 'value')
         */
        if (!form || !input || !messages || !sendButton) {
            console.error(
                "AI assistant could not start because required HTML elements are missing."
            );
            return;
        }

        root.dataset.initialized = "true";

        let isBusy = false;
        let lastReply = "";
        let conversationId = root.dataset.conversationId || null;
        let speechRecognition = null;

        /*
         * Safely read an element's value.
         */
        function getElementValue(element, fallback = "") {
            if (element && typeof element.value === "string") {
                return element.value;
            }

            return fallback;
        }

        function getCurrentLanguage() {
            const fallbackLanguage =
                document.documentElement.lang || "en";

            const selectedLanguage = getElementValue(
                languageSelect,
                fallbackLanguage
            );

            return (
                selectedLanguage
                    .trim()
                    .toLowerCase()
                    .split("-")[0] || "en"
            );
        }

        function getCsrfToken() {
            /*
             * First try the hidden form input.
             * If it does not exist, use the token stored on the root element.
             */
            return getElementValue(
                csrfInput,
                root.dataset.csrfToken || ""
            ).trim();
        }

        function updateStatus(message = "", isError = false) {
            if (!statusElement) {
                return;
            }

            statusElement.textContent = message;
            statusElement.classList.toggle("is-error", isError);
            statusElement.setAttribute(
                "role",
                isError ? "alert" : "status"
            );
        }

        function addMessage(role, message) {
            const messageElement = document.createElement("article");

            messageElement.className =
                `ai-message ai-message--${role}`;

            const labelElement = document.createElement("strong");

            labelElement.className = "ai-message__label";
            labelElement.textContent =
                role === "user"
                    ? "You"
                    : "Smart Property AI";

            const textElement = document.createElement("p");

            textElement.className = "ai-message__text";

            /*
             * Use textContent rather than innerHTML.
             * This prevents returned messages from injecting HTML.
             */
            textElement.textContent = message;

            messageElement.append(
                labelElement,
                textElement
            );

            messages.appendChild(messageElement);
            messages.scrollTop = messages.scrollHeight;
        }

        function setBusy(state) {
            isBusy = state;

            sendButton.disabled = state;
            input.disabled = state;

            form.setAttribute(
                "aria-busy",
                String(state)
            );

            if (!state) {
                input.focus();
            }
        }

        function getServerError(data, fallbackMessage) {
            if (
                data &&
                typeof data.detail === "string" &&
                data.detail.trim()
            ) {
                return data.detail;
            }

            if (
                data &&
                typeof data.error === "string" &&
                data.error.trim()
            ) {
                return data.error;
            }

            if (
                data &&
                typeof data.message === "string" &&
                data.message.trim()
            ) {
                return data.message;
            }

            return fallbackMessage;
        }

        async function submitMessage(event) {
            event.preventDefault();

            if (isBusy) {
                return;
            }

            const question =
                getElementValue(input).trim();

            if (!question) {
                updateStatus(
                    "Please enter a message.",
                    true
                );

                input.focus();
                return;
            }

            if (question.length > 4000) {
                updateStatus(
                    "Please keep your message under 4,000 characters.",
                    true
                );

                return;
            }

            const csrfToken = getCsrfToken();

            if (!csrfToken) {
                updateStatus(
                    "The security token is missing. Refresh the page and try again.",
                    true
                );

                return;
            }

            addMessage("user", question);

            input.value = "";

            setBusy(true);

            updateStatus(
                "Smart Property AI is responding…"
            );

            const requestController =
                new AbortController();

            const requestTimeout = window.setTimeout(
                () => requestController.abort(),
                30000
            );

            try {
                const endpoint =
                    form.dataset.endpoint ||
                    form.action ||
                    "/api/ai/chat";

                const response = await fetch(endpoint, {
                    method: "POST",

                    /*
                     * This sends the login session cookie.
                     */
                    credentials: "same-origin",

                    headers: {
                        Accept: "application/json",
                        "Content-Type": "application/json",

                        /*
                         * The FastAPI CSRF validator must read:
                         * request.headers.get("X-CSRF-Token")
                         */
                        "X-CSRF-Token": csrfToken
                    },

                    body: JSON.stringify({
                        message: question,
                        language: getCurrentLanguage(),
                        conversation_id: conversationId
                    }),

                    signal: requestController.signal
                });

                const contentType =
                    response.headers.get("content-type") || "";

                let responseData = {};

                if (
                    contentType.includes(
                        "application/json"
                    )
                ) {
                    responseData = await response.json();
                }

                /*
                 * A 401 response means the login session is missing.
                 */
                if (response.status === 401) {
                    const nextPage =
                        encodeURIComponent(
                            window.location.pathname
                        );

                    window.location.assign(
                        `/login?next=${nextPage}`
                    );

                    return;
                }

                /*
                 * A 403 may be caused by CSRF or permissions.
                 * Do not incorrectly report every 403 as login expiry.
                 */
                if (response.status === 403) {
                    throw new Error(
                        getServerError(
                            responseData,
                            "Access denied. Refresh the page and try again."
                        )
                    );
                }

                if (!response.ok) {
                    throw new Error(
                        getServerError(
                            responseData,
                            "The assistant could not complete your request."
                        )
                    );
                }

                /*
                 * Support either "reply" or "response" from FastAPI.
                 */
                let assistantReply = "";

                if (
                    typeof responseData.reply ===
                    "string"
                ) {
                    assistantReply =
                        responseData.reply.trim();
                } else if (
                    typeof responseData.response ===
                    "string"
                ) {
                    assistantReply =
                        responseData.response.trim();
                }

                if (!assistantReply) {
                    throw new Error(
                        "The assistant returned an empty response."
                    );
                }

                conversationId =
                    responseData.conversation_id ||
                    conversationId;

                if (conversationId) {
                    root.dataset.conversationId =
                        conversationId;
                }

                lastReply = assistantReply;

                addMessage(
                    "assistant",
                    assistantReply
                );

                if (
                    typeof responseData.disclaimer ===
                    "string"
                ) {
                    updateStatus(
                        responseData.disclaimer
                    );
                } else {
                    updateStatus("Reply received.");
                }
            } catch (error) {
                let errorMessage;

                if (error.name === "AbortError") {
                    errorMessage =
                        "The assistant timed out. Please try again.";
                } else {
                    errorMessage =
                        error.message ||
                        "Unable to contact the assistant.";
                }

                addMessage(
                    "assistant",
                    errorMessage
                );

                updateStatus(
                    errorMessage,
                    true
                );

                /*
                 * Restore the user's message so it is not lost.
                 */
                input.value = question;
            } finally {
                window.clearTimeout(
                    requestTimeout
                );

                setBusy(false);
            }
        }

        form.addEventListener(
            "submit",
            submitMessage
        );

        /*
         * Enter sends the message.
         * Shift + Enter creates a new line.
         */
        input.addEventListener(
            "keydown",
            (event) => {
                if (
                    event.key === "Enter" &&
                    !event.shiftKey &&
                    !event.isComposing
                ) {
                    event.preventDefault();
                    form.requestSubmit();
                }
            }
        );

        /*
         * Read the latest AI response aloud.
         */
        const readReplyButton =
            root.querySelector(
                "[data-ai-read-reply]"
            );

        readReplyButton?.addEventListener(
            "click",
            () => {
                if (!lastReply) {
                    updateStatus(
                        "There is no reply to read yet.",
                        true
                    );

                    return;
                }

                if (
                    !(
                        "speechSynthesis" in
                        window
                    )
                ) {
                    updateStatus(
                        "Speech output is unavailable in this browser.",
                        true
                    );

                    return;
                }

                window.speechSynthesis.cancel();

                const speech =
                    new SpeechSynthesisUtterance(
                        lastReply
                    );

                speech.lang =
                    getCurrentLanguage();

                window.speechSynthesis.speak(
                    speech
                );
            }
        );

        /*
         * Stop speech output.
         */
        const stopSpeechButton =
            root.querySelector(
                "[data-ai-stop-speech]"
            );

        stopSpeechButton?.addEventListener(
            "click",
            () => {
                if (
                    "speechSynthesis" in window
                ) {
                    window.speechSynthesis.cancel();
                }
            }
        );

        /*
         * Voice input.
         */
        const voiceButton =
            root.querySelector(
                "[data-ai-voice-input]"
            );

        voiceButton?.addEventListener(
            "click",
            () => {
                const Recognition =
                    window.SpeechRecognition ||
                    window.webkitSpeechRecognition;

                if (!Recognition) {
                    updateStatus(
                        "Voice input is unavailable in this browser.",
                        true
                    );

                    return;
                }

                /*
                 * Clicking again stops active recognition.
                 */
                if (speechRecognition) {
                    speechRecognition.stop();
                    return;
                }

                speechRecognition =
                    new Recognition();

                speechRecognition.lang =
                    getCurrentLanguage();

                speechRecognition.interimResults =
                    false;

                speechRecognition.continuous =
                    false;

                speechRecognition.onresult = (
                    event
                ) => {
                    const spokenText =
                        event.results?.[0]?.[0]
                            ?.transcript?.trim() ||
                        "";

                    if (spokenText) {
                        const existingText =
                            getElementValue(
                                input
                            ).trim();

                        input.value = [
                            existingText,
                            spokenText
                        ]
                            .filter(Boolean)
                            .join(" ");
                    }

                    input.focus();
                };

                speechRecognition.onerror = () => {
                    updateStatus(
                        "Voice input failed. Please type your message instead.",
                        true
                    );
                };

                speechRecognition.onend = () => {
                    speechRecognition = null;

                    voiceButton.setAttribute(
                        "aria-pressed",
                        "false"
                    );

                    input.focus();
                };

                voiceButton.setAttribute(
                    "aria-pressed",
                    "true"
                );

                updateStatus("Listening…");

                speechRecognition.start();
            }
        );
    }

    /*
     * Start only when the page DOM is ready.
     */
    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initializeAssistant,
            { once: true }
        );
    } else {
        initializeAssistant();
    }
})();