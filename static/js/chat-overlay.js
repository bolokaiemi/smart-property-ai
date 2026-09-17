(() => {
    "use strict";

    function initializeChatOverlay() {
        const overlay =
            document.getElementById("ai-chat-overlay");

        if (
            !overlay ||
            overlay.dataset.initialized === "true"
        ) {
            return;
        }

        const dialog =
            overlay.querySelector(".ai-overlay__dialog");

        const form =
            document.getElementById("ai-overlay-form");

        const input =
            document.getElementById("ai-overlay-question");

        const messages =
            document.getElementById("ai-overlay-messages");

        const statusElement =
            document.getElementById("ai-overlay-status");

        const languageSelect =
            document.getElementById("ai-overlay-language");

        const sendButton =
            form?.querySelector(
                "button[type='submit']"
            );

        const csrfInput =
            form?.querySelector(
                "input[name='csrf_token']"
            );

        

        /*
         * Stop safely if required HTML elements are missing.
         */
        if (
            !dialog ||
            !form ||
            !input ||
            !messages ||
            !sendButton
        ) {
            console.error(
                "The AI chat overlay could not start because required elements are missing."
            );

            return;
        }

        overlay.dataset.initialized = "true";

        let previousFocus = null;
        let requestInProgress = false;
        let conversationId = null;
        let abortController = null;

        function safeValue(element, fallback = "") {
            if (
                element &&
                typeof element.value === "string"
            ) {
                return element.value;
            }

            return fallback;
        }

        function getCsrfToken() {
            return safeValue(
                csrfInput,
                overlay.dataset.csrfToken || ""
            ).trim();
        }

        function getLanguage() {
            return (
                safeValue(
                    languageSelect,
                    document.documentElement.lang || "en"
                )
                    .trim()
                    .toLowerCase()
                    .split("-")[0] || "en"
            );
        }

        function showStatus(
            message = "",
            isError = false
        ) {
            if (!statusElement) {
                return;
            }

            statusElement.textContent = message;

            statusElement.classList.toggle(
                "is-error",
                isError
            );

            statusElement.setAttribute(
                "role",
                isError ? "alert" : "status"
            );
        }

        function createMessage(role, message) {
            const messageElement =
                document.createElement("div");

            messageElement.className =
                `ai-overlay__message ai-overlay__message--${role}`;

            const authorElement =
                document.createElement("strong");

            authorElement.textContent =
                role === "user"
                    ? "You"
                    : "Smart Property AI";

            const textElement =
                document.createElement("p");

            /*
             * Use textContent to prevent HTML injection.
             */
            textElement.textContent = message;

            messageElement.append(
                authorElement,
                textElement
            );

            messages.appendChild(messageElement);

            messages.scrollTop =
                messages.scrollHeight;
        }

        function createLoginLink() {
            /*
             * Do not add the login link repeatedly.
             */
            const existingLink =
                messages.querySelector(
                    ".ai-overlay__login-link"
                );

            if (existingLink) {
                return;
            }

            const loginLink =
                document.createElement("a");

            loginLink.className =
                "ai-overlay__login-link";

            loginLink.href =
                "/login?next=" +
                encodeURIComponent(
                    window.location.pathname
                );

            loginLink.textContent =
                "Go to login";

            messages.appendChild(loginLink);

            messages.scrollTop =
                messages.scrollHeight;
        }

        function setRequestState(state) {
            requestInProgress = state;

            sendButton.disabled = state;
            input.disabled = state;

            if (languageSelect) {
                languageSelect.disabled = state;
            }

            form.setAttribute(
                "aria-busy",
                String(state)
            );

            if (!state && !overlay.hidden) {
                input.focus();
            }
        }

        function selectPageLanguage() {
            if (!languageSelect) {
                return;
            }

            const pageLanguage =
                (
                    document.documentElement.lang ||
                    "en"
                )
                    .toLowerCase()
                    .split("-")[0];

            const languageExists =
                Array.from(
                    languageSelect.options
                ).some(
                    (option) =>
                        option.value === pageLanguage
                );

            if (languageExists) {
                languageSelect.value =
                    pageLanguage;
            }
        }

        function openOverlay(trigger) {
            previousFocus =
                trigger ||
                document.activeElement;

            selectPageLanguage();

            overlay.hidden = false;

            document.body.classList.add(
                "ai-overlay-is-open"
            );

            /*
             * Move focus into the modal after it becomes visible.
             */
            window.requestAnimationFrame(() => {
                input.focus();
            });
        }

        function closeOverlay() {
            /*
             * Do not close while a request is running.
             * Abort it first.
             */
            if (abortController) {
                abortController.abort();
                abortController = null;
            }

            setRequestState(false);

            overlay.hidden = true;

            document.body.classList.remove(
                "ai-overlay-is-open"
            );

            showStatus("");

            if (
                previousFocus &&
                typeof previousFocus.focus ===
                    "function"
            ) {
                previousFocus.focus();
            }
        }

        function getFocusableElements() {
            return Array.from(
                dialog.querySelectorAll(
                    [
                        "button:not(:disabled)",
                        "textarea:not(:disabled)",
                        "select:not(:disabled)",
                        "input:not([type='hidden']):not(:disabled)",
                        "a[href]"
                    ].join(",")
                )
            ).filter(
                (element) =>
                    element.offsetParent !== null
            );
        }

        function trapKeyboardFocus(event) {
            if (event.key === "Escape") {
                event.preventDefault();
                closeOverlay();
                return;
            }

            if (event.key !== "Tab") {
                return;
            }

            const focusableElements =
                getFocusableElements();

            if (!focusableElements.length) {
                event.preventDefault();
                dialog.focus();
                return;
            }

            const firstElement =
                focusableElements[0];

            const lastElement =
                focusableElements[
                    focusableElements.length - 1
                ];

            if (
                event.shiftKey &&
                document.activeElement === firstElement
            ) {
                event.preventDefault();
                lastElement.focus();
            } else if (
                !event.shiftKey &&
                document.activeElement === lastElement
            ) {
                event.preventDefault();
                firstElement.focus();
            }
        }

        function getServerMessage(
            responseData,
            fallbackMessage
        ) {
            if (
                responseData &&
                typeof responseData.detail ===
                    "string" &&
                responseData.detail.trim()
            ) {
                return responseData.detail;
            }

            if (
                responseData &&
                typeof responseData.error ===
                    "string" &&
                responseData.error.trim()
            ) {
                return responseData.error;
            }

            if (
                responseData &&
                typeof responseData.message ===
                    "string" &&
                responseData.message.trim()
            ) {
                return responseData.message;
            }

            return fallbackMessage;
        }

        async function submitMessage(event) {
            event.preventDefault();

            if (requestInProgress) {
                return;
            }

            const question =
                safeValue(input).trim();

            if (!question) {
                showStatus(
                    "Please enter a question.",
                    true
                );

                input.focus();
                return;
            }

            if (question.length > 4000) {
                showStatus(
                    "Please keep your question under 4,000 characters.",
                    true
                );

                return;
            }

            const csrfToken =
                getCsrfToken();

            if (!csrfToken) {
                showStatus(
                    "The security token is missing. Refresh the page and try again.",
                    true
                );

                return;
            }

            createMessage(
                "user",
                question
            );

            input.value = "";

            setRequestState(true);

            showStatus(
                "Smart Property AI is responding…"
            );

            abortController =
                new AbortController();

            const timeout = window.setTimeout(
                () => {
                    if (abortController) {
                        abortController.abort();
                    }
                },
                30000
            );

            try {
                const response = await fetch(
                    form.action ||
                        "/api/ai/chat",
                    {
                        method: "POST",

                        /*
                         * Include the authenticated session cookie.
                         */
                        credentials: "same-origin",

                        headers: {
                            Accept:
                                "application/json",

                            "Content-Type":
                                "application/json",

                            /*
                             * The FastAPI backend should read:
                             * request.headers.get("X-CSRF-Token")
                             */
                            "X-CSRF-Token":
                                csrfToken
                        },

                        body: JSON.stringify({
                            message: question,
                            language:
                                getLanguage(),
                            conversation_id:
                                conversationId
                        }),

                        signal:
                            abortController.signal
                    }
                );

                const contentType =
                    response.headers.get(
                        "content-type"
                    ) || "";

                let responseData = {};

                if (
                    contentType.includes(
                        "application/json"
                    )
                ) {
                    responseData =
                        await response.json();
                }

                /*
                 * A missing session should return 401.
                 */
                if (response.status === 401) {
                    createMessage(
                        "assistant",
                        "Please log in to continue using the AI assistant."
                    );

                    createLoginLink();

                    showStatus(
                        "Login is required.",
                        true
                    );

                    return;
                }

                /*
                 * A 403 can mean CSRF failure or insufficient permission.
                 */
                if (response.status === 403) {
                    throw new Error(
                        getServerMessage(
                            responseData,
                            "Access denied. Refresh the page and try again."
                        )
                    );
                }

                if (!response.ok) {
                    throw new Error(
                        getServerMessage(
                            responseData,
                            "The assistant could not complete your request."
                        )
                    );
                }

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

                createMessage(
                    "assistant",
                    assistantReply
                );

                if (
                    typeof responseData.disclaimer ===
                        "string" &&
                    responseData.disclaimer.trim()
                ) {
                    showStatus(
                        responseData.disclaimer
                    );
                } else {
                    showStatus(
                        "Reply received."
                    );
                }
            } catch (error) {
                /*
                 * Closing the dialog intentionally aborts the request.
                 */
                if (
                    error.name === "AbortError" &&
                    overlay.hidden
                ) {
                    return;
                }

                const errorMessage =
                    error.name === "AbortError"
                        ? "The assistant timed out. Please try again."
                        : error.message ||
                          "Unable to contact the assistant.";

                createMessage(
                    "assistant",
                    errorMessage
                );

                showStatus(
                    errorMessage,
                    true
                );

                /*
                 * Restore the unsent message.
                 */
                input.value = question;
            } finally {
                window.clearTimeout(timeout);

                abortController = null;

                setRequestState(false);
            }
        }

        /*
         * Open and close controls use event delegation so buttons
         * added elsewhere on the page continue to work.
         */
        document.addEventListener(
            "click",
            (event) => {
                const openButton =
                    event.target.closest(
                        "[data-ai-overlay-open]"
                    );

                if (openButton) {
                    event.preventDefault();

                    openOverlay(openButton);
                    return;
                }

                if (overlay.hidden) {
                    return;
                }

                const closeButton =
                    event.target.closest(
                        "[data-ai-overlay-close]"
                    );

                if (closeButton) {
                    event.preventDefault();
                    closeOverlay();
                }
            }
        );

        overlay.addEventListener(
            "keydown",
            trapKeyboardFocus
        );

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
    }

    /*
     * Initialize after the document is ready.
     */
    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initializeChatOverlay,
            { once: true }
        );
    } else {
        initializeChatOverlay();
    }
})();