/*
 * Smart Property AI
 * Language selector
 *
 * Features:
 * - Saves the selected language in localStorage and a cookie
 * - Updates the <html lang=""> attribute
 * - Synchronizes all language selectors on the page
 * - Optionally submits a FastAPI language form
 * - Supports RTL languages
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const STORAGE_KEY = "smart_property_language";
    const COOKIE_NAME = "smart_property_language";

    const supportedLanguages = {
        en: { name: "English", direction: "ltr" },
        de: { name: "Deutsch", direction: "ltr" },
        fr: { name: "Français", direction: "ltr" },
        es: { name: "Español", direction: "ltr" },
        it: { name: "Italiano", direction: "ltr" },
        pt: { name: "Português", direction: "ltr" },
        nl: { name: "Nederlands", direction: "ltr" },
        pl: { name: "Polski", direction: "ltr" },
        tr: { name: "Türkçe", direction: "ltr" },
        ar: { name: "العربية", direction: "rtl" },
        fa: { name: "فارسی", direction: "rtl" },
        ur: { name: "اردو", direction: "rtl" },
        he: { name: "עברית", direction: "rtl" },
        hi: { name: "हिन्दी", direction: "ltr" },
        zh: { name: "中文", direction: "ltr" },
        ja: { name: "日本語", direction: "ltr" },
        ko: { name: "한국어", direction: "ltr" },
        ru: { name: "Русский", direction: "ltr" },
        uk: { name: "Українська", direction: "ltr" },
        sw: { name: "Kiswahili", direction: "ltr" }
    };

    const selectors = document.querySelectorAll(
        "#language-selector, #language-select, " +
        "select[name='language'], [data-language-selector]"
    );

    /**
     * Converts values such as en-US into en.
     */
    function normalizeLanguage(language) {
        if (!language || typeof language !== "string") {
            return "en";
        }

        const normalized = language
            .trim()
            .toLowerCase()
            .replace("_", "-");

        if (supportedLanguages[normalized]) {
            return normalized;
        }

        const shortCode = normalized.split("-")[0];

        return supportedLanguages[shortCode] ? shortCode : "en";
    }

    function getCookie(name) {
        const prefix = `${encodeURIComponent(name)}=`;
        const cookies = document.cookie ? document.cookie.split(";") : [];

        for (const cookie of cookies) {
            const value = cookie.trim();

            if (value.startsWith(prefix)) {
                return decodeURIComponent(value.substring(prefix.length));
            }
        }

        return null;
    }

    function saveLanguage(language) {
        try {
            localStorage.setItem(STORAGE_KEY, language);
        } catch (error) {
            console.warn("Language preference could not be saved locally.", error);
        }

        const secure = window.location.protocol === "https:" ? "; Secure" : "";

        document.cookie =
            `${encodeURIComponent(COOKIE_NAME)}=` +
            `${encodeURIComponent(language)}; ` +
            `Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
    }

    function getSavedLanguage() {
        try {
            const storedLanguage = localStorage.getItem(STORAGE_KEY);

            if (storedLanguage) {
                return normalizeLanguage(storedLanguage);
            }
        } catch (error) {
            console.warn("Saved language could not be read.", error);
        }

        const cookieLanguage = getCookie(COOKIE_NAME);

        if (cookieLanguage) {
            return normalizeLanguage(cookieLanguage);
        }

        const pageLanguage = document.documentElement.lang;

        if (pageLanguage) {
            return normalizeLanguage(pageLanguage);
        }

        return normalizeLanguage(navigator.language || "en");
    }

    function updateDocumentLanguage(language) {
        const languageInformation =
            supportedLanguages[language] || supportedLanguages.en;

        document.documentElement.lang = language;
        document.documentElement.dir = languageInformation.direction;

        document.body.classList.toggle(
            "rtl-language",
            languageInformation.direction === "rtl"
        );
    }

    function synchronizeSelectors(language) {
        selectors.forEach((selector) => {
            const matchingOption = Array.from(selector.options || []).find(
                (option) => normalizeLanguage(option.value) === language
            );

            if (matchingOption) {
                selector.value = matchingOption.value;
            }
        });
    }

    function announceLanguage(language) {
        const liveRegion = document.querySelector(
            "#language-status, [data-language-status]"
        );

        if (!liveRegion) {
            return;
        }

        const languageName =
            supportedLanguages[language]?.name || language.toUpperCase();

        liveRegion.textContent = `Language changed to ${languageName}.`;
    }

    function dispatchLanguageEvent(language) {
        document.dispatchEvent(
            new CustomEvent("smartproperty:languagechange", {
                detail: {
                    language,
                    direction:
                        supportedLanguages[language]?.direction || "ltr"
                }
            })
        );
    }

    /**
     * Sends the preference to FastAPI when an endpoint is configured.
     *
     * Add this to a selector:
     * data-language-url="/language"
     */
    async function sendLanguageToServer(selector, language) {
        const endpoint =
            selector.dataset.languageUrl ||
            document.body.dataset.languageUrl;

        if (!endpoint) {
            return false;
        }

        const csrfToken =
            document.querySelector(
                "meta[name='csrf-token']"
            )?.getAttribute("content") ||
            document.querySelector(
                "input[name='csrf_token']"
            )?.value ||
            "";

        const formData = new FormData();
        formData.append("language", language);

        if (csrfToken) {
            formData.append("csrf_token", csrfToken);
        }

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                body: formData,
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            if (!response.ok) {
                throw new Error(
                    `Language request failed with status ${response.status}.`
                );
            }

            const contentType =
                response.headers.get("content-type") || "";

            if (contentType.includes("application/json")) {
                return await response.json();
            }

            return true;
        } catch (error) {
            console.error(
                "The language preference could not be sent to the server.",
                error
            );

            return false;
        }
    }

    function setLoadingState(selector, loading) {
        selector.disabled = loading;
        selector.setAttribute("aria-busy", String(loading));
    }

    async function changeLanguage(selector) {
        const language = normalizeLanguage(selector.value);

        saveLanguage(language);
        updateDocumentLanguage(language);
        synchronizeSelectors(language);
        announceLanguage(language);
        dispatchLanguageEvent(language);

        const shouldReload =
            selector.dataset.reload === "true" ||
            document.body.dataset.languageReload === "true";

        setLoadingState(selector, true);

        const serverResult = await sendLanguageToServer(
            selector,
            language
        );

        setLoadingState(selector, false);

        /*
         * The server may return:
         * {"redirect_url": "/de/dashboard"}
         */
        if (
            serverResult &&
            typeof serverResult === "object" &&
            serverResult.redirect_url
        ) {
            window.location.assign(serverResult.redirect_url);
            return;
        }

        if (shouldReload) {
            window.location.reload();
        }
    }

    function initializeSelector(selector) {
        if (!selector.getAttribute("aria-label")) {
            selector.setAttribute("aria-label", "Select language");
        }

        selector.addEventListener("change", () => {
            changeLanguage(selector);
        });
    }

    const selectedLanguage = getSavedLanguage();

    updateDocumentLanguage(selectedLanguage);
    synchronizeSelectors(selectedLanguage);

    selectors.forEach(initializeSelector);

    /*
     * Makes language switching available to other JavaScript files:
     *
     * window.SmartPropertyLanguage.set("de");
     * window.SmartPropertyLanguage.get();
     */
    window.SmartPropertyLanguage = {
        get() {
            return normalizeLanguage(
                document.documentElement.lang || selectedLanguage
            );
        },

        set(language) {
            const normalizedLanguage = normalizeLanguage(language);

            saveLanguage(normalizedLanguage);
            updateDocumentLanguage(normalizedLanguage);
            synchronizeSelectors(normalizedLanguage);
            announceLanguage(normalizedLanguage);
            dispatchLanguageEvent(normalizedLanguage);
        },

        supported() {
            return { ...supportedLanguages };
        }
    };
});