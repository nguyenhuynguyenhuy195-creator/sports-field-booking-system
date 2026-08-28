(function () {
    "use strict";

    const pendingKey = "admin:navigation:pending";
    const returnKeyPrefix = "admin:navigation:return:";
    const pendingLifetimeMs = 15000;
    let accountRequestController = null;

    function safeRead(key) {
        try {
            return JSON.parse(window.sessionStorage.getItem(key) || "null");
        } catch (_error) {
            return null;
        }
    }

    function safeWrite(key, value) {
        try {
            window.sessionStorage.setItem(key, JSON.stringify(value));
        } catch (_error) {
            // Navigation remains fully functional when storage is unavailable.
        }
    }

    function safeRemove(key) {
        try {
            window.sessionStorage.removeItem(key);
        } catch (_error) {
            // Nothing else is required for progressive enhancement.
        }
    }

    function getWorkspace(url) {
        const path = url.pathname.replace(/\/$/, "") || "/";
        if (/^\/admin\/(?:accounts|users)(?:\/\d+)?$/.test(path)) {
            return "accounts";
        }
        if (path === "/admin/owner-applications") {
            return "owner-applications";
        }
        if (path === "/admin/venues") {
            return "venues";
        }
        if (path === "/admin/monitoring") {
            return "monitoring";
        }
        return "";
    }

    function canonicalUrl(url) {
        const copy = new URL(url.href);
        copy.hash = "";
        copy.searchParams.sort();
        return `${copy.pathname}${copy.search}`;
    }

    function savePending(targetUrl, workspace, position) {
        safeWrite(pendingKey, {
            target: canonicalUrl(targetUrl),
            workspace,
            x: position.x,
            y: position.y,
            createdAt: Date.now(),
        });
    }

    function restorePendingNavigation() {
        const pending = safeRead(pendingKey);
        if (!pending) {
            return;
        }

        safeRemove(pendingKey);
        const currentUrl = new URL(window.location.href);
        if (
            Date.now() - Number(pending.createdAt || 0) > pendingLifetimeMs ||
            pending.workspace !== getWorkspace(currentUrl) ||
            pending.target !== canonicalUrl(currentUrl)
        ) {
            return;
        }

        window.requestAnimationFrame(function () {
            window.requestAnimationFrame(function () {
                window.scrollTo(Number(pending.x || 0), Number(pending.y || 0));
            });
        });
    }

    function prepareReturnLink() {
        const link = document.querySelector("[data-admin-workspace-return]");
        if (!link) {
            return;
        }

        const workspace = link.dataset.adminWorkspaceReturn || "";
        const saved = safeRead(`${returnKeyPrefix}${workspace}`);
        if (!saved || !saved.url || Date.now() - Number(saved.createdAt || 0) > 3600000) {
            return;
        }

        const savedUrl = new URL(saved.url, window.location.origin);
        if (savedUrl.origin !== window.location.origin || getWorkspace(savedUrl) !== workspace) {
            return;
        }

        link.href = savedUrl.href;
        link.addEventListener("click", function () {
            savePending(savedUrl, workspace, {
                x: Number(saved.x || 0),
                y: Number(saved.y || 0),
            });
        });
    }

    function syncFlashMessages(nextDocument, currentRoot) {
        const currentFlash = document.querySelector(".admin-flash-container");
        const nextFlash = nextDocument.querySelector(".admin-flash-container");
        if (currentFlash) {
            currentFlash.remove();
        }
        if (nextFlash) {
            currentRoot.before(nextFlash.cloneNode(true));
        }
    }

    function finishAccountNavigation(nextRoot, options) {
        const detail = nextRoot.querySelector(".admin-account-detail");
        if (options.focusDetail && detail) {
            detail.focus({ preventScroll: true });
        }

        window.requestAnimationFrame(function () {
            if (
                options.focusDetail &&
                detail &&
                window.matchMedia("(max-width: 767.98px)").matches
            ) {
                const reduceMotion = window.matchMedia(
                    "(prefers-reduced-motion: reduce)"
                ).matches;
                detail.scrollIntoView({
                    behavior: reduceMotion ? "auto" : "smooth",
                    block: "start",
                });
                return;
            }
            window.scrollTo(options.scroll.x, options.scroll.y);
        });
    }

    async function loadAccountPage(targetUrl, options) {
        const settings = Object.assign(
            { addHistory: true, focusDetail: true, restoreScroll: null },
            options
        );
        const currentRoot = document.querySelector("[data-admin-account-root]");
        if (!currentRoot || typeof window.fetch !== "function") {
            window.location.assign(targetUrl.href);
            return;
        }

        if (accountRequestController) {
            accountRequestController.abort();
        }
        const requestController = new AbortController();
        accountRequestController = requestController;
        currentRoot.setAttribute("aria-busy", "true");
        const status = currentRoot.querySelector("[data-admin-account-status]");
        if (status) {
            status.textContent = "Đang tải thông tin tài khoản.";
        }

        try {
            const response = await window.fetch(targetUrl.href, {
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
                signal: requestController.signal,
            });
            const responseUrl = new URL(response.url || targetUrl.href);
            const nextDocument = new DOMParser().parseFromString(
                await response.text(),
                "text/html"
            );
            const nextRoot = nextDocument.querySelector("[data-admin-account-root]");
            if (!response.ok || getWorkspace(responseUrl) !== "accounts" || !nextRoot) {
                window.location.assign(responseUrl.href);
                return;
            }

            const scroll = settings.restoreScroll || {
                x: window.scrollX,
                y: window.scrollY,
            };
            if (settings.addHistory) {
                window.history.replaceState(
                    Object.assign({}, window.history.state, {
                        adminAccounts: true,
                        adminScroll: { x: window.scrollX, y: window.scrollY },
                    }),
                    "",
                    window.location.href
                );
            }

            syncFlashMessages(nextDocument, currentRoot);
            currentRoot.replaceWith(nextRoot);
            document.title = nextDocument.title;

            if (settings.addHistory) {
                window.history.pushState(
                    { adminAccounts: true, adminScroll: scroll },
                    "",
                    responseUrl.href
                );
            }
            finishAccountNavigation(nextRoot, {
                focusDetail: settings.focusDetail,
                scroll,
            });
        } catch (error) {
            if (error.name !== "AbortError") {
                window.location.assign(targetUrl.href);
            }
        } finally {
            if (accountRequestController === requestController) {
                accountRequestController = null;
                const activeRoot = document.querySelector("[data-admin-account-root]");
                if (activeRoot) {
                    activeRoot.removeAttribute("aria-busy");
                }
            }
        }
    }

    document.addEventListener("click", function (event) {
        if (
            event.defaultPrevented ||
            event.button !== 0 ||
            event.metaKey ||
            event.ctrlKey ||
            event.shiftKey ||
            event.altKey
        ) {
            return;
        }

        const link = event.target.closest("a[href]");
        if (!link || link.target || link.hasAttribute("download")) {
            return;
        }

        const currentUrl = new URL(window.location.href);
        const targetUrl = new URL(link.href, currentUrl);
        if (targetUrl.origin !== currentUrl.origin) {
            return;
        }
        if (
            targetUrl.href === currentUrl.href &&
            link.matches("[data-admin-account-detail-link]")
        ) {
            event.preventDefault();
            return;
        }
        if (targetUrl.href === currentUrl.href) {
            return;
        }

        const currentWorkspace = getWorkspace(currentUrl);
        const targetWorkspace = getWorkspace(targetUrl);
        const position = { x: window.scrollX, y: window.scrollY };

        if (
            link.matches("[data-admin-account-detail-link]") &&
            currentWorkspace === "accounts" &&
            targetWorkspace === "accounts"
        ) {
            event.preventDefault();
            loadAccountPage(targetUrl);
            return;
        }

        if (link.matches("[data-admin-workspace-detail-link]") && currentWorkspace) {
            safeWrite(`${returnKeyPrefix}${currentWorkspace}`, {
                url: currentUrl.href,
                x: position.x,
                y: position.y,
                createdAt: Date.now(),
            });
            return;
        }

        if (
            currentWorkspace &&
            currentWorkspace === targetWorkspace &&
            !(currentWorkspace === "monitoring" && link.closest("[data-admin-monitoring-root]"))
        ) {
            savePending(targetUrl, targetWorkspace, position);
        }
    });

    document.addEventListener("submit", function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || form.method.toUpperCase() !== "GET") {
            return;
        }

        const currentUrl = new URL(window.location.href);
        const targetUrl = new URL(form.action || currentUrl.href, currentUrl);
        targetUrl.search = new URLSearchParams(new FormData(form)).toString();
        const workspace = getWorkspace(currentUrl);
        if (
            workspace &&
            workspace === getWorkspace(targetUrl) &&
            !(workspace === "monitoring" && form.closest("[data-admin-monitoring-root]"))
        ) {
            savePending(targetUrl, workspace, { x: window.scrollX, y: window.scrollY });
        }
    });

    document.addEventListener("shown.bs.tab", function (event) {
        if (!window.matchMedia("(max-width: 767.98px)").matches) {
            return;
        }
        if (!event.target.matches(".admin-owner-list-item, .admin-venue-list-item")) {
            return;
        }

        const targetSelector = event.target.getAttribute("data-bs-target");
        const panel = targetSelector ? document.querySelector(targetSelector) : null;
        if (!panel) {
            return;
        }

        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        panel.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
        panel.focus({ preventScroll: true });
    });

    window.addEventListener("popstate", function (event) {
        const currentUrl = new URL(window.location.href);
        if (
            getWorkspace(currentUrl) === "accounts" &&
            document.querySelector("[data-admin-account-root]")
        ) {
            loadAccountPage(currentUrl, {
                addHistory: false,
                focusDetail: false,
                restoreScroll: event.state?.adminScroll || null,
            });
        }
    });

    prepareReturnLink();
    restorePendingNavigation();
})();
