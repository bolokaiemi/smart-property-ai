"use strict";

/**
 * Smart Property AI — Tenant Portal
 *
 * This file is scoped to pages containing .tenant-page.
 */
(function tenantPortal() {
    const READY_EVENT = "smart-property:tenant-ready";

    function getTenantPage() {
        return document.querySelector(".tenant-page");
    }

    function prefersReducedMotion() {
        return (
            window.matchMedia &&
            window.matchMedia(
                "(prefers-reduced-motion: reduce)"
            ).matches
        );
    }

    function normaliseStatusText(value) {
        return String(value || "")
            .replace(/[_-]+/g, " ")
            .replace(/\s+/g, " ")
            .trim()
            .replace(/\b\w/g, (letter) =>
                letter.toUpperCase()
            );
    }

    function prepareStatusBadges(page) {
        page.querySelectorAll(
            ".tenant-status"
        ).forEach((badge) => {
            const text = normaliseStatusText(
                badge.textContent
            );

            if (text) {
                badge.textContent = text;
                badge.setAttribute(
                    "aria-label",
                    `Status: ${text}`
                );
            }
        });
    }

    function prepareExternalLinks(page) {
        page.querySelectorAll(
            'a[target="_blank"]'
        ).forEach((link) => {
            const rel = new Set(
                String(
                    link.getAttribute("rel") || ""
                )
                    .split(/\s+/)
                    .filter(Boolean)
            );

            rel.add("noopener");
            rel.add("noreferrer");

            link.setAttribute(
                "rel",
                Array.from(rel).join(" ")
            );
        });
    }

    function prepareDates(page) {
        page.querySelectorAll(
            "time[datetime]"
        ).forEach((timeElement) => {
            const rawValue =
                timeElement.getAttribute("datetime");

            if (
                !rawValue ||
                timeElement.dataset.tenantDateReady ===
                    "true"
            ) {
                return;
            }

            const date = new Date(rawValue);

            if (Number.isNaN(date.getTime())) {
                return;
            }

            timeElement.dataset.tenantDateReady =
                "true";

            if (!timeElement.getAttribute("title")) {
                try {
                    const formatter =
                        new Intl.DateTimeFormat(
                            document.documentElement
                                .lang || "en",
                            {
                                dateStyle: "full",
                                timeStyle: "short"
                            }
                        );

                    timeElement.setAttribute(
                        "title",
                        formatter.format(date)
                    );
                } catch (error) {
                    console.warn(
                        "Unable to format tenant date.",
                        error
                    );
                }
            }
        });
    }

    function makeAlertDismissible(alert) {
        if (
            alert.querySelector(
                "[data-tenant-alert-close]"
            )
        ) {
            return;
        }

        const closeButton =
            document.createElement("button");

        closeButton.type = "button";
        closeButton.className =
            "tenant-alert__close";
        closeButton.dataset.tenantAlertClose =
            "true";
        closeButton.setAttribute(
            "aria-label",
            "Dismiss message"
        );
        closeButton.textContent = "×";

        closeButton.addEventListener(
            "click",
            () => {
                if (prefersReducedMotion()) {
                    alert.remove();
                    return;
                }

                alert.style.transition =
                    "opacity 160ms ease, " +
                    "transform 160ms ease";

                alert.style.opacity = "0";
                alert.style.transform =
                    "translateY(-0.35rem)";

                window.setTimeout(
                    () => alert.remove(),
                    180
                );
            }
        );

        alert.appendChild(closeButton);
    }

    function prepareAlerts(page) {
        page.querySelectorAll(
            ".tenant-alert"
        ).forEach((alert) => {
            makeAlertDismissible(alert);
        });
    }

    function isVisible(element) {
        if (!element || element.hidden) {
            return false;
        }

        const style =
            window.getComputedStyle(element);

        return (
            style.display !== "none" &&
            style.visibility !== "hidden"
        );
    }

    function findAiOverlay() {
        const selectors = [
            "[data-ai-overlay]",
            "#ai-chat-overlay",
            "#chat-overlay",
            ".ai-chat-overlay",
            ".chat-overlay"
        ];

        for (const selector of selectors) {
            const element =
                document.querySelector(selector);

            if (element) {
                return element;
            }
        }

        return null;
    }

    function findAiCloseButton(overlay) {
        return overlay.querySelector(
            [
                "[data-ai-overlay-close]",
                "[data-chat-overlay-close]",
                ".ai-chat-overlay__close",
                ".chat-overlay__close",
                "#close-ai-chat",
                "#close-chat-overlay"
            ].join(", ")
        );
    }

    function openAiOverlay(trigger) {
        const overlay = findAiOverlay();

        if (!overlay) {
            document.dispatchEvent(
                new CustomEvent(
                    "smart-property:open-ai",
                    {
                        detail: {
                            trigger
                        }
                    }
                )
            );

            return;
        }

        overlay.hidden = false;
        overlay.removeAttribute("aria-hidden");
        overlay.setAttribute(
            "aria-modal",
            "true"
        );

        overlay.classList.add(
            "is-open",
            "open",
            "active"
        );

        document.body.classList.add(
            "ai-overlay-open"
        );

        const firstControl =
            overlay.querySelector(
                [
                    "textarea",
                    "input:not([type='hidden'])",
                    "button",
                    "select",
                    "a[href]"
                ].join(", ")
            );

        window.requestAnimationFrame(() => {
            if (firstControl) {
                firstControl.focus();
            }
        });
    }

    function closeAiOverlay(
        overlay,
        trigger
    ) {
        if (!overlay) {
            return;
        }

        overlay.classList.remove(
            "is-open",
            "open",
            "active"
        );

        overlay.setAttribute(
            "aria-hidden",
            "true"
        );

        overlay.hidden = true;

        document.body.classList.remove(
            "ai-overlay-open"
        );

        if (trigger) {
            trigger.focus();
        }
    }

    function prepareAiOverlay(page) {
        const triggers =
            page.querySelectorAll(
                "[data-ai-overlay-open]"
            );

        triggers.forEach((trigger) => {
            if (
                trigger.dataset.tenantAiReady ===
                "true"
            ) {
                return;
            }

            trigger.dataset.tenantAiReady =
                "true";

            trigger.addEventListener(
                "click",
                (event) => {
                    const overlay =
                        findAiOverlay();

                    /*
                     * If chat-overlay.js has already
                     * opened the assistant, do nothing.
                     */
                    if (
                        overlay &&
                        isVisible(overlay)
                    ) {
                        return;
                    }

                    event.preventDefault();
                    openAiOverlay(trigger);
                }
            );
        });

        const overlay = findAiOverlay();

        if (
            !overlay ||
            overlay.dataset
                .tenantOverlayReady === "true"
        ) {
            return;
        }

        overlay.dataset.tenantOverlayReady =
            "true";

        const closeButton =
            findAiCloseButton(overlay);

        if (closeButton) {
            closeButton.addEventListener(
                "click",
                () => {
                    const trigger =
                        page.querySelector(
                            "[data-ai-overlay-open]"
                        );

                    closeAiOverlay(
                        overlay,
                        trigger
                    );
                }
            );
        }

        overlay.addEventListener(
            "click",
            (event) => {
                if (event.target !== overlay) {
                    return;
                }

                const trigger =
                    page.querySelector(
                        "[data-ai-overlay-open]"
                    );

                closeAiOverlay(
                    overlay,
                    trigger
                );
            }
        );

        document.addEventListener(
            "keydown",
            (event) => {
                if (
                    event.key !== "Escape" ||
                    !isVisible(overlay)
                ) {
                    return;
                }

                const trigger =
                    page.querySelector(
                        "[data-ai-overlay-open]"
                    );

                closeAiOverlay(
                    overlay,
                    trigger
                );
            }
        );
    }

    function prepareServiceCards(page) {
        page.querySelectorAll(
            ".tenant-service-card[href]"
        ).forEach((card) => {
            card.addEventListener(
                "keydown",
                (event) => {
                    if (
                        event.key === " " &&
                        event.currentTarget ===
                            document.activeElement
                    ) {
                        event.preventDefault();
                        event.currentTarget.click();
                    }
                }
            );
        });
    }

    function initialiseTenantPortal() {
        const page = getTenantPage();

        if (
            !page ||
            page.dataset.tenantReady ===
                "true"
        ) {
            return;
        }

        page.dataset.tenantReady = "true";

        prepareStatusBadges(page);
        prepareExternalLinks(page);
        prepareDates(page);
        prepareAlerts(page);
        prepareAiOverlay(page);
        prepareServiceCards(page);

        document.dispatchEvent(
            new CustomEvent(READY_EVENT, {
                detail: {
                    page
                }
            })
        );
    }

    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initialiseTenantPortal,
            {
                once: true
            }
        );
    } else {
        initialiseTenantPortal();
    }
})();