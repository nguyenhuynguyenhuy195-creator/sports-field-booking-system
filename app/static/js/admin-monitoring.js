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

    function updateFieldPicker(picker) {
        const input = picker.querySelector("[data-admin-field-search]");
        const toggle = picker.querySelector("[data-admin-field-toggle]");
        const empty = picker.querySelector("[data-admin-field-empty]");
        const choices = Array.from(picker.querySelectorAll("[data-admin-field-choice]"));
        const query = (input ? input.value : "").trim().toLocaleLowerCase("vi");
        const expanded = picker.dataset.expanded === "true";
        let visibleCount = 0;

        choices.forEach(function (choice) {
            const matches = !query || (choice.dataset.fieldSearchValue || "").toLocaleLowerCase("vi").includes(query);
            const isExtra = choice.hasAttribute("data-admin-field-extra");
            const shouldShow = matches && (Boolean(query) || expanded || !isExtra);
            choice.hidden = !shouldShow;
            if (shouldShow) {
                visibleCount += 1;
            }
        });

        if (toggle) {
            toggle.hidden = Boolean(query);
            const total = Number(toggle.dataset.totalFields || choices.length);
            toggle.textContent = expanded ? "Thu gọn danh sách sân" : `Xem thêm ${Math.max(total - 8, 0)} sân`;
        }
        if (empty) {
            empty.hidden = visibleCount > 0;
        }
    }

    function prepareResponsiveScope(root) {
        if (!root || !window.matchMedia("(max-width: 575.98px)").matches) {
            return;
        }
        const scope = root.querySelector(".admin-scope-panel");
        if (scope) {
            scope.removeAttribute("open");
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
            prepareResponsiveScope(nextRoot);
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
        const fieldToggle = event.target.closest("[data-admin-field-toggle]");
        if (fieldToggle) {
            const picker = fieldToggle.closest("[data-admin-field-picker]");
            if (picker) {
                picker.dataset.expanded = String(picker.dataset.expanded !== "true");
                updateFieldPicker(picker);
            }
            return;
        }

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

    document.addEventListener("input", function (event) {
        if (!event.target.matches("[data-admin-field-search]")) {
            return;
        }
        const picker = event.target.closest("[data-admin-field-picker]");
        if (picker) {
            updateFieldPicker(picker);
        }
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

    prepareResponsiveScope(getRoot());
})();
