// Match chat room: 5-second polling by after_id, no WebSocket/SSE.
// Every piece of user-controlled data is written with textContent so a message
// can never become markup.
document.addEventListener("DOMContentLoaded", () => {
    const room = document.querySelector("[data-match-chat]");
    if (!room) {
        return;
    }

    const timeline = room.querySelector("[data-chat-timeline]");
    const emptyState = room.querySelector("[data-chat-empty]");
    const form = room.querySelector("[data-chat-form]");
    const input = room.querySelector("[data-chat-input]");
    const sendButton = room.querySelector("[data-chat-send]");
    const errorBox = room.querySelector("[data-chat-error]");
    const readOnlyBox = room.querySelector("[data-chat-readonly]");
    const readOnlyText = room.querySelector("[data-chat-readonly-text]");
    const messagesUrl = room.dataset.messagesUrl;
    const sendUrl = room.dataset.sendUrl;

    // The polling cursor and the set of rendered ids are deliberately separate.
    // A message this browser posted is rendered immediately, but it must NOT
    // move the cursor: another member's message may have landed in between, and
    // jumping the cursor past it would lose it until a reload.
    const renderedIds = new Set();
    let pollAfterId = Number.parseInt(room.dataset.lastId || "0", 10) || 0;
    let canSend = Boolean(form);
    let sending = false;
    let polling = false;
    let timer = null;

    const POLL_INTERVAL_MS = 5000;

    timeline.querySelectorAll("[data-message-id]").forEach((node) => {
        const id = Number.parseInt(node.dataset.messageId || "", 10);
        if (Number.isInteger(id)) {
            renderedIds.add(id);
        }
    });

    const scrollToLatest = () => {
        timeline.scrollTop = timeline.scrollHeight;
    };

    const showError = (message) => {
        if (!errorBox) {
            return;
        }
        errorBox.textContent = message;
        errorBox.classList.remove("d-none");
    };

    const clearError = () => {
        if (!errorBox) {
            return;
        }
        errorBox.textContent = "";
        errorBox.classList.add("d-none");
    };

    const buildElement = (tag, className, text) => {
        const element = document.createElement(tag);
        if (className) {
            element.className = className;
        }
        if (text !== undefined && text !== null) {
            element.textContent = text;
        }
        return element;
    };

    const renderMessage = (message) => {
        const item = document.createElement("li");
        item.dataset.messageId = String(message.id);

        if (message.type === "SYSTEM") {
            item.className = "match-chat-item match-chat-item-system";
            if (message.event_type) {
                item.dataset.eventType = message.event_type;
            }
            const body = buildElement("div", "match-chat-system-body");
            body.appendChild(buildElement("span", "match-chat-system-label", "Hệ thống"));
            body.appendChild(buildElement("p", "match-chat-content", message.content));
            body.appendChild(buildElement("time", "match-chat-time", message.created_at));
            item.appendChild(body);
            return item;
        }

        item.className = "match-chat-item match-chat-item-user";
        const body = buildElement("div", "match-chat-user-body");
        const meta = buildElement("div", "match-chat-meta");
        meta.appendChild(buildElement("span", "match-chat-sender", message.sender_name));
        meta.appendChild(buildElement("span", "match-chat-role", message.sender_role));
        meta.appendChild(buildElement("time", "match-chat-time", message.created_at));
        body.appendChild(meta);
        body.appendChild(buildElement("p", "match-chat-content", message.content));
        item.appendChild(body);
        return item;
    };

    // Renders anything not rendered yet. Never touches the polling cursor.
    const appendMessages = (messages) => {
        let appended = false;
        (messages || []).forEach((message) => {
            const id = Number.parseInt(message.id, 10);
            if (!Number.isInteger(id) || renderedIds.has(id)) {
                return;
            }
            renderedIds.add(id);
            timeline.appendChild(renderMessage(message));
            appended = true;
        });
        if (!appended) {
            return;
        }
        if (emptyState) {
            emptyState.classList.add("d-none");
        }
        scrollToLatest();
    };

    // The wording lives on the server only; this just reveals what it sent.
    const applyReadOnly = (notice) => {
        canSend = false;
        if (readOnlyText && typeof notice === "string" && notice) {
            readOnlyText.textContent = notice;
        }
        if (readOnlyBox) {
            readOnlyBox.classList.remove("d-none");
        }
        if (input) {
            input.disabled = true;
        }
        if (sendButton) {
            sendButton.disabled = true;
        }
        if (form) {
            form.classList.add("d-none");
        }
    };

    const applySendState = (payload) => {
        if (!payload || payload.can_send !== false) {
            return;
        }
        applyReadOnly(payload.read_only_notice);
    };

    const poll = async () => {
        if (polling || sending || document.hidden) {
            return;
        }
        polling = true;
        try {
            const response = await fetch(`${messagesUrl}?after_id=${pollAfterId}`, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (!response.ok) {
                return;
            }
            const payload = await response.json();
            appendMessages(payload.messages);
            // Only a processed poll response may move the cursor forward.
            const nextCursor = Number.parseInt(payload.last_id, 10);
            if (Number.isInteger(nextCursor) && nextCursor > pollAfterId) {
                pollAfterId = nextCursor;
            }
            // Keep polling even once the room is read-only: the closing system
            // message is exactly what the reader still needs to receive.
            applySendState(payload);
        } catch (error) {
            // A failed poll is not worth interrupting the reader for; the next
            // tick tries again.
        } finally {
            polling = false;
        }
    };

    const startPolling = () => {
        if (timer === null) {
            timer = window.setInterval(poll, POLL_INTERVAL_MS);
        }
    };

    const stopPolling = () => {
        if (timer !== null) {
            window.clearInterval(timer);
            timer = null;
        }
    };

    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            stopPolling();
        } else {
            poll();
            startPolling();
        }
    });

    if (form && input && sendButton) {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (sending || !canSend) {
                return;
            }
            const content = input.value.trim();
            if (!content) {
                showError("Vui lòng nhập nội dung tin nhắn.");
                return;
            }

            sending = true;
            sendButton.disabled = true;
            clearError();

            const body = new FormData();
            body.set("content", content);
            const token = form.querySelector('input[name="csrf_token"]');
            if (token) {
                body.set("csrf_token", token.value);
            }

            try {
                const response = await fetch(sendUrl, {
                    method: "POST",
                    body,
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                });
                const payload = await response.json().catch(() => null);
                if (response.status === 201 && payload && payload.message) {
                    input.value = "";
                    // Rendered now, but the cursor stays where it was so the
                    // next poll still picks up anything sent in between.
                    appendMessages([payload.message]);
                } else if (response.status === 409) {
                    applySendState(payload);
                } else if (payload && typeof payload.message === "string") {
                    showError(payload.message);
                } else {
                    showError("Không gửi được tin nhắn.");
                }
            } catch (error) {
                showError("Không gửi được tin nhắn. Vui lòng thử lại.");
            } finally {
                sending = false;
                if (canSend) {
                    sendButton.disabled = false;
                }
            }
        });
    }

    scrollToLatest();
    startPolling();
});
