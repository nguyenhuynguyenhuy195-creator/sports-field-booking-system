(function () {
    "use strict";

    const rootSelector = "[data-admin-monitoring-root]";
    let activeRequest = null;

    function getRoot() {
        return document.querySelector(rootSelector);
    }

    function isMonitoringUrl(value) {
        const url = new URL(value, window.location.href);
        return url.origin === window.location.origin && url.pathname === "/admin/monitoring";
    }

    function setLoading(isLoading) {
        const root = getRoot();
        if (!root) {
            return;
        }

        root.classList.toggle("is-loading", isLoading);
        root.setAttribute("aria-busy", String(isLoading));
        const status = root.querySelector("[data-admin-monitoring-status]");
        if (status) {
            status.textContent = isLoading ? "Đang cập nhật thông tin giám sát." : "Đã cập nhật thông tin giám sát.";
        }
    }

    async function loadMonitoringPage(targetUrl, options) {
        const settings = Object.assign({ addHistory: true }, options);
        const currentRoot = getRoot();
        if (!currentRoot) {
            window.location.assign(targetUrl);
            return;
        }

        if (activeRequest) {
            activeRequest.abort();
        }

        const controller = new AbortController();
        activeRequest = controller;
        setLoading(true);

        try {
            const response = await fetch(targetUrl, {
                method: "GET",
                headers: { "X-Requested-With": "XMLHttpRequest" },
                credentials: "same-origin",
                signal: controller.signal,
            });

            if (!response.ok) {
                throw new Error(`Không thể tải trang (${response.status}).`);
            }

            const html = await response.text();
            const nextDocument = new DOMParser().parseFromString(html, "text/html");
            const nextRoot = nextDocument.querySelector(rootSelector);
            if (!nextRoot) {
                window.location.assign(response.url || targetUrl);
                return;
            }

            const scrollPosition = { x: window.scrollX, y: window.scrollY };
            currentRoot.replaceWith(nextRoot);
            document.title = nextDocument.title;

            if (settings.addHistory) {
                window.history.pushState({ adminMonitoring: true }, "", response.url || targetUrl);
            }

            window.scrollTo(scrollPosition.x, scrollPosition.y);
            setLoading(false);
        } catch (error) {
            if (error.name === "AbortError") {
                return;
            }

            window.location.assign(targetUrl);
        } finally {
            if (activeRequest === controller) {
                activeRequest = null;
            }
        }
    }

    document.addEventListener("click", function (event) {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return;
        }

        const link = event.target.closest(`${rootSelector} a[href]`);
        if (!link || link.target || link.hasAttribute("download") || !isMonitoringUrl(link.href)) {
            return;
        }

        event.preventDefault();
        loadMonitoringPage(link.href);
    });

    document.addEventListener("submit", function (event) {
        const form = event.target.closest(`${rootSelector} form`);
        if (!form || form.method.toUpperCase() !== "GET" || !isMonitoringUrl(form.action)) {
            return;
        }

        event.preventDefault();
        const targetUrl = new URL(form.action, window.location.href);
        targetUrl.search = new URLSearchParams(new FormData(form)).toString();
        loadMonitoringPage(targetUrl.href);
    });

    window.addEventListener("popstate", function () {
        if (isMonitoringUrl(window.location.href)) {
            loadMonitoringPage(window.location.href, { addHistory: false });
        }
    });
})();
