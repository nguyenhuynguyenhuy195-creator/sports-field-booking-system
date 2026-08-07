(() => {
    const countdown = document.querySelector("[data-booking-countdown]");
    if (!countdown) return;

    const deadline = new Date(countdown.dataset.deadline).getTime();
    if (Number.isNaN(deadline)) return;

    const render = () => {
        const remainingSeconds = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
        const minutes = Math.floor(remainingSeconds / 60);
        const seconds = remainingSeconds % 60;
        if (remainingSeconds === 0) {
            countdown.textContent = "Thời gian giữ chỗ đã hết. Hãy tải lại trang để cập nhật trạng thái.";
            countdown.classList.add("is-expired");
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
