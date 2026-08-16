(() => {
    const form = document.querySelector(".booking-flow-form");
    if (!form) return;

    const panels = [...form.querySelectorAll("[data-booking-step]")];
    const indicators = [...document.querySelectorAll("[data-step-indicator]")];
    const errorBoxes = [...form.querySelectorAll("[data-flow-error]")];
    const submitButton = form.querySelector("[data-booking-submit]");
    const availabilityGrid = form.querySelector("[data-availability-grid]");
    const availabilityLoading = form.querySelector("[data-availability-loading]");
    const availabilityEmpty = form.querySelector("[data-availability-empty]");
    const selectionSummary = form.querySelector("[data-selection-summary]");
    const stepTwoNext = form.querySelector("[data-next-step='3']");
    const dateInput = form.elements.booking_date;
    const moneyFormatter = new Intl.NumberFormat("vi-VN", {
        style: "currency",
        currency: "VND",
        maximumFractionDigits: 0,
    });
    const slotLabels = {
        AVAILABLE: "Còn trống",
        BOOKED: "Đã có người đặt",
        MAINTENANCE: "Đang bảo trì",
        NO_PRICE: "Chưa áp dụng giá",
        PAST: "Đã qua",
    };

    let currentStep = 2;
    let latestQuote = null;
    let availabilitySlots = [];
    let availabilityStepMinutes = 30;
    let minimumDurationMinutes = 60;
    let selectionStart = null;
    let selectionEnd = null;
    let selectionFinalized = false;
    let availabilityRequestId = 0;
    let quoteRequestId = 0;

    form.classList.add("is-enhanced");
    syncPlayerSplitFields();
    setStep(currentStep);
    initializeAvailability();

    form.querySelectorAll("[data-next-step]").forEach((button) => {
        button.addEventListener("click", async () => {
            clearErrors();
            if (Number(button.dataset.nextStep) === 3 && !hasValidSelection()) {
                showError("Vui lòng chọn giờ bắt đầu và kết thúc cách nhau ít nhất 60 phút.");
                return;
            }
            button.disabled = true;
            try {
                latestQuote = await requestQuote();
                renderReview(latestQuote);
                setStep(Number(button.dataset.nextStep));
            } catch (error) {
                showError(error.message || "Không thể kiểm tra booking lúc này.");
            } finally {
                if (button === stepTwoNext) {
                    button.disabled = !hasValidSelection();
                } else {
                    button.disabled = false;
                }
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
        if (!event.target.matches("input, select, textarea")) return;
        latestQuote = null;
        if (event.target.name === "booking_date") {
            clearErrors();
            clearSelection();
            loadAvailability();
            return;
        }
        if (event.target.name === "booking_mode") syncPlayerSplitFields();
        const summaryTotal = document.querySelector("[data-summary-total]");
        if (summaryTotal) summaryTotal.textContent = "Cần kiểm tra lại giá";
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

    form.querySelector("[data-clear-selection]")?.addEventListener("click", () => {
        clearErrors();
        clearSelection();
    });

    form.querySelector("[data-date-previous]")?.addEventListener("click", () => {
        moveSelectedDate(-1);
    });
    form.querySelector("[data-date-next]")?.addEventListener("click", () => {
        moveSelectedDate(1);
    });

    function initializeAvailability() {
        if (!availabilityGrid || !form.dataset.availabilityUrl || !dateInput) return;
        if (stepTwoNext) stepTwoNext.disabled = true;
        loadAvailability();
    }

    async function loadAvailability() {
        if (!dateInput?.value) return;
        const requestId = ++availabilityRequestId;
        setAvailabilityLoading(true);
        renderDateStrip();
        availabilityGrid.replaceChildren();
        if (availabilityEmpty) availabilityEmpty.hidden = true;

        try {
            const url = new URL(form.dataset.availabilityUrl, window.location.origin);
            url.searchParams.set("date", dateInput.value);
            const response = await fetch(url, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            let payload;
            try {
                payload = await response.json();
            } catch (_) {
                throw new Error("Phiên làm việc đã hết hạn. Vui lòng tải lại trang.");
            }
            if (!response.ok || !payload.ok) {
                throw new Error(payload.message || "Không thể tải lịch trống.");
            }
            if (requestId !== availabilityRequestId) return;

            availabilitySlots = payload.slots;
            availabilityStepMinutes = Number(payload.step_minutes);
            minimumDurationMinutes = Number(payload.minimum_duration_minutes);
            setText("[data-availability-date-label]", formatDate(payload.date));
            renderAvailabilitySlots();
        } catch (error) {
            if (requestId !== availabilityRequestId) return;
            availabilitySlots = [];
            if (availabilityEmpty) {
                availabilityEmpty.textContent = error.message || "Không thể tải lịch trống.";
                availabilityEmpty.hidden = false;
            }
            showError(error.message || "Không thể tải lịch trống.");
        } finally {
            if (requestId === availabilityRequestId) setAvailabilityLoading(false);
        }
    }

    function renderAvailabilitySlots() {
        availabilityGrid.replaceChildren();
        if (!availabilitySlots.length) {
            if (availabilityEmpty) {
                availabilityEmpty.textContent = "Sân chưa có khung 30 phút phù hợp trong ngày này.";
                availabilityEmpty.hidden = false;
            }
            return;
        }

        const timeMarkers = availabilitySlots.map((slot) => ({
            time: slot.start_time,
            status: slot.status,
        }));
        const lastSlot = availabilitySlots[availabilitySlots.length - 1];
        timeMarkers.push({time: lastSlot.end_time, status: "BOUNDARY"});

        timeMarkers.forEach((marker, index) => {
            const button = document.createElement("button");
            const timeLabel = document.createElement("strong");
            const statusLabel = document.createElement("small");
            const markerLabel = marker.status === "BOUNDARY"
                ? "Mốc kết thúc"
                : slotLabels[marker.status];
            button.type = "button";
            button.className = marker.status === "BOUNDARY"
                ? "availability-slot is-boundary"
                : `availability-slot is-${marker.status.toLowerCase().replace("_", "-")}`;
            button.dataset.slotIndex = String(index);
            button.dataset.slotLabel = markerLabel;
            button.dataset.slotStatus = marker.status;
            button.setAttribute(
                "aria-disabled",
                marker.status === "AVAILABLE" ? "false" : "true",
            );
            button.setAttribute("role", "gridcell");
            button.setAttribute("aria-pressed", "false");
            button.title = `${marker.time}: ${markerLabel}`;
            timeLabel.textContent = marker.time;
            statusLabel.textContent = markerLabel;
            statusLabel.dataset.slotStatusLabel = "";
            button.append(timeLabel, statusLabel);
            button.addEventListener("click", () => selectSlot(index));
            availabilityGrid.append(button);
        });
    }

    function selectSlot(index) {
        clearErrors();
        if (selectionStart === null || selectionFinalized) {
            if (index >= availabilitySlots.length
                || availabilitySlots[index].status !== "AVAILABLE") {
                showError("Mốc này không thể dùng làm giờ bắt đầu. Hãy chọn một ô còn trống.");
                return;
            }
            selectionStart = index;
            selectionEnd = null;
            selectionFinalized = false;
            syncSelection();
            return;
        }

        if (index <= selectionStart) {
            if (index === selectionStart) {
                clearSelection();
                return;
            }
            if (index < availabilitySlots.length
                && availabilitySlots[index].status === "AVAILABLE") {
                selectionStart = index;
                selectionEnd = null;
                selectionFinalized = false;
                syncSelection();
                return;
            }
            showError("Giờ kết thúc phải sau giờ bắt đầu.");
            return;
        }

        const selectedIntervals = availabilitySlots.slice(selectionStart, index);
        if (selectedIntervals.some((slot) => slot.status !== "AVAILABLE")) {
            showError("Khoảng đã chọn đi qua thời gian không còn trống. Hãy chọn mốc kết thúc sớm hơn.");
            return;
        }

        selectionEnd = index;
        const duration = (selectionEnd - selectionStart) * availabilityStepMinutes;
        selectionFinalized = duration >= minimumDurationMinutes;
        syncSelection();
        if (!selectionFinalized) {
            showError(`Khoảng đã chọn mới có ${duration} phút. Vui lòng chọn tối thiểu ${minimumDurationMinutes} phút.`);
        }
    }

    function syncSelection() {
        availabilityGrid.querySelectorAll("[data-slot-index]").forEach((button) => {
            const index = Number(button.dataset.slotIndex);
            let actionable = button.dataset.slotStatus === "AVAILABLE";
            if (selectionStart !== null && !selectionFinalized && index > selectionStart) {
                actionable = availabilitySlots
                    .slice(selectionStart, index)
                    .every((slot) => slot.status === "AVAILABLE");
            }
            button.setAttribute("aria-disabled", actionable ? "false" : "true");
            const selected = selectionStart !== null
                && index >= selectionStart
                && (selectionEnd === null ? index === selectionStart : index <= selectionEnd);
            button.classList.toggle("is-selected", selected);
            button.setAttribute("aria-pressed", selected ? "true" : "false");
            const statusLabel = button.querySelector("[data-slot-status-label]");
            if (statusLabel) {
                if (!selected) statusLabel.textContent = button.dataset.slotLabel;
                else if (index === selectionStart) statusLabel.textContent = "Bắt đầu";
                else if (index === selectionEnd) statusLabel.textContent = "Kết thúc";
                else statusLabel.textContent = "Đã chọn";
            }
        });

        if (selectionStart === null) {
            if (selectionSummary) selectionSummary.hidden = true;
            if (stepTwoNext) stepTwoNext.disabled = true;
            return;
        }

        const firstSlot = availabilitySlots[selectionStart];
        const endTime = selectionEnd === null
            ? firstSlot.start_time
            : selectionEnd < availabilitySlots.length
                ? availabilitySlots[selectionEnd].start_time
                : availabilitySlots[availabilitySlots.length - 1].end_time;
        const duration = selectionEnd === null
            ? 0
            : (selectionEnd - selectionStart) * availabilityStepMinutes;
        setFormTime("start", firstSlot.start_time);
        if (selectionEnd !== null) setFormTime("end", endTime);
        setText(
            "[data-selection-time]",
            selectionEnd === null ? `Bắt đầu lúc ${firstSlot.start_time}` : `${firstSlot.start_time}–${endTime}`,
        );
        setText("[data-selection-duration]", duration ? formatDuration(duration) : "Chưa chọn giờ kết thúc");
        if (selectionSummary) selectionSummary.hidden = false;

        const valid = hasValidSelection();
        if (stepTwoNext) stepTwoNext.disabled = !valid;
        if (!valid) {
            setText("[data-selection-total]", "Chọn mốc kết thúc");
            setText("[data-summary-total]", "Cần chọn tối thiểu 60 phút");
            latestQuote = null;
            return;
        }
        quoteCurrentSelection();
    }

    /*
     * The availability API returns half-hour intervals. The interface renders
     * their boundaries so a click on 18:00 followed by 19:00 means exactly
     * 18:00–19:00; the interval starting at the end boundary is not included.
     */

    async function quoteCurrentSelection() {
        const requestId = ++quoteRequestId;
        setText("[data-selection-total]", "Đang tính giá…");
        try {
            const quote = await requestQuote();
            if (requestId !== quoteRequestId) return;
            latestQuote = quote;
            renderReview(quote);
            setText("[data-selection-total]", moneyFormatter.format(Number(quote.total)));
        } catch (error) {
            if (requestId !== quoteRequestId) return;
            latestQuote = null;
            setText("[data-selection-total]", "Chưa thể báo giá");
            setText("[data-summary-total]", "Cần kiểm tra lại");
            showError(error.message || "Khoảng giờ này chưa thể đặt.");
        }
    }

    function clearSelection() {
        selectionStart = null;
        selectionEnd = null;
        selectionFinalized = false;
        latestQuote = null;
        quoteRequestId += 1;
        syncSelection();
        setText("[data-summary-total]", "Chọn giờ để xem giá");
    }

    function hasValidSelection() {
        if (!selectionFinalized || selectionStart === null || selectionEnd === null) {
            return false;
        }
        const duration = (selectionEnd - selectionStart) * availabilityStepMinutes;
        return duration >= minimumDurationMinutes;
    }

    function setFormTime(prefix, value) {
        const [hour, minute] = value.split(":");
        form.elements[`${prefix}_hour`].value = hour;
        form.elements[`${prefix}_minute`].value = minute;
    }

    function renderDateStrip() {
        const strip = form.querySelector("[data-date-strip]");
        if (!strip || !dateInput.value) return;
        strip.replaceChildren();

        const selected = parseDate(dateInput.value);
        const minimum = parseDate(form.dataset.minimumDate);
        const maximum = parseDate(form.dataset.maximumDate);
        let start = addDays(selected, -3);
        if (start < minimum) start = minimum;
        if (addDays(start, 6) > maximum) start = addDays(maximum, -6);
        if (start < minimum) start = minimum;

        for (let offset = 0; offset < 7; offset += 1) {
            const day = addDays(start, offset);
            if (day > maximum) break;
            const button = document.createElement("button");
            const weekday = document.createElement("span");
            const dateLabel = document.createElement("strong");
            const value = toIsoDate(day);
            button.type = "button";
            button.className = "availability-day-button";
            button.classList.toggle("is-active", value === dateInput.value);
            button.setAttribute("aria-pressed", value === dateInput.value ? "true" : "false");
            weekday.textContent = new Intl.DateTimeFormat("vi-VN", { weekday: "short" }).format(day);
            dateLabel.textContent = new Intl.DateTimeFormat("vi-VN", {
                day: "2-digit",
                month: "2-digit",
            }).format(day);
            button.append(weekday, dateLabel);
            button.addEventListener("click", () => setSelectedDate(value));
            strip.append(button);
        }

        const activeDay = strip.querySelector(".availability-day-button.is-active");
        if (activeDay) {
            window.requestAnimationFrame(() => {
                if (strip.scrollWidth <= strip.clientWidth) return;
                const stripRect = strip.getBoundingClientRect();
                const activeRect = activeDay.getBoundingClientRect();
                strip.scrollLeft += activeRect.left - stripRect.left
                    - (strip.clientWidth - activeRect.width) / 2;
            });
        }

        const previous = form.querySelector("[data-date-previous]");
        const next = form.querySelector("[data-date-next]");
        if (previous) previous.disabled = selected <= minimum;
        if (next) next.disabled = selected >= maximum;
    }

    function moveSelectedDate(offset) {
        if (!dateInput?.value) return;
        const selected = parseDate(dateInput.value);
        const target = addDays(selected, offset);
        const minimum = parseDate(form.dataset.minimumDate);
        const maximum = parseDate(form.dataset.maximumDate);
        if (target < minimum || target > maximum) return;
        setSelectedDate(toIsoDate(target));
    }

    function setSelectedDate(value) {
        if (dateInput.value === value) return;
        dateInput.value = value;
        dateInput.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function setAvailabilityLoading(isLoading) {
        if (availabilityLoading) {
            availabilityLoading.textContent = isLoading ? "Đang tải lịch…" : "";
        }
        if (availabilityGrid) availabilityGrid.setAttribute("aria-busy", String(isLoading));
    }

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
        const selectedMode = form.querySelector("input[name='booking_mode']:checked");
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
            "[data-review-venue-balance]",
            moneyFormatter.format(Number(quote.venue_balance)),
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
        const input = form.elements.requested_players;
        if (!wrapper || !input) return;
        const isPlayerSplit = form.querySelector(
            "input[name='booking_mode']:checked",
        )?.value === "FIND_PLAYERS";
        wrapper.hidden = !isPlayerSplit;
        input.required = isPlayerSplit;
        input.disabled = !isPlayerSplit;
        if (!isPlayerSplit) input.value = "";
    }

    function contributionNote(plan) {
        if (Number(plan.external_amount) === 0) {
            return plan.requested_players
                ? `${plan.requested_players} người ghép không cần cọc và thanh toán tại sân.`
                : "Bạn thanh toán toàn bộ khoản cọc 30%.";
        }
        return "Bạn trả 15% để giữ sân; đội nhận kèo trả 15% và tham gia ngay sau khi thanh toán. Không có đối thủ, booking vẫn còn hiệu lực.";
    }

    function setText(selector, value) {
        const element = document.querySelector(selector);
        if (element) element.textContent = value;
    }

    function formatDate(value) {
        if (!value) return "—";
        return new Intl.DateTimeFormat("vi-VN", {
            weekday: "long",
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
        }).format(parseDate(value));
    }

    function formatDuration(minutes) {
        if (minutes < 60) return `${minutes} phút`;
        const hours = Math.floor(minutes / 60);
        const remainder = minutes % 60;
        return remainder ? `${hours} giờ ${remainder} phút` : `${hours} giờ`;
    }

    function parseDate(value) {
        const [year, month, day] = value.split("-").map(Number);
        return new Date(year, month - 1, day, 12);
    }

    function toIsoDate(value) {
        const year = value.getFullYear();
        const month = String(value.getMonth() + 1).padStart(2, "0");
        const day = String(value.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function addDays(value, amount) {
        const result = new Date(value);
        result.setDate(result.getDate() + amount);
        return result;
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
