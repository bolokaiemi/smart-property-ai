/*
 * Smart Property AI
 * Guided apartment search
 *
 * Features:
 * - Multi-step accessible search form
 * - Previous and next navigation
 * - Progress indicator
 * - Keyboard navigation
 * - Optional spoken instructions
 * - Local draft saving
 * - Validation before moving forward
 * - Search summary generation
 *
 * Expected container:
 *   data-guided-search
 *
 * Expected steps:
 *   data-search-step
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const STORAGE_KEY = "smart_property_guided_search";
    const guidedSearchForms = document.querySelectorAll(
        "[data-guided-search]"
    );

    if (!guidedSearchForms.length) {
        return;
    }

    const messages = {
        required: "Please complete the required fields before continuing.",
        saved: "Your search preferences have been saved.",
        restored: "Your saved search preferences have been restored.",
        cleared: "Your saved search preferences have been cleared.",
        completed: "Your apartment search is ready.",
        unavailable: "Guided search is currently unavailable."
    };

    function announce(form, message, type = "info") {
        const status = form.querySelector(
            "[data-guided-search-status]"
        );

        if (!status) {
            return;
        }

        status.textContent = message;
        status.dataset.statusType = type;
        status.setAttribute("role", type === "error" ? "alert" : "status");
        status.setAttribute(
            "aria-live",
            type === "error" ? "assertive" : "polite"
        );
        status.setAttribute("aria-atomic", "true");
    }

    function getFormKey(form, index) {
        return `${STORAGE_KEY}:${form.id || index}`;
    }

    function safeParseJSON(value) {
        try {
            return JSON.parse(value);
        } catch (error) {
            console.warn("Saved guided-search data is invalid.", error);
            return null;
        }
    }

    function saveDraft(form, storageKey) {
        const formData = new FormData(form);
        const draft = {};

        for (const [name, value] of formData.entries()) {
            const field = form.elements.namedItem(name);

            if (
                field instanceof HTMLInputElement &&
                ["password", "file"].includes(field.type)
            ) {
                continue;
            }

            if (Object.prototype.hasOwnProperty.call(draft, name)) {
                if (!Array.isArray(draft[name])) {
                    draft[name] = [draft[name]];
                }

                draft[name].push(value);
            } else {
                draft[name] = value;
            }
        }

        try {
            localStorage.setItem(
                storageKey,
                JSON.stringify({
                    values: draft,
                    step: Number(form.dataset.currentStep || 0),
                    savedAt: new Date().toISOString()
                })
            );
        } catch (error) {
            console.warn("Search preferences could not be saved.", error);
        }
    }

    function restoreDraft(form, storageKey) {
        let savedDraft;

        try {
            savedDraft = safeParseJSON(
                localStorage.getItem(storageKey)
            );
        } catch (error) {
            console.warn("Saved search preferences could not be read.", error);
            return null;
        }

        if (!savedDraft?.values) {
            return null;
        }

        Object.entries(savedDraft.values).forEach(([name, value]) => {
            const fields = form.querySelectorAll(
                `[name="${CSS.escape(name)}"]`
            );

            fields.forEach((field) => {
                if (
                    field instanceof HTMLInputElement &&
                    (field.type === "checkbox" ||
                        field.type === "radio")
                ) {
                    const values = Array.isArray(value)
                        ? value
                        : [value];

                    field.checked = values.includes(field.value);
                    return;
                }

                if (
                    field instanceof HTMLSelectElement &&
                    field.multiple
                ) {
                    const values = Array.isArray(value)
                        ? value
                        : [value];

                    Array.from(field.options).forEach((option) => {
                        option.selected = values.includes(option.value);
                    });

                    return;
                }

                if (
                    field instanceof HTMLInputElement ||
                    field instanceof HTMLTextAreaElement ||
                    field instanceof HTMLSelectElement
                ) {
                    field.value = Array.isArray(value)
                        ? value[0]
                        : value;
                }
            });
        });

        announce(form, messages.restored);

        return Number.isInteger(savedDraft.step)
            ? savedDraft.step
            : null;
    }

    function clearDraft(form, storageKey) {
        try {
            localStorage.removeItem(storageKey);
        } catch (error) {
            console.warn("Saved search preferences could not be cleared.", error);
        }

        announce(form, messages.cleared);
    }

    function getReadableStepText(step) {
        if (!step) {
            return "";
        }

        const clone = step.cloneNode(true);

        clone.querySelectorAll(
            [
                "button",
                "input",
                "select",
                "textarea",
                "script",
                "style",
                "[hidden]",
                "[aria-hidden='true']",
                "[data-speech-ignore]"
            ].join(",")
        ).forEach((element) => element.remove());

        return (clone.textContent || "")
            .replace(/\s+/g, " ")
            .trim();
    }

    function speakStep(form, step) {
        const speechEnabled = form.querySelector(
            "[data-guided-speech-toggle]"
        );

        if (!speechEnabled?.checked) {
            return;
        }

        const text =
            step.dataset.speechText ||
            getReadableStepText(step);

        if (!text) {
            return;
        }

        if (
            window.SmartPropertySpeech &&
            typeof window.SmartPropertySpeech.speak === "function"
        ) {
            window.SmartPropertySpeech.speak(text, {
                language:
                    document.documentElement.lang ||
                    navigator.language,
                rate: 0.95
            });
            return;
        }

        if (
            "speechSynthesis" in window &&
            "SpeechSynthesisUtterance" in window
        ) {
            window.speechSynthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang =
                document.documentElement.lang ||
                navigator.language ||
                "en-US";
            utterance.rate = 0.95;

            window.speechSynthesis.speak(utterance);
        }
    }

    function focusFirstField(step) {
        const heading = step.querySelector(
            "h1, h2, h3, [data-step-heading]"
        );

        if (heading) {
            if (!heading.hasAttribute("tabindex")) {
                heading.setAttribute("tabindex", "-1");
            }

            heading.focus();
            return;
        }

        const focusable = step.querySelector(
            [
                "input:not([disabled])",
                "select:not([disabled])",
                "textarea:not([disabled])",
                "button:not([disabled])",
                "[tabindex]:not([tabindex='-1'])"
            ].join(",")
        );

        focusable?.focus();
    }

    function validateStep(form, step) {
        const controls = step.querySelectorAll(
            "input, select, textarea"
        );

        for (const control of controls) {
            if (
                control.disabled ||
                control.type === "hidden"
            ) {
                continue;
            }

            if (!control.checkValidity()) {
                control.setAttribute("aria-invalid", "true");
                control.reportValidity();
                control.focus();

                announce(form, messages.required, "error");
                return false;
            }

            control.removeAttribute("aria-invalid");
        }

        return true;
    }

    function updateProgress(form, currentIndex, steps) {
        const progressBar = form.querySelector(
            "[data-guided-progress]"
        );

        const progressText = form.querySelector(
            "[data-guided-progress-text]"
        );

        const percentage = Math.round(
            ((currentIndex + 1) / steps.length) * 100
        );

        if (progressBar) {
            progressBar.value = currentIndex + 1;
            progressBar.max = steps.length;
            progressBar.setAttribute(
                "aria-valuenow",
                String(currentIndex + 1)
            );
            progressBar.setAttribute(
                "aria-valuemin",
                "1"
            );
            progressBar.setAttribute(
                "aria-valuemax",
                String(steps.length)
            );
            progressBar.setAttribute(
                "aria-valuetext",
                `Step ${currentIndex + 1} of ${steps.length}`
            );
        }

        if (progressText) {
            progressText.textContent =
                `Step ${currentIndex + 1} of ${steps.length} ` +
                `(${percentage}%)`;
        }

        form.style.setProperty(
            "--guided-search-progress",
            `${percentage}%`
        );
    }

    function updateButtons(form, currentIndex, steps) {
        const previousButtons = form.querySelectorAll(
            "[data-guided-previous]"
        );

        const nextButtons = form.querySelectorAll(
            "[data-guided-next]"
        );

        const submitButtons = form.querySelectorAll(
            "[data-guided-submit]"
        );

        previousButtons.forEach((button) => {
            button.hidden = currentIndex === 0;
            button.disabled = currentIndex === 0;
        });

        nextButtons.forEach((button) => {
            button.hidden = currentIndex === steps.length - 1;
        });

        submitButtons.forEach((button) => {
            button.hidden = currentIndex !== steps.length - 1;
        });
    }

    function updateSummary(form) {
        const summary = form.querySelector(
            "[data-guided-summary]"
        );

        if (!summary) {
            return;
        }

        summary.innerHTML = "";

        const controls = form.querySelectorAll(
            "[data-summary-label]"
        );

        controls.forEach((control) => {
            let value = "";

            if (
                control instanceof HTMLInputElement &&
                (control.type === "checkbox" ||
                    control.type === "radio")
            ) {
                if (!control.checked) {
                    return;
                }

                value =
                    control.dataset.summaryValue ||
                    control.labels?.[0]?.textContent?.trim() ||
                    control.value;
            } else if (control instanceof HTMLSelectElement) {
                value = Array.from(control.selectedOptions)
                    .map((option) => option.textContent.trim())
                    .join(", ");
            } else {
                value = control.value?.trim();
            }

            if (!value) {
                return;
            }

            const row = document.createElement("div");
            row.className = "guided-summary-row";

            const term = document.createElement("dt");
            term.textContent =
                control.dataset.summaryLabel ||
                control.name;

            const description = document.createElement("dd");
            description.textContent = value;

            row.append(term, description);
            summary.append(row);
        });
    }

    function showStep(
        form,
        requestedIndex,
        steps,
        options = {}
    ) {
        const currentIndex = Number(
            form.dataset.currentStep || 0
        );

        const nextIndex = Math.max(
            0,
            Math.min(requestedIndex, steps.length - 1)
        );

        if (
            options.validateCurrent &&
            !validateStep(form, steps[currentIndex])
        ) {
            return false;
        }

        steps.forEach((step, index) => {
            const isCurrent = index === nextIndex;

            step.hidden = !isCurrent;
            step.classList.toggle(
                "is-active",
                isCurrent
            );
            step.setAttribute(
                "aria-hidden",
                String(!isCurrent)
            );

            step.querySelectorAll(
                "input, select, textarea, button"
            ).forEach((control) => {
                if (isCurrent) {
                    if (
                        control.dataset.guidedOriginalTabindex !==
                        undefined
                    ) {
                        control.setAttribute(
                            "tabindex",
                            control.dataset.guidedOriginalTabindex
                        );

                        delete control.dataset.guidedOriginalTabindex;
                    } else {
                        control.removeAttribute("tabindex");
                    }
                } else {
                    if (control.hasAttribute("tabindex")) {
                        control.dataset.guidedOriginalTabindex =
                            control.getAttribute("tabindex");
                    }

                    control.setAttribute("tabindex", "-1");
                }
            });
        });

        form.dataset.currentStep = String(nextIndex);

        updateProgress(form, nextIndex, steps);
        updateButtons(form, nextIndex, steps);

        if (nextIndex === steps.length - 1) {
            updateSummary(form);
        }

        if (options.save !== false) {
            saveDraft(form, options.storageKey);
        }

        if (options.focus !== false) {
            focusFirstField(steps[nextIndex]);
        }

        if (options.speak !== false) {
            speakStep(form, steps[nextIndex]);
        }

        return true;
    }

    function initializeForm(form, formIndex) {
        const steps = Array.from(
            form.querySelectorAll("[data-search-step]")
        );

        if (!steps.length) {
            announce(form, messages.unavailable, "error");
            return;
        }

        const storageKey = getFormKey(form, formIndex);
        const savedStep = restoreDraft(form, storageKey);
        const initialStep = Math.max(
            0,
            Math.min(
                savedStep ?? 0,
                steps.length - 1
            )
        );

        steps.forEach((step, index) => {
            step.dataset.stepIndex = String(index);

            if (!step.id) {
                step.id =
                    `${form.id || "guided-search"}-step-${index + 1}`;
            }
        });

        form.querySelectorAll(
            "[data-guided-next]"
        ).forEach((button) => {
            button.setAttribute("type", "button");

            button.addEventListener("click", () => {
                const currentIndex = Number(
                    form.dataset.currentStep || 0
                );

                showStep(
                    form,
                    currentIndex + 1,
                    steps,
                    {
                        validateCurrent: true,
                        storageKey
                    }
                );
            });
        });

        form.querySelectorAll(
            "[data-guided-previous]"
        ).forEach((button) => {
            button.setAttribute("type", "button");

            button.addEventListener("click", () => {
                const currentIndex = Number(
                    form.dataset.currentStep || 0
                );

                showStep(
                    form,
                    currentIndex - 1,
                    steps,
                    {
                        storageKey
                    }
                );
            });
        });

        form.querySelectorAll(
            "[data-guided-clear]"
        ).forEach((button) => {
            button.setAttribute("type", "button");

            button.addEventListener("click", () => {
                const confirmed = window.confirm(
                    "Clear all saved search preferences?"
                );

                if (!confirmed) {
                    return;
                }

                form.reset();
                clearDraft(form, storageKey);

                showStep(form, 0, steps, {
                    storageKey,
                    save: false
                });
            });
        });

        form.addEventListener("input", () => {
            saveDraft(form, storageKey);
        });

        form.addEventListener("change", () => {
            saveDraft(form, storageKey);
        });

        form.addEventListener("keydown", (event) => {
            if (!event.altKey) {
                return;
            }

            const currentIndex = Number(
                form.dataset.currentStep || 0
            );

            if (event.key === "ArrowRight") {
                event.preventDefault();

                showStep(
                    form,
                    currentIndex + 1,
                    steps,
                    {
                        validateCurrent: true,
                        storageKey
                    }
                );
            }

            if (event.key === "ArrowLeft") {
                event.preventDefault();

                showStep(
                    form,
                    currentIndex - 1,
                    steps,
                    {
                        storageKey
                    }
                );
            }
        });

        form.addEventListener("submit", (event) => {
            const currentIndex = Number(
                form.dataset.currentStep || 0
            );

            if (!validateStep(form, steps[currentIndex])) {
                event.preventDefault();
                return;
            }

            if (!form.checkValidity()) {
                event.preventDefault();

                const invalidField = form.querySelector(":invalid");
                const invalidStep = invalidField?.closest(
                    "[data-search-step]"
                );

                if (invalidStep) {
                    const invalidIndex = steps.indexOf(invalidStep);

                    showStep(form, invalidIndex, steps, {
                        storageKey,
                        focus: false,
                        speak: false
                    });
                }

                invalidField?.reportValidity();
                invalidField?.focus();

                announce(form, messages.required, "error");
                return;
            }

            updateSummary(form);
            clearDraft(form, storageKey);
            announce(form, messages.completed);
        });

        showStep(form, initialStep, steps, {
            storageKey,
            focus: false,
            speak: false,
            save: false
        });
    }

    guidedSearchForms.forEach(initializeForm);

    window.SmartPropertyGuidedSearch = {
        save(form) {
            const forms = Array.from(guidedSearchForms);
            const index = forms.indexOf(form);

            if (index >= 0) {
                saveDraft(form, getFormKey(form, index));
            }
        },

        reset(form) {
            const forms = Array.from(guidedSearchForms);
            const index = forms.indexOf(form);

            if (index < 0) {
                return;
            }

            form.reset();
            clearDraft(form, getFormKey(form, index));
        }
    };
});