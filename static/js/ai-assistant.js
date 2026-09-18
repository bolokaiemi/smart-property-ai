"use strict";

/**
 * Smart Property AI Assistant
 * Chat, model selection, voice controls, maximize mode
 * and inactivity logout.
 */
(function initialiseSmartPropertyAssistant() {
    const page = document.querySelector(
        "[data-ai-assistant-page]"
    );

    if (
        !page ||
        page.dataset.aiAssistantReady === "true"
    ) {
        return;
    }

    page.dataset.aiAssistantReady = "true";

    const form = page.querySelector(
        "[data-ai-chat-form]"
    );

    const conversation = page.querySelector(
        "[data-ai-conversation]"
    );

    const messageInput = page.querySelector(
        "[data-ai-message]"
    );

    const sendButton = page.querySelector(
        "[data-send-button]"
    );

    const chatStatus = page.querySelector(
        "[data-ai-chat-status]"
    );

    const voiceStatus = page.querySelector(
        "[data-voice-status]"
    );

    const typingIndicator = page.querySelector(
        "[data-typing-indicator]"
    );

    const messageCounter = page.querySelector(
        "[data-message-counter]"
    );

    const conversationIdInput =
        page.querySelector(
            "[data-conversation-id]"
        );

    const csrfInput = page.querySelector(
        "[data-csrf-token]"
    );

    const modelSelect = page.querySelector(
        "[data-ai-model-select]"
    );

    const voiceButton = page.querySelector(
        "[data-voice-input]"
    );

    const stopSpeechButton =
        page.querySelector(
            "[data-stop-speech]"
        );

    const maximizeButton = page.querySelector(
        "[data-ai-maximize]"
    );

    const maximizeLabel = page.querySelector(
        "[data-maximize-label]"
    );

    const maximizeIcon = page.querySelector(
        "[data-maximize-icon]"
    );

    const clearButton = page.querySelector(
        "[data-clear-conversation]"
    );

    const chatPanel = page.querySelector(
        ".ai-chat-panel"
    );

    const inactivityWarning =
        page.querySelector(
            "[data-inactivity-warning-message]"
        );

    const inactivityCountdown =
        page.querySelector(
            "[data-inactivity-countdown]"
        );

    const continueSessionButton =
        page.querySelector(
            "[data-continue-session]"
        );

    if (
        !form ||
        !conversation ||
        !messageInput
    ) {
        return;
    }

    const chatUrl =
        form.dataset.chatUrl ||
        "/api/ai/chat";

    const clearUrl =
        form.dataset.clearUrl ||
        "/api/ai/conversation/clear";

    const logoutUrl =
        page.dataset.logoutUrl ||
        "/logout";

    const loginUrl =
        page.dataset.loginUrl ||
        "/login?reason=inactive";

    const maximumMessageLength =
        Number(messageInput.maxLength) || 3000;

    const inactivityLimit =
        positiveNumber(
            page.dataset.inactivityTimeout,
            180000
        );

    const warningDuration = Math.min(
        positiveNumber(
            page.dataset.inactivityWarning,
            30000
        ),
        inactivityLimit
    );

    let recognition = null;
    let isListening = false;
    let isSending = false;
    let isMaximized = false;
    let inactivityTimer = null;
    let countdownTimer = null;
    let remainingWarningSeconds =
        Math.ceil(warningDuration / 1000);

    function positiveNumber(
        value,
        fallback
    ) {
        const number = Number(value);

        return (
            Number.isFinite(number) &&
            number > 0
        )
            ? number
            : fallback;
    }

    function csrfToken() {
        return String(
            csrfInput?.value || ""
        ).trim();
    }

    function selectedModel() {
        return String(
            modelSelect?.value || "default"
        ).trim();
    }

    function setStatus(
        message,
        isError = false
    ) {
        if (!chatStatus) {
            return;
        }

        chatStatus.textContent =
            message || "";

        chatStatus.classList.toggle(
            "is-error",
            Boolean(isError)
        );
    }

    function setVoiceStatus(
        message,
        isError = false
    ) {
        if (!voiceStatus) {
            return;
        }

        voiceStatus.textContent =
            message || "";

        voiceStatus.classList.toggle(
            "is-error",
            Boolean(isError)
        );
    }

    function updateCounter() {
        if (!messageCounter) {
            return;
        }

        messageCounter.textContent =
            `${messageInput.value.length} / ` +
            `${maximumMessageLength}`;
    }

    function scrollConversationToBottom() {
        window.requestAnimationFrame(() => {
            conversation.scrollTop =
                conversation.scrollHeight;
        });
    }

    function setTyping(isVisible) {
        if (!typingIndicator) {
            return;
        }

        typingIndicator.hidden =
            !isVisible;

        if (isVisible) {
            scrollConversationToBottom();
        }
    }

    function setSending(isBusy) {
        isSending = isBusy;
        messageInput.disabled = isBusy;

        if (sendButton) {
            sendButton.disabled = isBusy;

            const text =
                sendButton.querySelector(
                    "span:last-child"
                );

            if (text) {
                text.textContent =
                    isBusy
                        ? "Sending…"
                        : "Send";
            }
        }

        setTyping(isBusy);
    }

    function createElement(
        tag,
        className,
        text
    ) {
        const element =
            document.createElement(tag);

        if (className) {
            element.className =
                className;
        }

        if (text !== undefined) {
            element.textContent = text;
        }

        return element;
    }

    function createMessage(
        role,
        content
    ) {
        const isUser =
            role === "user";

        const article = createElement(
            "article",
            `chat-message ${
                isUser
                    ? "user-message"
                    : "assistant-message"
            }`
        );

        const avatar = createElement(
            "div",
            "chat-avatar",
            isUser ? "You" : "AI"
        );

        avatar.setAttribute(
            "aria-hidden",
            "true"
        );

        const messageContent =
            createElement(
                "div",
                "chat-message-content"
            );

        const author = createElement(
            "p",
            "chat-message-author",
            isUser
                ? "You"
                : "Smart Property AI"
        );

        const bubble = createElement(
            "div",
            "chat-message-bubble"
        );

        bubble.appendChild(
            createElement(
                "p",
                "",
                content
            )
        );

        messageContent.append(
            author,
            bubble
        );

        if (!isUser) {
            const readButton =
                createElement(
                    "button",
                    "chat-speech-button",
                    "🔊 Read aloud"
                );

            readButton.type = "button";

            readButton.dataset.readMessage =
                "true";

            readButton.setAttribute(
                "aria-label",
                "Read this message aloud"
            );

            readButton.setAttribute(
                "aria-pressed",
                "false"
            );

            messageContent.appendChild(
                readButton
            );
        }

        article.append(
            avatar,
            messageContent
        );

        if (
            typingIndicator &&
            typingIndicator.parentNode ===
                conversation
        ) {
            conversation.insertBefore(
                article,
                typingIndicator
            );
        } else {
            conversation.appendChild(
                article
            );
        }

        scrollConversationToBottom();

        return article;
    }

    function responseMessage(data) {
        if (
            !data ||
            typeof data !== "object"
        ) {
            return "";
        }

        const candidate =
            data.reply ??
            data.response ??
            data.answer ??
            data.message ??
            data.content;

        return typeof candidate === "string"
            ? candidate.trim()
            : "";
    }

    function responseError(
        data,
        fallback
    ) {
        if (
            data &&
            typeof data === "object"
        ) {
            const detail =
                data.detail ??
                data.error ??
                data.message;

            if (
                typeof detail === "string" &&
                detail.trim()
            ) {
                return detail.trim();
            }
        }

        return fallback;
    }

    async function parseJson(response) {
        const type =
            response.headers.get(
                "content-type"
            ) || "";

        if (
            !type.includes(
                "application/json"
            )
        ) {
            return {};
        }

        try {
            return await response.json();
        } catch {
            return {};
        }
    }

    async function submitMessage(
        message
    ) {
        const cleanMessage =
            String(message || "").trim();

        if (
            !cleanMessage ||
            isSending
        ) {
            return;
        }

        if (
            cleanMessage.length >
            maximumMessageLength
        ) {
            setStatus(
                `Messages must contain no more than ` +
                `${maximumMessageLength} characters.`,
                true
            );

            messageInput.focus();
            return;
        }

        const token = csrfToken();

        if (!token) {
            setStatus(
                "The security token is missing. " +
                "Refresh the page and try again.",
                true
            );

            return;
        }

        createMessage(
            "user",
            cleanMessage
        );

        messageInput.value = "";

        updateCounter();
        setStatus("");
        setSending(true);
        resetInactivityTimer();

        try {
            const response = await fetch(
                chatUrl,
                {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Accept":
                            "application/json",

                        "Content-Type":
                            "application/json",

                        "X-CSRF-Token":
                            token,

                        "X-CSRFToken":
                            token
                    },

                    body: JSON.stringify({
                        message:
                            cleanMessage,

                        model:
                            selectedModel(),

                        conversation_id:
                            conversationIdInput
                                ?.value || "",

                        csrf_token:
                            token
                    })
                }
            );

            const data =
                await parseJson(response);

            if (
                response.status === 401
            ) {
                window.location.assign(
                    `/login?next=${
                        encodeURIComponent(
                            window.location.pathname
                        )
                    }`
                );

                return;
            }

            if (
                !response.ok ||
                data.success === false
            ) {
                throw new Error(
                    responseError(
                        data,
                        "The assistant could not " +
                        "process your request."
                    )
                );
            }

            const reply =
                responseMessage(data);

            if (!reply) {
                throw new Error(
                    "The assistant returned " +
                    "an empty response."
                );
            }

            if (
                conversationIdInput &&
                data.conversation_id
            ) {
                conversationIdInput.value =
                    String(
                        data.conversation_id
                    );
            }

            createMessage(
                "assistant",
                reply
            );

            setStatus(
                "Response received."
            );
        } catch (error) {
            const messageText =
                error instanceof Error
                    ? error.message
                    : "The assistant is " +
                      "temporarily unavailable.";

            createMessage(
                "assistant",
                messageText
            );

            setStatus(
                messageText,
                true
            );
        } finally {
            setSending(false);
            messageInput.focus();
            resetInactivityTimer();
        }
    }

    async function clearConversation() {
        const confirmed =
            window.confirm(
                "Clear this AI conversation?"
            );

        if (!confirmed) {
            return;
        }

        const token = csrfToken();

        if (!token) {
            setStatus(
                "The security token is missing. " +
                "Refresh the page and try again.",
                true
            );

            return;
        }

        if (clearButton) {
            clearButton.disabled = true;
        }

        setStatus(
            "Clearing conversation…"
        );

        try {
            const response = await fetch(
                clearUrl,
                {
                    method: "POST",
                    credentials: "same-origin",

                    headers: {
                        "Accept":
                            "application/json",

                        "Content-Type":
                            "application/json",

                        "X-CSRF-Token":
                            token,

                        "X-CSRFToken":
                            token
                    },

                    body: JSON.stringify({
                        conversation_id:
                            conversationIdInput
                                ?.value || "",

                        csrf_token:
                            token
                    })
                }
            );

            const data =
                await parseJson(response);

            if (
                !response.ok ||
                data.success === false
            ) {
                throw new Error(
                    responseError(
                        data,
                        "The conversation " +
                        "could not be cleared."
                    )
                );
            }

            conversation
                .querySelectorAll(
                    ".chat-message:not(" +
                    "[data-typing-indicator])"
                )
                .forEach((message) => {
                    message.remove();
                });

            if (conversationIdInput) {
                conversationIdInput.value =
                    String(
                        data.conversation_id ||
                        ""
                    );
            }

            createMessage(
                "assistant",
                "The conversation has been " +
                "cleared. How can I help?"
            );

            setStatus(
                "Conversation cleared."
            );
        } catch (error) {
            setStatus(
                error instanceof Error
                    ? error.message
                    : "The conversation " +
                      "could not be cleared.",
                true
            );
        } finally {
            if (clearButton) {
                clearButton.disabled = false;
            }

            resetInactivityTimer();
        }
    }

    function speechLanguage() {
        const language =
            document.documentElement.lang ||
            navigator.language ||
            "en-US";

        const languageMap = {
            en: "en-US",
            de: "de-DE",
            fr: "fr-FR",
            es: "es-ES"
        };

        return (
            languageMap[
                language.toLowerCase()
            ] ||
            language
        );
    }

    function stopSpeech() {
        if (
            "speechSynthesis" in window
        ) {
            window.speechSynthesis.cancel();
        }

        if (stopSpeechButton) {
            stopSpeechButton.disabled = true;
        }

        page.querySelectorAll(
            "[data-read-message]"
        ).forEach((button) => {
            button.setAttribute(
                "aria-pressed",
                "false"
            );
        });

        setVoiceStatus(
            "Voice output stopped."
        );
    }

    function readText(
        text,
        trigger
    ) {
        const content =
            String(text || "").trim();

        if (!content) {
            return;
        }

        if (
            !(
                "speechSynthesis" in
                window
            ) ||
            !(
                "SpeechSynthesisUtterance" in
                window
            )
        ) {
            setVoiceStatus(
                "Voice output is not " +
                "supported by this browser.",
                true
            );

            return;
        }

        window.speechSynthesis.cancel();

        const utterance =
            new SpeechSynthesisUtterance(
                content
            );

        utterance.lang =
            speechLanguage();

        utterance.rate = 1;

        utterance.onstart = () => {
            if (trigger) {
                trigger.setAttribute(
                    "aria-pressed",
                    "true"
                );
            }

            if (stopSpeechButton) {
                stopSpeechButton.disabled =
                    false;
            }

            setVoiceStatus(
                "Reading response aloud."
            );

            resetInactivityTimer();
        };

        const finish = () => {
            if (trigger) {
                trigger.setAttribute(
                    "aria-pressed",
                    "false"
                );
            }

            if (stopSpeechButton) {
                stopSpeechButton.disabled =
                    true;
            }
        };

        utterance.onend = () => {
            finish();

            setVoiceStatus(
                "Finished reading."
            );
        };

        utterance.onerror = (event) => {
            finish();

            if (
                event.error !== "canceled" &&
                event.error !== "interrupted"
            ) {
                setVoiceStatus(
                    "The response could not " +
                    "be read aloud.",
                    true
                );
            }
        };

        window.speechSynthesis.speak(
            utterance
        );
    }

    function initialiseRecognition() {
        const Recognition =
            window.SpeechRecognition ||
            window.webkitSpeechRecognition;

        if (
            !Recognition ||
            !voiceButton
        ) {
            if (voiceButton) {
                voiceButton.disabled = true;

                voiceButton.title =
                    "Voice input is not " +
                    "supported by this browser";
            }

            return;
        }

        recognition =
            new Recognition();

        recognition.lang =
            speechLanguage();

        recognition.interimResults = true;
        recognition.continuous = false;

        let originalText = "";

        recognition.onstart = () => {
            isListening = true;

            originalText =
                messageInput.value.trim();

            voiceButton.setAttribute(
                "aria-pressed",
                "true"
            );

            voiceButton.classList.add(
                "is-listening"
            );

            setVoiceStatus(
                "Listening… Speak now."
            );

            resetInactivityTimer();
        };

        recognition.onresult = (
            event
        ) => {
            let transcript = "";

            for (
                let index =
                    event.resultIndex;
                index <
                    event.results.length;
                index += 1
            ) {
                transcript +=
                    event.results[
                        index
                    ][0].transcript;
            }

            const separator =
                originalText ? " " : "";

            messageInput.value =
                `${originalText}` +
                `${separator}` +
                `${transcript}`;

            messageInput.value =
                messageInput.value.slice(
                    0,
                    maximumMessageLength
                );

            updateCounter();
        };

        recognition.onerror = (
            event
        ) => {
            const messages = {
                "not-allowed":
                    "Microphone permission " +
                    "was denied.",

                "audio-capture":
                    "No microphone was found.",

                "no-speech":
                    "No speech was detected. " +
                    "Please try again."
            };

            setVoiceStatus(
                messages[event.error] ||
                "Voice input could not " +
                "be completed.",
                true
            );
        };

        recognition.onend = () => {
            isListening = false;

            voiceButton.setAttribute(
                "aria-pressed",
                "false"
            );

            voiceButton.classList.remove(
                "is-listening"
            );

            if (
                !voiceStatus?.classList
                    .contains("is-error")
            ) {
                setVoiceStatus(
                    "Voice input finished."
                );
            }

            messageInput.focus();
            resetInactivityTimer();
        };
    }

    function toggleVoiceInput() {
        if (!recognition) {
            setVoiceStatus(
                "Voice input is not " +
                "supported by this browser.",
                true
            );

            return;
        }

        if (isListening) {
            recognition.stop();
        } else {
            setVoiceStatus("");
            recognition.lang =
                speechLanguage();
            recognition.start();
        }
    }

    function setMaximized(
        maximized
    ) {
        isMaximized =
            Boolean(maximized);

        chatPanel?.classList.toggle(
            "is-maximized",
            isMaximized
        );

        page.classList.toggle(
            "is-maximized",
            isMaximized
        );

        document.body.classList.toggle(
            "ai-assistant-maximized",
            isMaximized
        );

        if (maximizeButton) {
            maximizeButton.setAttribute(
                "aria-pressed",
                String(isMaximized)
            );

            maximizeButton.setAttribute(
                "aria-label",
                isMaximized
                    ? "Restore the AI assistant"
                    : "Maximize the AI assistant"
            );

            maximizeButton.title =
                isMaximized
                    ? "Restore assistant"
                    : "Maximize assistant";
        }

        if (maximizeLabel) {
            maximizeLabel.textContent =
                isMaximized
                    ? "Restore"
                    : "Maximize";
        }

        if (maximizeIcon) {
            maximizeIcon.textContent =
                isMaximized
                    ? "🗗"
                    : "⛶";
        }

        resetInactivityTimer();
    }

    function hideInactivityWarning() {
        if (inactivityWarning) {
            inactivityWarning.hidden =
                true;
        }

        if (countdownTimer) {
            window.clearInterval(
                countdownTimer
            );

            countdownTimer = null;
        }
    }

    async function logoutForInactivity() {
        hideInactivityWarning();
        stopSpeech();

        if (
            recognition &&
            isListening
        ) {
            recognition.stop();
        }

        const token = csrfToken();

        try {
            await fetch(
                logoutUrl,
                {
                    method: "POST",
                    credentials: "same-origin",

                    headers: {
                        "Content-Type":
                            "application/" +
                            "x-www-form-urlencoded;" +
                            "charset=UTF-8",

                        "X-CSRF-Token":
                            token,

                        "X-CSRFToken":
                            token
                    },

                    body:
                        new URLSearchParams({
                            csrf_token: token
                        }).toString(),

                    keepalive: true
                }
            );
        } finally {
            window.location.replace(
                loginUrl
            );
        }
    }

    function showInactivityWarning() {
        remainingWarningSeconds =
            Math.max(
                1,
                Math.ceil(
                    warningDuration / 1000
                )
            );

        if (inactivityCountdown) {
            inactivityCountdown.textContent =
                String(
                    remainingWarningSeconds
                );
        }

        if (inactivityWarning) {
            inactivityWarning.hidden =
                false;
        }

        countdownTimer =
            window.setInterval(() => {
                remainingWarningSeconds -= 1;

                if (
                    inactivityCountdown
                ) {
                    inactivityCountdown
                        .textContent =
                        String(
                            Math.max(
                                0,
                                remainingWarningSeconds
                            )
                        );
                }

                if (
                    remainingWarningSeconds <=
                    0
                ) {
                    window.clearInterval(
                        countdownTimer
                    );

                    countdownTimer = null;

                    logoutForInactivity();
                }
            }, 1000);
    }

    function resetInactivityTimer() {
        if (inactivityTimer) {
            window.clearTimeout(
                inactivityTimer
            );
        }

        hideInactivityWarning();

        const delay = Math.max(
            0,
            inactivityLimit -
            warningDuration
        );

        inactivityTimer =
            window.setTimeout(
                showInactivityWarning,
                delay
            );
    }

    function registerActivityListeners() {
        let lastReset = 0;

        const activity = () => {
            const now = Date.now();

            if (
                now - lastReset <
                1000
            ) {
                return;
            }

            lastReset = now;
            resetInactivityTimer();
        };

        [
            "pointerdown",
            "keydown",
            "touchstart",
            "scroll"
        ].forEach((eventName) => {
            document.addEventListener(
                eventName,
                activity,
                {
                    passive: true
                }
            );
        });
    }

    form.addEventListener(
        "submit",
        (event) => {
            event.preventDefault();

            submitMessage(
                messageInput.value
            );
        }
    );

    messageInput.addEventListener(
        "input",
        () => {
            updateCounter();
            resetInactivityTimer();
        }
    );

    messageInput.addEventListener(
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

    page.addEventListener(
        "click",
        (event) => {
            const readButton =
                event.target.closest(
                    "[data-read-message]"
                );

            if (readButton) {
                const bubble =
                    readButton
                        .closest(
                            ".chat-message-content"
                        )
                        ?.querySelector(
                            ".chat-message-bubble"
                        );

                readText(
                    bubble?.textContent || "",
                    readButton
                );

                return;
            }

            const promptButton =
                event.target.closest(
                    "[data-ai-prompt]"
                );

            if (promptButton) {
                messageInput.value =
                    String(
                        promptButton
                            .dataset
                            .aiPrompt || ""
                    ).slice(
                        0,
                        maximumMessageLength
                    );

                updateCounter();
                messageInput.focus();
                resetInactivityTimer();
            }
        }
    );

    voiceButton?.addEventListener(
        "click",
        toggleVoiceInput
    );

    stopSpeechButton?.addEventListener(
        "click",
        stopSpeech
    );

    maximizeButton?.addEventListener(
        "click",
        () => {
            setMaximized(
                !isMaximized
            );
        }
    );

    clearButton?.addEventListener(
        "click",
        clearConversation
    );

    continueSessionButton
        ?.addEventListener(
            "click",
            () => {
                resetInactivityTimer();
                messageInput.focus();

                setStatus(
                    "Session continued."
                );
            }
        );

    modelSelect?.addEventListener(
        "change",
        () => {
            try {
                window.sessionStorage
                    .setItem(
                        "smartPropertyAiModel",
                        selectedModel()
                    );
            } catch {
                /*
                 * Browser storage may be
                 * unavailable in privacy mode.
                 */
            }

            setStatus(
                "AI model updated."
            );

            resetInactivityTimer();
        }
    );

    document.addEventListener(
        "keydown",
        (event) => {
            if (
                event.key === "Escape" &&
                isMaximized
            ) {
                setMaximized(false);
            }
        }
    );

    window.addEventListener(
        "beforeunload",
        () => {
            if (
                "speechSynthesis" in
                window
            ) {
                window
                    .speechSynthesis
                    .cancel();
            }

            if (
                recognition &&
                isListening
            ) {
                recognition.abort();
            }
        }
    );

    try {
        const savedModel =
            window.sessionStorage
                .getItem(
                    "smartPropertyAiModel"
                );

        if (
            savedModel &&
            modelSelect
        ) {
            const optionExists =
                Array.from(
                    modelSelect.options
                ).some(
                    (option) =>
                        option.value ===
                        savedModel
                );

            if (optionExists) {
                modelSelect.value =
                    savedModel;
            }
        }
    } catch {
        /*
         * Ignore unavailable
         * browser storage.
         */
    }

    initialiseRecognition();
    registerActivityListeners();
    updateCounter();
    scrollConversationToBottom();
    resetInactivityTimer();
})();