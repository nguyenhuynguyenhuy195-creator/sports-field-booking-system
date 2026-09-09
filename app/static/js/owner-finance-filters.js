document.addEventListener("DOMContentLoaded", () => {
    const financeForm = document.querySelector(".owner-finance-scope");
    if (!financeForm) {
        return;
    }

    const venueSelect = financeForm.querySelector('select[name="venue_id"]');
    const fieldSelect = financeForm.querySelector('select[name="field_id"]');
    const timeRangeSelect = financeForm.querySelector("[data-finance-time-range]");
    const dateFromInput = financeForm.querySelector('input[name="date_from"]');
    const dateToInput = financeForm.querySelector('input[name="date_to"]');
    const advancedFilters = document.querySelector("#financeAdvancedFilters");

    const syncFieldOptions = () => {
        if (!venueSelect || !fieldSelect) {
            return;
        }
        const venueId = venueSelect.value;
        const defaultOption = fieldSelect.options[0];
        fieldSelect.disabled = !venueId;
        if (defaultOption) {
            defaultOption.textContent = venueId ? "Tất cả sân" : "Chọn cơ sở trước";
        }
        for (const option of fieldSelect.options) {
            if (!option.value) {
                continue;
            }
            const unavailable = Boolean(
                !venueId || option.dataset.venueId !== venueId,
            );
            option.hidden = unavailable;
            option.disabled = unavailable;
        }
        if (!venueId || fieldSelect.selectedOptions[0]?.disabled) {
            fieldSelect.value = "";
        }
    };

    const restoreVenueForSelectedField = () => {
        if (venueSelect?.value || !fieldSelect?.value) {
            return;
        }
        const selectedField = fieldSelect.selectedOptions[0];
        if (selectedField?.dataset.venueId) {
            venueSelect.value = selectedField.dataset.venueId;
        }
    };

    const formatLocalDate = (date) => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    };

    const rangeForPreset = (preset) => {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const start = new Date(today);

        if (preset === "last_7_days") {
            start.setDate(today.getDate() - 6);
        } else if (preset === "last_30_days") {
            start.setDate(today.getDate() - 29);
        } else if (preset === "this_month") {
            start.setDate(1);
        } else {
            return null;
        }

        return [formatLocalDate(start), formatLocalDate(today)];
    };

    const showAdvancedFilters = () => {
        if (!advancedFilters) {
            return;
        }
        if (window.bootstrap?.Collapse) {
            window.bootstrap.Collapse.getOrCreateInstance(advancedFilters, {
                toggle: false,
            }).show();
        } else {
            advancedFilters.classList.add("show");
        }
    };

    const detectInitialTimeRange = () => {
        if (!timeRangeSelect || !dateFromInput || !dateToInput) {
            return;
        }
        const currentRange = [dateFromInput.value, dateToInput.value];
        if (!currentRange[0] && !currentRange[1]) {
            timeRangeSelect.value = "all";
            return;
        }
        for (const preset of ["last_7_days", "last_30_days", "this_month"]) {
            const presetRange = rangeForPreset(preset);
            if (
                presetRange[0] === currentRange[0] &&
                presetRange[1] === currentRange[1]
            ) {
                timeRangeSelect.value = preset;
                return;
            }
        }
        timeRangeSelect.value = "custom";
        showAdvancedFilters();
    };

    const syncSelectedTimeRange = () => {
        if (!timeRangeSelect || !dateFromInput || !dateToInput) {
            return;
        }
        if (timeRangeSelect.value === "custom") {
            showAdvancedFilters();
            return;
        }
        const selectedRange = rangeForPreset(timeRangeSelect.value);
        dateFromInput.value = selectedRange?.[0] ?? "";
        dateToInput.value = selectedRange?.[1] ?? "";
    };

    venueSelect?.addEventListener("change", syncFieldOptions);
    timeRangeSelect?.addEventListener("change", () => {
        syncSelectedTimeRange();
        if (timeRangeSelect.value === "custom") {
            dateFromInput?.focus();
        }
    });
    financeForm.addEventListener("submit", syncSelectedTimeRange);

    restoreVenueForSelectedField();
    syncFieldOptions();
    detectInitialTimeRange();
});
