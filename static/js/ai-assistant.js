/*
 * Smart Property AI
 * AI assistant chat interface
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector(
        "[data-ai-chat-form]"
    );

    if (!form) {
        return;
    }

    const conversation = document.querySelector(
        "[data-ai-conversation]"
    );

    const messageField = form.querySelector(
        "[data-ai-message]"
    );

    const sendButton = form.querySelector(
        "[data-send-button]"
    );

    const statusRegion = form.querySelector(
        "[data-ai-chat-status]"
    );

    const counter = form.querySelector(
        "[data-message-counter]"
    );

    const conversationIdField = form.querySelector(
        "[data-conversation-id]"
    );

    const csrfField = form.querySelector(
        "[data-csrf-token]"
    );

    const typingIndicator = document.querySelector(
        "[data-typing-indicator]"
    );

    const clearButton = document.querySelector(
        "[data-clear-conversation]"
    );

    const quickPromptButtons = document.querySelectorAll(
        "[data-ai-prompt]"
    );

    let requestInProgress = false;

    function announce(message, type = "info") {
        if (!statusRegion) {
            return;
        }

        statusRegion.textContent = message;
        statusRegion.dataset.statusType = type;

        statusRegion.setAttribute(
            "role",
            type === "error" ? "alert" : "status"
        );

        statusRegion.setAttribute(
            "aria-live",
            type === "error"
                ? "assertive"
                : "polite"
        );
    }

    function getLanguage() {
        return (
            document.documentElement.lang ||
            navigator.language ||
            "en"
        );
    }

    function scrollToLatestMessage() {
        if (!conversation) {
            return;
        }

        const reducedMotion = window.matchMedia(
            "(prefers-reduced-motion: reduce)"
        ).matches;

        conversation.scrollTo({
            top: conversation.scrollHeight,
            behavior: reducedMotion ? "auto" : "smooth"
        });
    }

    function updateCounter() {
        if (!messageField || !counter) {
            return;
        }

        const maximum =
            messageField.maxLength > 0
                ? messageField.maxLength
                : 3000;

        counter.textContent =
            `${messageField.value.length} / ${maximum}`;
    }

    function resizeTextarea() {
        if (!messageField) {
            return;
        }

        messageField.style.height = "auto";

        const nextHeight = Math.min(
            messageField.scrollHeight,
            180
        );

        messageField.style.height = `${nextHeight}px`;
    }

    function setLoading(loading) {
        requestInProgress = loading;

        if (sendButton) {
            sendButton.disabled = loading;
            sendButton.setAttribute(
                "aria-disabled",
                String(loading)
            );

            const label = sendButton.querySelector(
                "span:last-child"
            );

            if (label) {
                label.textContent = loading
                    ? "Sending…"
                    : "Send";
            }
        }

        if (messageField) {
            messageField.setAttribute(
                "aria-busy",
                String(loading)
            );
        }

        if (typingIndicator) {
            typingIndicator.hidden = !loading;
        }

        if (loading) {
            scrollToLatestMessage();
        }
    }

    function createElement(
        tagName,
        className = "",
        text = ""
    ) {
        const element =
            document.createElement(tagName);

        if (className) {
            element.className = className;
        }

        if (text) {
            element.textContent = text;
        }

        return element;
    }

    function formatTime() {
        return new Intl.DateTimeFormat(
            document.documentElement.lang || "en",
            {
                hour: "2-digit",
                minute: "2-digit"
            }
        ).format(new Date());
    }

    function readMessage(button) {
        const messageContent = button
            .closest(".chat-message-content")
            ?.querySelector(".chat-message-bubble")
            ?.textContent
            ?.trim();

        if (!messageContent) {
            return;
        }

        if (
            window.SmartPropertySpeech &&
            typeof window.SmartPropertySpeech.speak ===
                "function"
        ) {
            window.SmartPropertySpeech.speak(
                messageContent,
                {
                    language: getLanguage()
                }
            );

            return;
        }

        if (
            "speechSynthesis" in window &&
            "SpeechSynthesisUtterance" in window
        ) {
            window.speechSynthesis.cancel();

            const utterance =
                new SpeechSynthesisUtterance(
                    messageContent
                );

            utterance.lang = getLanguage();

            window.speechSynthesis.speak(utterance);
        }
    }

    function attachSpeechButton(button) {
        button.addEventListener("click", () => {
            readMessage(button);
        });
    }

    function createMessage(
        role,
        content,
        options = {}
    ) {
        const article = createElement(
            "article",
            role === "user"
                ? "chat-message user-message"
                : "chat-message assistant-message"
        );

        const avatar = createElement(
            "div",
            "chat-avatar",
            role === "user" ? "You" : "AI"
        );

        avatar.setAttribute("aria-hidden", "true");

        const messageContent = createElement(
            "div",
            "chat-message-content"
        );

        const author = createElement(
            "p",
            "chat-message-author",
            role === "user"
                ? "You"
                : "Smart Property AI"
        );

        const bubble = createElement(
            "div",
            "chat-message-bubble"
        );

        const paragraph = createElement(
            "p",
            "",
            content
        );

        bubble.appendChild(paragraph);

        const time = createElement(
            "time",
            "chat-message-time",
            formatTime()
        );

        time.dateTime = new Date().toISOString();

        messageContent.append(
            author,
            bubble,
            time
        );

        if (role === "assistant") {
            const speechButton = createElement(
                "button",
                "chat-speech-button",
                "Read aloud"
            );

            speechButton.type = "button";
            speechButton.dataset.readMessage = "";
            speechButton.setAttribute(
                "aria-label",
                "Read this message aloud"
            );

            attachSpeechButton(speechButton);
            messageContent.appendChild(speechButton);
        }

        if (role === "user") {
            article.append(messageContent, avatar);
        } else {
            article.append(avatar, messageContent);
        }

        if (options.emergency) {
            article.classList.add(
                "emergency-message"
            );

            bubble.setAttribute("role", "alert");
        }

        if (options.humanReviewRequired) {
            const notice = createElement(
                "p",
                "human-review-notice",
                "Human review is required."
            );

            messageContent.appendChild(notice);
        }

        return article;
    }

    function addMessage(
        role,
        content,
        options = {}
    ) {
        if (!conversation || !content) {
            return;
        }

        const message = createMessage(
            role,
            content,
            options
        );

        if (
            typingIndicator &&
            typingIndicator.parentElement === conversation
        ) {
            conversation.insertBefore(
                message,
                typingIndicator
            );
        } else {
            conversation.appendChild(message);
        }

        scrollToLatestMessage();
    }

    async function parseErrorResponse(response) {
        try {
            const data = await response.json();

            if (typeof data.detail === "string") {
                return data.detail;
            }

            if (Array.isArray(data.detail)) {
                return data.detail
                    .map((error) => error.msg)
                    .filter(Boolean)
                    .join(" ");
            }

            if (typeof data.message === "string") {
                return data.message;
            }
        } catch (error) {
            console.debug(
                "The error response was not JSON.",
                error
            );
        }

        return (
            "The assistant could not process your request. " +
            "Please try again."
        );
    }

    async function sendMessage() {
        if (
            requestInProgress ||
            !messageField
        ) {
            return;
        }

        const message =
            messageField.value.trim();

        if (!message) {
            announce(
                "Enter a message before sending.",
                "error"
            );

            messageField.focus();
            return;
        }

        const endpoint = form.dataset.chatUrl;

        if (!endpoint) {
            announce(
                "The AI chat endpoint is missing.",
                "error"
            );

            return;
        }

        const conversationId =
            conversationIdField?.value || null;

        const csrfToken =
            csrfField?.value || "";

        addMessage("user", message);

        messageField.value = "";
        updateCounter();
        resizeTextarea();
        setLoading(true);

        announce(
            "Your message is being processed."
        );

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                    "X-Requested-With":
                        "XMLHttpRequest",
                    "X-CSRF-Token": csrfToken
                },
                body: JSON.stringify({
                    message,
                    language: getLanguage(),
                    conversation_id:
                        conversationId,
                    page_context:
                        window.location.pathname,
                    consent: true
                })
            });

            if (response.status === 401) {
                window.location.assign(
                    `/login?next=${encodeURIComponent(
                        window.location.pathname
                    )}`
                );

                return;
            }

            if (!response.ok) {
                const errorMessage =
                    await parseErrorResponse(
                        response
                    );

                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (
                conversationIdField &&
                data.conversation_id
            ) {
                conversationIdField.value =
                    data.conversation_id;
            }

            addMessage(
                "assistant",
                data.response,
                {
                    emergency:
                        Boolean(data.emergency),
                    humanReviewRequired:
                        Boolean(
                            data.human_review_required
                        )
                }
            );

            if (data.disclaimer) {
                announce(
                    `${data.response} ${data.disclaimer}`
                );
            } else {
                announce(
                    "The assistant responded."
                );
            }
        } catch (error) {
            console.error(
                "AI assistant request failed.",
                error
            );

            addMessage(
                "assistant",
                (
                    "I could not process your request. " +
                    "Please check your connection and try again."
                )
            );

            announce(
                error.message ||
                    "The assistant is unavailable.",
                "error"
            );
        } finally {
            setLoading(false);
            messageField.focus();
        }
    }

    async function clearConversation() {
        if (
            requestInProgress ||
            !clearButton
        ) {
            return;
        }

        const confirmed = window.confirm(
            "Clear this AI conversation?"
        );

        if (!confirmed) {
            return;
        }

        const endpoint = form.dataset.clearUrl;
        const csrfToken =
            csrfField?.value || "";

        if (!endpoint) {
            announce(
                "The clear-conversation endpoint is missing.",
                "error"
            );

            return;
        }

        clearButton.disabled = true;

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "X-Requested-With":
                        "XMLHttpRequest",
                    "X-CSRF-Token": csrfToken
                }
            });

            if (!response.ok) {
                throw new Error(
                    await parseErrorResponse(response)
                );
            }

            const data = await response.json();

            conversation
                ?.querySelectorAll(
                    ".chat-message:not([data-typing-indicator])"
                )
                .forEach((message) => {
                    message.remove();
                });

            addMessage(
                "assistant",
                (
                    "The conversation has been cleared. " +
                    "How can I help you?"
                )
            );

            if (
                conversationIdField &&
                data.conversation_id
            ) {
                conversationIdField.value =
                    data.conversation_id;
            }

            announce(
                "Conversation cleared."
            );
        } catch (error) {
            console.error(
                "Conversation could not be cleared.",
                error
            );

            announce(
                error.message ||
                    "The conversation could not be cleared.",
                "error"
            );
        } finally {
            clearButton.disabled = false;
        }
    }

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        sendMessage();
    });

    messageField?.addEventListener(
        "keydown",
        (event) => {
            if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.isComposing
            ) {
                event.preventDefault();
                sendMessage();
            }
        }
    );

    messageField?.addEventListener(
        "input",
        () => {
            updateCounter();
            resizeTextarea();
        }
    );

    clearButton?.addEventListener(
        "click",
        clearConversation
    );

    quickPromptButtons.forEach((button) => {
        button.type = "button";

        button.addEventListener("click", () => {
            if (!messageField) {
                return;
            }

            messageField.value =
                button.dataset.aiPrompt || "";

            updateCounter();
            resizeTextarea();
            messageField.focus();

            messageField.scrollIntoView({
                behavior: window.matchMedia(
                    "(prefers-reduced-motion: reduce)"
                ).matches
                    ? "auto"
                    : "smooth",
                block: "center"
            });
        });
    });

    document.querySelectorAll(
        "[data-read-message]"
    ).forEach(attachSpeechButton);

    document.addEventListener(
        "smartproperty:languagechange",
        () => {
            announce(
                "The assistant language has been updated."
            );
        }
    );

    updateCounter();
    resizeTextarea();
    scrollToLatestMessage();

    window.SmartPropertyAI = {
        send(message) {
            if (!messageField) {
                return;
            }

            messageField.value = String(
                message || ""
            );

            updateCounter();
            resizeTextarea();

            return sendMessage();
        },

        clear: clearConversation,

        focus() {
            messageField?.focus();
        }
    };
});