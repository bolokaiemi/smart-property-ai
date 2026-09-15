(() => {
    "use strict";

    const form = document.querySelector("#ai-chat-form, [data-ai-chat-form], #assistant-form");
    if (!form) return;

    const input = form.querySelector("#ai-message, [name='message'], [data-ai-message]");
    const messages = document.querySelector("#ai-chat-messages, [data-ai-messages], #assistant-messages");
    const send = form.querySelector("button[type='submit'], [data-ai-submit]");
    const language = document.querySelector("#ai-language, [data-ai-language], #language-select");
    const status = document.querySelector("#ai-status, [data-ai-status]");

    if (!input || !messages || !send) {
        console.warn("AI chat needs a message input, a message container, and a submit button.");
        return;
    }

    let busy = false;
    let lastReply = "";
    let conversationId = null;
    let recognition = null;
    messages.setAttribute("aria-live", "polite");

    function currentLanguage() {
        return (language?.value || document.documentElement.lang || "en")
            .trim().toLowerCase().split("-")[0] || "en";
    }

    function announce(value, error = false) {
        if (!status) return;
        status.textContent = value;
        status.setAttribute("role", error ? "alert" : "status");
    }

    function addMessage(role, value) {
        const item = document.createElement("div");
        item.className = "ai-message ai-message--" + role;

        const title = document.createElement("strong");
        title.className = "ai-message__label";
        title.textContent = role === "user" ? "You" : "Smart Property AI";

        const content = document.createElement("p");
        content.className = "ai-message__text";
        content.textContent = value; // Never interpret messages as HTML.

        item.append(title, content);
        messages.append(item);
        item.scrollIntoView({ block: "nearest" });
    }

    function setBusy(value) {
        busy = value;
        send.disabled = value;
        input.disabled = value;
        form.setAttribute("aria-busy", String(value));

        if (value) announce("Smart Property AI is responding...");
        else input.focus();
    }

    async function onSubmit(event) {
        event.preventDefault();
        if (busy) return;

        const question = input.value.trim();

        if (!question) {
            announce("Please type or dictate a question.", true);
            input.focus();
            return;
        }

        if (question.length > 4000) {
            announce("Please keep your question under 4,000 characters.", true);
            return;
        }

        addMessage("user", question);
        input.value = "";
        setBusy(true);

        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), 30000);

        try {
            const response = await fetch("/api/ai/chat", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({
                    message: question,
                    language: currentLanguage(),
                    conversation_id: conversationId
                }),
                signal: controller.signal
            });

            let data;

            try {
                data = await response.json();
            } catch (_) {
                throw new Error("The server returned an invalid response.");
            }

            if (response.status === 401 || response.status === 403) {
                addMessage("assistant", "Please log in to continue using the AI assistant.");

                const link = document.createElement("a");
                link.href = "/login?next=" + encodeURIComponent("/ai-assistant");
                link.textContent = "Go to login";
                link.className = "button button-primary";
                messages.append(link);

                announce("Your login session has expired.", true);
                return;
            }

            if (!response.ok) {
                const detail = typeof data.detail === "string" ? data.detail
                    : typeof data.error === "string" ? data.error
                    : "Your request could not be completed.";

                throw new Error(detail);
            }

            if (typeof data.reply !== "string" || !data.reply.trim()) {
                throw new Error("The AI assistant returned an empty reply.");
            }

            conversationId = data.conversation_id || conversationId;
            lastReply = data.reply.trim();
            addMessage("assistant", lastReply);

            if (data.disclaimer) announce(data.disclaimer);
            else announce("");
        } catch (error) {
            const detail = error.name === "AbortError"
                ? "The assistant timed out. Please try again."
                : error.message || "Unable to contact the assistant.";

            addMessage("assistant", detail);
            announce(detail, true);
            input.value = question;
        } finally {
            window.clearTimeout(timer);
            setBusy(false);
        }
    }

    form.addEventListener("submit", onSubmit);

    input.addEventListener("keydown", (event) => {
        if (
            input.tagName === "TEXTAREA" &&
            event.key === "Enter" &&
            !event.shiftKey &&
            !event.isComposing
        ) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    document.querySelector("#ai-read-reply, [data-ai-read-reply]")
        ?.addEventListener("click", () => {
            if (!lastReply) {
                announce("There is no reply to read yet.", true);
                return;
            }

            if (!("speechSynthesis" in window)) {
                announce("Speech output is unavailable in this browser.", true);
                return;
            }

            window.speechSynthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(lastReply);
            utterance.lang = currentLanguage();
            window.speechSynthesis.speak(utterance);
        });

    document.querySelector("#ai-stop-speech, [data-ai-stop-speech]")
        ?.addEventListener("click", () => {
            if ("speechSynthesis" in window) window.speechSynthesis.cancel();
        });

    const voice = document.querySelector("#ai-voice-input, [data-ai-voice-input]");

    voice?.addEventListener("click", () => {
        const SpeechRecognition =
            window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            announce("Voice input is unavailable in this browser.", true);
            return;
        }

        if (recognition) {
            recognition.stop();
            return;
        }

        recognition = new SpeechRecognition();
        recognition.lang = currentLanguage();
        recognition.interimResults = false;

        recognition.onresult = (event) => {
            const spoken = event.results[0][0].transcript.trim();
            input.value = [input.value.trim(), spoken]
                .filter(Boolean)
                .join(" ");
            input.focus();
        };

        recognition.onerror = () => {
            announce("Voice input failed. Please type instead.", true);
        };

        recognition.onend = () => {
            recognition = null;
            voice.setAttribute("aria-pressed", "false");
        };

        voice.setAttribute("aria-pressed", "true");
        announce("Listening...");
        recognition.start();
    });
})();