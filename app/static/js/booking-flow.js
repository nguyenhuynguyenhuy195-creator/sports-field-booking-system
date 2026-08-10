(() => {
    const form = document.querySelector(".booking-flow-form");
    if (!form) return;

    const panels = [...form.querySelectorAll("[data-booking-step]")];
    const indicators = [...document.querySelectorAll("[data-step-indicator]")];
    const errorBoxes = [...form.querySelectorAll("[data-flow-error]")];
    const submitButton = form.querySelector("[data-booking-submit]");
    const moneyFormatter = new Intl.NumberFormat("vi-VN", {
        style: "currency",
        currency: "VND",
        maximumFractionDigits: 0,
    });
    let currentStep = 2;
    let latestQuote = null;

    form.classList.add("is-enhanced");
    syncPlayerSplitFields();
    setStep(currentStep);

    form.querySelectorAll("[data-next-step]").forEach((button) => {
        button.addEventListener("click", async () => {
            clearErrors();
            button.disabled = true;
            try {
                latestQuote = await requestQuote();
                renderReview(latestQuote);
                setStep(Number(button.dataset.nextStep));
            } catch (error) {
                showError(error.message || "Không thể kiểm tra booking lúc này.");
            } finally {
                button.disabled = false;
            }
        });
    });

    form.querySelectorAll("[data-previous-step]").forEach((button) => {
        button.addEventListener("click", () => {
            clearErrors();
            setStep(Number(button.dataset.previousStep));
        });
    });

    form.addEventListener("change", (event) => {
        if (event.target.matches("input, select, textarea")) {
            latestQuote = null;
            if (event.target.name === "payment_mode") syncPlayerSplitFields();
            const summaryTotal = document.querySelector("[data-summary-total]");
            if (summaryTotal) summaryTotal.textContent = "Cần kiểm tra lại giá";
        }
    });

    form.addEventListener("submit", (event) => {
        if (!latestQuote && form.classList.contains("is-enhanced")) {
            event.preventDefault();
            showError("Vui lòng kiểm tra lại giờ và giá trước khi giữ chỗ.");
            return;
        }
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.value = "Đang giữ chỗ...";
        }
    });

    function setStep(step) {
        currentStep = step;
        panels.forEach((panel) => {
            const isActive = Number(panel.dataset.bookingStep) === step;
            panel.classList.toggle("is-active", isActive);
            panel.hidden = !isActive;
        });
        indicators.forEach((indicator) => {
            const indicatorStep = Number(indicator.dataset.stepIndicator);
            indicator.classList.toggle("is-active", indicatorStep === step);
            indicator.classList.toggle("is-complete", indicatorStep < step);
            const badge = indicator.querySelector("span");
            if (badge) badge.textContent = indicatorStep < step ? "✓" : String(indicatorStep);
        });
        document.querySelector(".booking-stepper")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
    }

    async function requestQuote() {
        const response = await fetch(form.dataset.quoteUrl, {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        let payload;
        try {
            payload = await response.json();
        } catch (_) {
            throw new Error("Phiên làm việc đã hết hạn. Vui lòng tải lại trang.");
        }
        if (!response.ok || !payload.ok) {
            throw new Error(payload.message || "Khoảng giờ này chưa thể đặt.");
        }
        return payload;
    }

    function renderReview(quote) {
        const bookingDate = form.elements.booking_date.value;
        const start = `${form.elements.start_hour.value}:${form.elements.start_minute.value}`;
        const end = `${form.elements.end_hour.value}:${form.elements.end_minute.value}`;
        const selectedMode = form.querySelector("input[name='payment_mode']:checked");
        const selectedModeLabel = selectedMode
            ?.closest("label")
            ?.querySelector("strong")
            ?.textContent?.trim() || "—";

        setText("[data-review-date]", formatDate(bookingDate));
        setText("[data-review-time]", `${start}–${end}`);
        setText("[data-review-mode]", selectedModeLabel);
        setText("[data-review-total]", moneyFormatter.format(Number(quote.total)));
        setText("[data-summary-total]", moneyFormatter.format(Number(quote.total)));
        setText(
            "[data-review-creator-amount]",
            moneyFormatter.format(Number(quote.contribution_plan.creator_amount)),
        );
        setText(
            "[data-review-external-amount]",
            moneyFormatter.format(Number(quote.contribution_plan.external_amount)),
        );
        setText(
            "[data-review-contribution-note]",
            contributionNote(quote.contribution_plan),
        );

        const body = form.querySelector("[data-review-segments]");
        if (!body) return;
        body.replaceChildren();
        quote.segments.forEach((segment) => {
            const row = document.createElement("tr");
            const interval = document.createElement("td");
            const duration = document.createElement("td");
            const subtotal = document.createElement("td");
            interval.textContent = `${segment.start_time}–${segment.end_time}`;
            duration.textContent = `${segment.duration_minutes} phút`;
            subtotal.textContent = moneyFormatter.format(Number(segment.subtotal));
            subtotal.className = "text-end fw-semibold";
            row.append(interval, duration, subtotal);
            body.append(row);
        });
    }

    function syncPlayerSplitFields() {
        const wrapper = form.querySelector("[data-player-split-fields]");
        const input = form.elements.required_players;
        if (!wrapper || !input) return;
        const isPlayerSplit = form.querySelector(
            "input[name='payment_mode']:checked",
        )?.value === "SPLIT_PLAYERS";
        wrapper.hidden = !isPlayerSplit;
        input.required = isPlayerSplit;
        input.disabled = !isPlayerSplit;
        if (!isPlayerSplit) input.value = "";
    }

    function contributionNote(plan) {
        if (Number(plan.external_amount) === 0) {
            return "Bạn thanh toán toàn bộ tiền sân trong một lần.";
        }
        if (plan.total_players) {
            return `Nhóm hiện có ${plan.existing_players}/${plan.total_players} người; `
                + `${plan.required_players} người ghép thanh toán từng phần riêng.`;
        }
        return "Đội bạn trả phần đầu tiên; đội đối thủ thanh toán phần còn lại.";
    }

    function setText(selector, value) {
        const element = document.querySelector(selector);
        if (element) element.textContent = value;
    }

    function formatDate(value) {
        if (!value) return "—";
        const [year, month, day] = value.split("-").map(Number);
        return new Intl.DateTimeFormat("vi-VN", {
            weekday: "long",
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
        }).format(new Date(year, month - 1, day));
    }

    function showError(message) {
        const activePanel = panels.find((panel) => Number(panel.dataset.bookingStep) === currentStep);
        const box = activePanel?.querySelector("[data-flow-error]") || errorBoxes[0];
        if (!box) return;
        box.textContent = message;
        box.classList.remove("d-none");
        box.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function clearErrors() {
        errorBoxes.forEach((box) => {
            box.textContent = "";
            box.classList.add("d-none");
        });
    }
})();
