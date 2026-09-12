/*
 * Smart Property AI
 * Public listing-page interactions
 *
 * Features:
 * - Search suggestions
 * - Keyboard suggestion navigation
 * - Image fallback
 * - Share button
 * - Print button
 * - Focus helpers
 * - Filter validation
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const searchInputs = document.querySelectorAll(
        "[data-search-suggestions]"
    );

    const propertyImages = document.querySelectorAll(
        "[data-property-image]"
    );

    const shareButtons = document.querySelectorAll(
        "[data-share-listing]"
    );

    const printButtons = document.querySelectorAll(
        "[data-print-listing]"
    );

    const focusButtons = document.querySelectorAll(
        "[data-focus-target]"
    );

    const languageButtons = document.querySelectorAll(
        "[data-open-language-selector]"
    );

    const searchForms = document.querySelectorAll(
        ".listing-search-form, [data-listing-search-form]"
    );

    const PLACEHOLDER_IMAGE = createPlaceholderImage();

    function createPlaceholderImage() {
        const svg = `
            <svg xmlns="http://www.w3.org/2000/svg"
                 width="960"
                 height="600"
                 viewBox="0 0 960 600">
                <rect width="960" height="600" fill="#e2e8f0"/>
                <rect x="240" y="245" width="480" height="250"
                      rx="12" fill="#94a3b8"/>
                <path d="M190 280 480 80 770 280"
                      fill="#64748b"/>
                <rect x="300" y="305" width="105" height="105"
                      fill="#dbeafe"/>
                <rect x="555" y="305" width="105" height="105"
                      fill="#dbeafe"/>
                <rect x="435" y="350" width="90" height="145"
                      fill="#475569"/>
                <text x="480" y="555"
                      text-anchor="middle"
                      font-family="Arial, sans-serif"
                      font-size="32"
                      fill="#334155">
                    Smart Property AI
                </text>
            </svg>
        `;

        return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
    }

    function announce(message, type = "info") {
        const region =
            document.querySelector("[data-listing-status]") ||
            document.querySelector("[data-share-status]");

        if (!region) {
            return;
        }

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
    }

    function debounce(callback, delay = 300) {
        let timer;

        return (...argumentsList) => {
            window.clearTimeout(timer);

            timer = window.setTimeout(() => {
                callback(...argumentsList);
            }, delay);
        };
    }

    function escapeHTML(value) {
        const element = document.createElement("div");
        element.textContent = String(value ?? "");
        return element.innerHTML;
    }

    function validHttpURL(value) {
        if (!value) {
            return false;
        }

        try {
            const url = new URL(value, window.location.origin);

            return (
                url.protocol === "http:" ||
                url.protocol === "https:" ||
                url.protocol === "data:"
            );
        } catch (error) {
            return false;
        }
    }

    /* =====================================================
       Property image fallback
       ===================================================== */

    propertyImages.forEach((image) => {
        image.addEventListener(
            "error",
            () => {
                if (image.dataset.fallbackApplied === "true") {
                    return;
                }

                image.dataset.fallbackApplied = "true";
                image.src = PLACEHOLDER_IMAGE;

                if (!image.alt) {
                    image.alt = "Property image unavailable";
                }
            },
            {
                once: true
            }
        );

        if (!image.getAttribute("src")) {
            image.src = PLACEHOLDER_IMAGE;
        }
    });

    /* =====================================================
       Search suggestions
       ===================================================== */

    function findSuggestionContainer(input) {
        const form = input.closest("form");

        return (
            form?.querySelector(
                "[data-search-suggestions-list]"
            ) ||
            document.querySelector(
                "[data-search-suggestions-list]"
            )
        );
    }

    function hideSuggestions(input, container) {
        if (!container) {
            return;
        }

        container.hidden = true;
        container.innerHTML = "";

        input.setAttribute("aria-expanded", "false");
        input.removeAttribute("aria-activedescendant");
    }

    function suggestionMarkup(suggestions) {
        if (!suggestions.length) {
            return `
                <p class="search-suggestion-message">
                    No matching properties found.
                </p>
            `;
        }

        const items = suggestions.map((suggestion, index) => {
            const title = escapeHTML(
                suggestion.title || "Property"
            );

            const location = escapeHTML(
                suggestion.city ||
                suggestion.address ||
                "Location available on request"
            );

            const rent =
                suggestion.minimum_rent !== null &&
                suggestion.minimum_rent !== undefined
                    ? ` · From ${escapeHTML(
                        suggestion.minimum_rent
                    )} per month`
                    : "";

            const image =
                validHttpURL(suggestion.image_url)
                    ? suggestion.image_url
                    : PLACEHOLDER_IMAGE;

            const url =
                validHttpURL(suggestion.url)
                    ? suggestion.url
                    : "#";

            return `
                <li class="search-suggestion-item">
                    <a
                        id="search-suggestion-${index}"
                        class="search-suggestion-link"
                        href="${escapeHTML(url)}"
                        role="option"
                        aria-selected="false"
                        data-suggestion-index="${index}"
                    >
                        <img
                            class="search-suggestion-image"
                            src="${escapeHTML(image)}"
                            alt=""
                            width="52"
                            height="45"
                            loading="lazy"
                        >

                        <span>
                            <span class="search-suggestion-title">
                                ${title}
                            </span>

                            <span class="search-suggestion-meta">
                                ${location}${rent}
                            </span>
                        </span>
                    </a>
                </li>
            `;
        });

        return `
            <ul
                class="search-suggestion-list"
                role="listbox"
                aria-label="Property suggestions"
            >
                ${items.join("")}
            </ul>
        `;
    }

    async function fetchSuggestions(input, container) {
        const query = input.value.trim();

        if (query.length < 2) {
            hideSuggestions(input, container);
            return;
        }

        const endpoint =
            input.dataset.suggestionsUrl ||
            "/listings/api/search/suggestions";

        const url = new URL(endpoint, window.location.origin);
        url.searchParams.set("q", query);
        url.searchParams.set("limit", "6");

        input.setAttribute("aria-busy", "true");

        try {
            const response = await fetch(url, {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            if (!response.ok) {
                throw new Error(
                    `Suggestion request failed: ${response.status}`
                );
            }

            const data = await response.json();
            const suggestions = Array.isArray(data.suggestions)
                ? data.suggestions
                : [];

            /*
             * Do not show results for an older request after the
             * user has already changed the query.
             */
            if (input.value.trim() !== query) {
                return;
            }

            container.innerHTML = suggestionMarkup(suggestions);
            container.hidden = false;

            input.setAttribute("aria-expanded", "true");

            container.querySelectorAll("img").forEach((image) => {
                image.addEventListener(
                    "error",
                    () => {
                        image.src = PLACEHOLDER_IMAGE;
                    },
                    {
                        once: true
                    }
                );
            });
        } catch (error) {
            console.error(
                "Listing suggestions could not be loaded.",
                error
            );

            hideSuggestions(input, container);
        } finally {
            input.setAttribute("aria-busy", "false");
        }
    }

    function suggestionLinks(container) {
        return Array.from(
            container.querySelectorAll(
                ".search-suggestion-link"
            )
        );
    }

    function setActiveSuggestion(input, container, index) {
        const links = suggestionLinks(container);

        if (!links.length) {
            return;
        }

        const normalizedIndex =
            (index + links.length) % links.length;

        links.forEach((link, linkIndex) => {
            const active = linkIndex === normalizedIndex;

            link.classList.toggle("is-active", active);
            link.setAttribute(
                "aria-selected",
                String(active)
            );
        });

        const activeLink = links[normalizedIndex];

        input.dataset.activeSuggestion =
            String(normalizedIndex);

        input.setAttribute(
            "aria-activedescendant",
            activeLink.id
        );

        activeLink.scrollIntoView({
            block: "nearest"
        });
    }

    searchInputs.forEach((input, inputIndex) => {
        const container = findSuggestionContainer(input);

        if (!container) {
            return;
        }

        if (!container.id) {
            container.id =
                `search-suggestions-${inputIndex + 1}`;
        }

        input.setAttribute("role", "combobox");
        input.setAttribute("aria-autocomplete", "list");
        input.setAttribute("aria-expanded", "false");
        input.setAttribute("aria-controls", container.id);
        input.setAttribute("autocomplete", "off");

        const updateSuggestions = debounce(() => {
            fetchSuggestions(input, container);
        }, 300);

        input.addEventListener("input", () => {
            delete input.dataset.activeSuggestion;
            updateSuggestions();
        });

        input.addEventListener("focus", () => {
            if (
                input.value.trim().length >= 2 &&
                !container.innerHTML.trim()
            ) {
                fetchSuggestions(input, container);
            }
        });

        input.addEventListener("keydown", (event) => {
            if (container.hidden) {
                return;
            }

            const links = suggestionLinks(container);
            let activeIndex = Number.parseInt(
                input.dataset.activeSuggestion ?? "-1",
                10
            );

            if (event.key === "ArrowDown") {
                event.preventDefault();

                activeIndex += 1;

                setActiveSuggestion(
                    input,
                    container,
                    activeIndex
                );
            }

            if (event.key === "ArrowUp") {
                event.preventDefault();

                activeIndex -= 1;

                setActiveSuggestion(
                    input,
                    container,
                    activeIndex
                );
            }

            if (event.key === "Enter" && activeIndex >= 0) {
                const activeLink = links[activeIndex];

                if (activeLink) {
                    event.preventDefault();
                    window.location.assign(activeLink.href);
                }
            }

            if (event.key === "Escape") {
                event.preventDefault();
                hideSuggestions(input, container);
            }
        });

        document.addEventListener("click", (event) => {
            if (
                event.target !== input &&
                !container.contains(event.target)
            ) {
                hideSuggestions(input, container);
            }
        });
    });

    /* =====================================================
       Search form validation
       ===================================================== */

    searchForms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            const minimumRent = form.querySelector(
                "[name='minimum_rent']"
            );

            const maximumRent = form.querySelector(
                "[name='maximum_rent']"
            );

            if (
                minimumRent?.value &&
                maximumRent?.value &&
                Number(minimumRent.value) >
                    Number(maximumRent.value)
            ) {
                event.preventDefault();

                maximumRent.setCustomValidity(
                    "Maximum rent must be equal to or greater than minimum rent."
                );

                maximumRent.reportValidity();
                maximumRent.focus();

                announce(
                    "Maximum rent must be equal to or greater than minimum rent.",
                    "error"
                );

                return;
            }

            maximumRent?.setCustomValidity("");
        });

        const rentFields = form.querySelectorAll(
            "[name='minimum_rent'], [name='maximum_rent']"
        );

        rentFields.forEach((field) => {
            field.addEventListener("input", () => {
                field.setCustomValidity("");
            });
        });
    });

    /* =====================================================
       Share listing
       ===================================================== */

    async function copyToClipboard(text) {
        if (
            navigator.clipboard &&
            window.isSecureContext
        ) {
            await navigator.clipboard.writeText(text);
            return;
        }

        const temporaryInput =
            document.createElement("textarea");

        temporaryInput.value = text;
        temporaryInput.setAttribute("readonly", "");
        temporaryInput.style.position = "fixed";
        temporaryInput.style.opacity = "0";

        document.body.appendChild(temporaryInput);
        temporaryInput.select();

        const successful = document.execCommand("copy");
        temporaryInput.remove();

        if (!successful) {
            throw new Error("Clipboard copy failed.");
        }
    }

    shareButtons.forEach((button) => {
        button.addEventListener("click", async () => {
            const title =
                button.dataset.shareTitle ||
                document.title;

            const url =
                button.dataset.shareUrl ||
                window.location.href;

            try {
                if (navigator.share) {
                    await navigator.share({
                        title,
                        text: `View ${title} on Smart Property AI.`,
                        url
                    });

                    announce("Property shared successfully.");
                    return;
                }

                await copyToClipboard(url);

                announce(
                    "Property link copied to the clipboard."
                );
            } catch (error) {
                if (error.name === "AbortError") {
                    return;
                }

                console.error(
                    "The listing could not be shared.",
                    error
                );

                announce(
                    "The property link could not be shared.",
                    "error"
                );
            }
        });
    });

    /* =====================================================
       Print listing
       ===================================================== */

    printButtons.forEach((button) => {
        button.addEventListener("click", () => {
            window.print();
        });
    });

    /* =====================================================
       Focus and language helpers
       ===================================================== */

    focusButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const targetReference =
                button.dataset.focusTarget;

            const target =
                document.getElementById(targetReference) ||
                document.querySelector(targetReference);

            if (!target) {
                return;
            }

            target.scrollIntoView({
                behavior: window.matchMedia(
                    "(prefers-reduced-motion: reduce)"
                ).matches
                    ? "auto"
                    : "smooth",
                block: "center"
            });

            target.focus();
        });
    });

    languageButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const languageSelector =
                document.querySelector(
                    "#language-selector"
                ) ||
                document.querySelector(
                    "#language-select"
                ) ||
                document.querySelector(
                    "[data-language-selector]"
                );

            if (!languageSelector) {
                announce(
                    "The language selector could not be found.",
                    "error"
                );
                return;
            }

            languageSelector.scrollIntoView({
                behavior: window.matchMedia(
                    "(prefers-reduced-motion: reduce)"
                ).matches
                    ? "auto"
                    : "smooth",
                block: "center"
            });

            languageSelector.focus();
        });
    });

    /* =====================================================
       Public listing API
       ===================================================== */

    window.SmartPropertyListings = {
        search(query) {
            const url = new URL(
                "/listings/search",
                window.location.origin
            );

            if (query) {
                url.searchParams.set("q", query);
            }

            window.location.assign(url);
        },

        share(title, url) {
            if (navigator.share) {
                return navigator.share({
                    title,
                    url
                });
            }

            return copyToClipboard(url);
        },

        print() {
            window.print();
        }
    };
});