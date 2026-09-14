(() => {
    "use strict";
    const center = document.querySelector("[data-notification-center]");
    if (!center) return;
    const items = center.querySelector("[data-notification-items]");
    const badge = center.querySelector("[data-notification-count]");
    const bell = center.querySelector("#notificationBell");
    const interval = 30000;
    let inFlight = false;
    let stopped = false;

    // Keep the two overlays mutually exclusive, using the chatbot's existing
    // close control (which preserves its conversation and draft).
    const chatLauncher = document.querySelector("[data-chatbot-launcher]");
    const chatPanel = document.querySelector("[data-chatbot-panel]");
    const chatClose = document.querySelector("[data-chatbot-close]");
    bell.addEventListener("show.bs.dropdown", () => {
        if (chatPanel && !chatPanel.hidden && chatClose) {
            chatClose.click();
            bell.focus();
        }
    });
    chatLauncher?.addEventListener("click", () => {
        window.bootstrap?.Dropdown.getInstance(bell)?.hide();
    });

    function readableTime(value) {
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("vi-VN");
    }
    document.querySelectorAll("[data-notification-time]").forEach((node) => {
        node.textContent = readableTime(node.dateTime);
    });

    function localTarget(value) {
        return typeof value === "string" && /^\/(?:notifications|bookings(?:\/[A-Za-z0-9_-]+)?|matches(?:\/[0-9]+)?)$/.test(value)
            ? value : "/notifications";
    }

    function render(payload) {
        if (!Number.isInteger(payload.unread_count) || payload.unread_count < 0 || !Array.isArray(payload.notifications)) return;
        const fragment = document.createDocumentFragment();
        payload.notifications.slice(0, 5).forEach((item) => {
            if (!Number.isInteger(item.id) || item.id <= 0) return;
            const wrapper = document.createElement("div");
            wrapper.className = "notification-item" + (item.is_read ? "" : " notification-unread");
            const link = document.createElement("a");
            link.className = "dropdown-item py-2";
            link.href = localTarget(item.target_url);
            const title = document.createElement("strong");
            title.className = "d-block small";
            title.textContent = item.title;
            const message = document.createElement("span");
            message.className = "d-block small notification-message";
            message.textContent = item.message;
            const time = document.createElement("time");
            time.className = "small text-secondary";
            time.dateTime = item.created_at;
            time.textContent = readableTime(item.created_at);
            link.append(title, message, time);
            wrapper.append(link);
            if (!item.is_read) {
                // Two explicit actions preserve native links and avoid GET mutations.
                const form = document.createElement("form");
                form.method = "post";
                form.action = `/notifications/${item.id}/read`;
                form.className = "px-3 pb-2";
                const csrf = document.createElement("input");
                csrf.type = "hidden";
                csrf.name = "csrf_token";
                csrf.value = center.dataset.csrfToken;
                const button = document.createElement("button");
                button.type = "submit";
                button.className = "btn btn-sm btn-outline-secondary";
                button.textContent = "Đánh dấu đã đọc";
                form.append(csrf, button);
                wrapper.append(form);
            }
            fragment.append(wrapper);
        });
        if (!fragment.childNodes.length) {
            const empty = document.createElement("p");
            empty.className = "px-3 small text-secondary";
            empty.textContent = "Bạn chưa có thông báo nào.";
            fragment.append(empty);
        }
        // Do not replace a focused dropdown action while someone is using it.
        if (!items.contains(document.activeElement)) items.replaceChildren(fragment);
        badge.hidden = payload.unread_count === 0;
        badge.textContent = payload.unread_count > 99 ? "99+" : String(payload.unread_count);
        bell.setAttribute("aria-label", `Thông báo, ${payload.unread_count} chưa đọc`);
    }

    async function poll() {
        if (inFlight || stopped || document.hidden) return;
        inFlight = true;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(center.dataset.recentUrl, {
                credentials: "same-origin", cache: "no-store", signal: controller.signal,
                headers: { Accept: "application/json" },
            });
            if (response.redirected || response.status === 401 || response.status === 403) {
                stopped = true;
                return;
            }
            if (response.ok) render(await response.json());
        } catch (_) {
            // Keep the previous display on a temporary network/server failure.
        } finally {
            clearTimeout(timeout);
            inFlight = false;
        }
    }
    poll();
    setInterval(poll, interval);
})();
