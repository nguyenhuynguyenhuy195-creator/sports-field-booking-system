// Chatbot widget: talks to POST /chatbot/query and renders the reply.
//
// Two rules run through this file.
//
// 1. Nothing from the server or the user is ever written as markup. Every
//    dynamic string goes through textContent, so an answer, a source label or
//    an error message cannot become HTML. There is no Markdown renderer:
//    line breaks are preserved with white-space: pre-wrap in CSS instead.
//
// 2. History lives in sessionStorage only, keyed by user AND page AND
//    resource, so one account's conversation can never be replayed to another
//    and a booking's history is never sent from a venue page. It is cleared
//    when the tab notices a different account.
document.addEventListener("DOMContentLoaded", () => {
    const widget = document.querySelector("[data-chatbot-widget]");
    if (!widget) {
        return;
    }

    const launcher = widget.querySelector("[data-chatbot-launcher]");
    const panel = widget.querySelector("[data-chatbot-panel]");
    const closeButton = widget.querySelector("[data-chatbot-close]");
    const clearButton = widget.querySelector("[data-chatbot-clear]");
    const scroller = widget.querySelector("[data-chatbot-scroll]");
    const intro = widget.querySelector("[data-chatbot-intro]");
    const thread = widget.querySelector("[data-chatbot-thread]");
    const status = widget.querySelector("[data-chatbot-status]");
    const form = widget.querySelector("[data-chatbot-form]");
    const input = widget.querySelector("[data-chatbot-input]");
    const sendButton = widget.querySelector("[data-chatbot-send]");

    const queryUrl = widget.dataset.chatbotQueryUrl;
    const csrfToken = widget.dataset.chatbotCsrf;
    const userId = widget.dataset.chatbotUser || "anon";
    const pageType = widget.dataset.chatbotPageType || "general";
    const resourceId = widget.dataset.chatbotResourceId || "general";

    const STORAGE_PREFIX = "chatbot:v1:";
    const STORAGE_KEY = `${STORAGE_PREFIX}${userId}:${pageType}:${resourceId}`;
    const OWNER_KEY = "chatbot:v1:owner";
    // The API accepts 8 turns; keeping the same ceiling here means the browser
    // never sends something the server would only truncate.
    const MAX_MESSAGES = 16;
    const MAX_SOURCES = 3;

    const ERRORS = {
        400: "Yêu cầu không hợp lệ. Vui lòng tải lại trang và thử lại.",
        401: "Phiên đăng nhập đã hết. Vui lòng đăng nhập lại.",
        403: "Tài khoản này không sử dụng được trợ lý.",
        413: "Câu hỏi quá dài. Vui lòng rút gọn lại.",
        415: "Yêu cầu không hợp lệ. Vui lòng tải lại trang và thử lại.",
        422: "Câu hỏi không hợp lệ. Vui lòng thử lại.",
        429: "Bạn đang hỏi quá nhanh. Vui lòng thử lại sau.",
        503: "Trợ lý đang tạm thời không phản hồi. Vui lòng thử lại sau.",
    };
    const GENERIC_ERROR = "Không gửi được câu hỏi. Vui lòng thử lại.";

    let history = [];
    let pending = false;

    // --- storage ---------------------------------------------------------
    // Every read and write is guarded: sessionStorage throws in a private
    // window and may be disabled outright. The widget must still work.

    function safeSession(action, fallback) {
        try {
            return action();
        } catch (error) {
            return fallback;
        }
    }

    function removeChatbotKeys(keepOwnerMarker) {
        // Only ever touches the chatbot's own prefix, so nothing else stored
        // by the site can be collateral damage.
        safeSession(() => {
            const doomed = [];
            for (let index = 0; index < window.sessionStorage.length; index += 1) {
                const key = window.sessionStorage.key(index);
                if (!key || !key.startsWith(STORAGE_PREFIX)) {
                    continue;
                }
                if (keepOwnerMarker && key === OWNER_KEY) {
                    continue;
                }
                doomed.push(key);
            }
            doomed.forEach((key) => window.sessionStorage.removeItem(key));
        }, null);
    }

    function dropOtherAccounts() {
        // A second account signing in to the same tab must not inherit the
        // first one's conversations.
        const previousOwner = safeSession(
            () => window.sessionStorage.getItem(OWNER_KEY), null);
        if (previousOwner === userId) {
            return;
        }
        removeChatbotKeys(true);
        safeSession(
            () => window.sessionStorage.setItem(OWNER_KEY, userId), null);
    }

    function loadHistory() {
        const raw = safeSession(
            () => window.sessionStorage.getItem(STORAGE_KEY), null);
        if (!raw) {
            return [];
        }
        let parsed;
        try {
            parsed = JSON.parse(raw);
        } catch (error) {
            return [];
        }
        if (!Array.isArray(parsed)) {
            return [];
        }
        return parsed
            .filter((item) => item
                && (item.role === "user" || item.role === "assistant")
                && typeof item.content === "string")
            .map((item) => ({ role: item.role, content: item.content }))
            .slice(-MAX_MESSAGES);
    }

    function saveHistory() {
        history = history.slice(-MAX_MESSAGES);
        safeSession(
            () => window.sessionStorage.setItem(
                STORAGE_KEY, JSON.stringify(history)),
            null,
        );
    }

    function clearHistory() {
        history = [];
        safeSession(() => window.sessionStorage.removeItem(STORAGE_KEY), null);
    }

    // --- rendering -------------------------------------------------------

    function scrollToEnd() {
        if (scroller) {
            scroller.scrollTop = scroller.scrollHeight;
        }
    }

    function renderMessage(role, content, options) {
        const settings = options || {};
        const item = document.createElement("li");
        item.className = `chatbot-message chatbot-message-${role}`;
        if (settings.error) {
            item.classList.add("chatbot-message-error");
        }

        const bubble = document.createElement("div");
        bubble.className = "chatbot-bubble";
        // textContent, never innerHTML: model output and user input alike.
        bubble.textContent = content;
        item.appendChild(bubble);

        const sources = dedupeSources(settings.sources || []);
        if (sources.length) {
            item.appendChild(renderSources(sources));
        }
        thread.appendChild(item);
        scrollToEnd();
        return item;
    }

    function dedupeSources(sources) {
        const seen = new Set();
        const unique = [];
        sources.forEach((source) => {
            if (!source || typeof source.label !== "string") {
                return;
            }
            // Deduplicated by slug for display only; the backend decides what
            // actually grounded the answer.
            const key = typeof source.source === "string" ? source.source : source.label;
            if (seen.has(key)) {
                return;
            }
            seen.add(key);
            unique.push(source);
        });
        return unique.slice(0, MAX_SOURCES);
    }

    function renderSources(sources) {
        const details = document.createElement("details");
        details.className = "chatbot-sources";
        const summary = document.createElement("summary");
        summary.textContent = `Xem nguồn (${sources.length})`;
        details.appendChild(summary);

        const list = document.createElement("ul");
        list.className = "chatbot-source-list";
        sources.forEach((source) => {
            const entry = document.createElement("li");
            // The human label only. The slug is an internal identifier.
            entry.textContent = source.label;
            list.appendChild(entry);
        });
        details.appendChild(list);
        return details;
    }

    function renderHistory() {
        thread.replaceChildren();
        history.forEach((item) => renderMessage(item.role, item.content));
        syncIntro();
    }

    function syncIntro() {
        // Driven by the thread, not by history.length: a question that is
        // still in flight is on screen but deliberately not yet persisted.
        if (intro) {
            intro.hidden = thread.children.length > 0;
        }
    }

    function setStatus(text) {
        status.textContent = text || "";
    }

    // --- sending ---------------------------------------------------------

    function setPending(active) {
        pending = active;
        sendButton.disabled = active;
        input.disabled = active;
        // Clearing mid-flight would let the reply land in a conversation the
        // user just emptied. Disabling it is the whole race fix; no request
        // cancellation machinery is needed.
        clearButton.disabled = active;
    }

    async function ask(question) {
        const trimmed = question.trim();
        if (!trimmed || pending) {
            return;
        }

        // Persisted history is not touched until the answer arrives. The
        // bubble below is shown immediately for feedback, but a question that
        // fails must not survive into the next request as context.
        const priorHistory = history.slice(-MAX_MESSAGES);

        renderMessage("user", trimmed);
        syncIntro();

        setPending(true);
        setStatus("Đang tìm thông tin...");

        const body = {
            question: trimmed,
            // Only turns that previously succeeded.
            history: priorHistory,
            context: {
                page_type: pageType,
                resource_id: resourceId === "general"
                    ? null
                    : Number.parseInt(resourceId, 10),
            },
        };

        let response;
        let payload = null;
        try {
            response = await fetch(queryUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify(body),
            });
            payload = await response.json().catch(() => null);
        } catch (error) {
            setPending(false);
            setStatus("");
            renderMessage("assistant", GENERIC_ERROR, { error: true });
            return;
        }

        setPending(false);
        setStatus("");

        if (!response.ok || !payload || payload.ok !== true) {
            // A failed turn is shown but never remembered: it must not become
            // context for the next question.
            const message = ERRORS[response.status] || GENERIC_ERROR;
            renderMessage("assistant", message, { error: true });
            return;
        }

        renderMessage("assistant", payload.answer, { sources: payload.sources });
        // The pair is appended together, only now. That is what makes an
        // assistant-only history impossible: there is no window in which the
        // question is stored without its answer.
        history.push({ role: "user", content: trimmed });
        history.push({ role: "assistant", content: payload.answer });
        saveHistory();
        input.focus();
    }

    // --- panel -----------------------------------------------------------

    function openPanel() {
        panel.hidden = false;
        launcher.setAttribute("aria-expanded", "true");
        input.focus();
        scrollToEnd();
    }

    function closePanel() {
        panel.hidden = true;
        launcher.setAttribute("aria-expanded", "false");
        launcher.focus();
    }

    launcher.addEventListener("click", () => {
        if (panel.hidden) {
            openPanel();
        } else {
            closePanel();
        }
    });

    closeButton.addEventListener("click", closePanel);

    clearButton.addEventListener("click", () => {
        // Local only: no request, no database, nothing on the server.
        clearHistory();
        renderHistory();
        setStatus("");
        input.focus();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !panel.hidden) {
            closePanel();
        }
    });

    widget.querySelectorAll("[data-chatbot-chip]").forEach((chip) => {
        chip.addEventListener("click", () => {
            ask(chip.textContent.trim());
        });
    });

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const question = input.value;
        input.value = "";
        autoGrow();
        ask(question);
    });

    function autoGrow() {
        input.style.height = "auto";
        input.style.height = `${Math.min(input.scrollHeight, 96)}px`;
    }

    input.addEventListener("input", autoGrow);

    input.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" || event.shiftKey) {
            return;
        }
        // Enter while an IME candidate window is open is confirming a
        // Vietnamese/CJK composition, not sending a message.
        if (event.isComposing || event.keyCode === 229) {
            return;
        }
        event.preventDefault();
        form.requestSubmit();
    });

    const logoutForm = document.querySelector("[data-logout-form]");
    if (logoutForm) {
        // Synchronous removal in the submit handler: it finishes before the
        // browser navigates, and preventDefault is never called, so the
        // logout POST itself is untouched.
        logoutForm.addEventListener("submit", () => {
            removeChatbotKeys(false);
        });
    }

    dropOtherAccounts();
    history = loadHistory();
    renderHistory();
});
