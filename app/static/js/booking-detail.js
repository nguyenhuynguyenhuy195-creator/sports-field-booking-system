(() => {
    const countdown = document.querySelector("[data-booking-countdown]");

    // Fix 3: Chrome/Safari can restore this page from BFCache when the user
    // presses Back from VNPAY. Only a button THIS script disabled for an
    // in-flight submit gets re-enabled — a button disabled for another
    // reason (e.g. the countdown expiring below) must stay disabled.
    document.querySelectorAll("[data-payment-submit]").forEach((button) => {
        const originalLabel = button.textContent;
        button.closest("form")?.addEventListener("submit", () => {
            button.dataset.originalLabel = originalLabel;
            button.dataset.paymentSubmitting = "true";
            button.disabled = true;
            button.textContent = "Đang xử lý...";
        });
    });

    window.addEventListener("pageshow", (event) => {
        if (!event.persisted) return;
        document
            .querySelectorAll('[data-payment-submit][data-payment-submitting="true"]')
            .forEach((button) => {
                button.disabled = false;
                if (button.dataset.originalLabel) {
                    button.textContent = button.dataset.originalLabel;
                }
                delete button.dataset.paymentSubmitting;
            });
    });

    if (!countdown) return;

    const initialPaymentWindow = countdown.hasAttribute("data-initial-payment-countdown");
    const refreshButton = document.querySelector("[data-booking-payment-refresh]");
    refreshButton?.addEventListener("click", () => window.location.reload());

    const deadline = new Date(countdown.dataset.deadline).getTime();
    if (Number.isNaN(deadline)) return;

    const render = () => {
        const remainingSeconds = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
        const minutes = Math.floor(remainingSeconds / 60);
        const seconds = remainingSeconds % 60;
        if (remainingSeconds === 0) {
            countdown.textContent = initialPaymentWindow
                ? "Thời gian thanh toán giữ chỗ đã hết. Tải lại trang để xem trạng thái mới nhất."
                : "Thời gian giữ chỗ đã hết. Hãy tải lại trang để cập nhật trạng thái.";
            countdown.classList.add("is-expired");
            if (initialPaymentWindow) {
                countdown.closest(".booking-action-card")?.querySelectorAll("[data-payment-submit]").forEach((button) => {
                    button.disabled = true;
                });
                if (refreshButton) refreshButton.hidden = false;
            }
            return false;
        }
        countdown.textContent = `Còn ${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")} để thanh toán`;
        return true;
    };

    if (!render()) return;
    const timer = window.setInterval(() => {
        if (!render()) window.clearInterval(timer);
    }, 1000);
})();

// Fix 2: after a verified VNPAY Return finds the Payment still PENDING, the
// page renders a watch marker (see [data-vnpay-payment-watch] in
// bookings/detail.html and matches/detail.html). Poll the read-only status
// endpoint briefly and reload once IPN has applied a terminal status, so the
// user is not stuck looking at a stale "PENDING" page until they hit F5.
// IPN remains the only path that can ever change the Payment's status.
(() => {
    const watcher = document.querySelector("[data-vnpay-payment-watch]");
    if (!watcher) return;
    const statusUrl = watcher.dataset.statusUrl;
    if (!statusUrl) return;

    const POLL_INTERVAL_MS = 1000;
    const MAX_ATTEMPTS = 15;
    const MAX_CONSECUTIVE_FAILURES = 3;

    let attempts = 0;
    let consecutiveFailures = 0;
    let stopped = false;
    let timer = null;

    const stop = () => {
        stopped = true;
        if (timer !== null) window.clearInterval(timer);
    };

    const tick = async () => {
        if (stopped) return;
        attempts += 1;
        try {
            const response = await fetch(statusUrl, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (!response.ok) throw new Error(`status ${response.status}`);
            const payload = await response.json();
            consecutiveFailures = 0;
            if (payload.status && payload.status !== "PENDING") {
                stop();
                window.location.reload();
                return;
            }
        } catch (_) {
            consecutiveFailures += 1;
            if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
                stop();
                return;
            }
        }
        if (attempts >= MAX_ATTEMPTS) {
            stop();
        }
    };

    timer = window.setInterval(tick, POLL_INTERVAL_MS);
    tick();
})();
