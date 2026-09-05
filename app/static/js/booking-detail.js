(() => {
    const countdown = document.querySelector("[data-booking-countdown]");
    document.querySelectorAll("[data-payment-submit]").forEach((button) => {
        button.closest("form")?.addEventListener("submit", () => {
            button.disabled = true;
            button.textContent = "Đang xử lý...";
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
