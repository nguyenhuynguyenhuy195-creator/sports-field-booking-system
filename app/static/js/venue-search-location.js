(function () {
    "use strict";

    const button = document.getElementById("use-current-location");
    const form = document.getElementById("venue-search-form");
    if (!form) {
        return;
    }

    setupDependentFieldTypes();

    if (!button) {
        return;
    }

    const latitudeInput = document.getElementById("latitude");
    const longitudeInput = document.getElementById("longitude");
    const radiusInput = document.getElementById("radius_km");
    const statusElement = document.getElementById("location-search-status");

    button.addEventListener("click", () => {
        if (!navigator.geolocation) {
            showError("Trình duyệt này không hỗ trợ lấy vị trí. Bạn vẫn có thể tìm theo khu vực.");
            return;
        }
        button.disabled = true;
        statusElement.textContent = "Đang lấy vị trí hiện tại…";
        navigator.geolocation.getCurrentPosition(
            (position) => {
                latitudeInput.value = position.coords.latitude.toFixed(6);
                longitudeInput.value = position.coords.longitude.toFixed(6);
                if (!radiusInput.value) {
                    radiusInput.value = "5";
                }
                statusElement.textContent = "Đã lấy vị trí. Đang tìm các sân gần bạn…";
                form.submit();
            },
            (error) => {
                button.disabled = false;
                const message = error.code === error.PERMISSION_DENIED
                    ? "Bạn chưa cho phép truy cập vị trí. Tìm kiếm theo tên/khu vực vẫn hoạt động."
                    : "Không thể lấy vị trí lúc này. Hãy thử lại hoặc tìm theo khu vực.";
                showError(message);
            },
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
        );
    });

    function showError(message) {
        statusElement.textContent = message;
        statusElement.classList.add("text-danger");
    }

    function setupDependentFieldTypes() {
        const sportInput = document.getElementById("sport");
        const fieldTypeInput = document.getElementById("field_type");
        const fieldTypeOptionsElement = document.getElementById("field-type-filter-options");
        const helpElement = document.getElementById("field-type-filter-help");
        if (!sportInput || !fieldTypeInput || !fieldTypeOptionsElement) {
            return;
        }

        const fieldTypeOptions = Array.from(fieldTypeInput.options);
        fieldTypeInput.classList.add("d-none");
        fieldTypeOptionsElement.classList.remove("d-none");

        const submitFilters = () => {
            if (typeof form.requestSubmit === "function") {
                form.requestSubmit();
            } else {
                form.submit();
            }
        };

        const syncFieldTypes = () => {
            const selectedSport = sportInput.value;
            const selectedSportLabel = sportInput.selectedOptions[0]?.textContent?.trim();
            fieldTypeOptions.forEach((option) => {
                const belongsToSelectedSport = (
                    !option.value
                    || !selectedSport
                    || option.dataset.sport === selectedSport
                );
                option.hidden = !belongsToSelectedSport;
                option.disabled = !belongsToSelectedSport;
            });

            if (fieldTypeInput.selectedOptions[0]?.disabled) {
                fieldTypeInput.value = "";
            }

            fieldTypeOptionsElement.replaceChildren();
            fieldTypeOptions
                .filter((option) => option.value && !option.disabled)
                .forEach((option) => {
                    const optionButton = document.createElement("button");
                    const isSelected = option.value === fieldTypeInput.value;
                    const optionLabel = option.value && selectedSport
                        ? option.textContent.split("—").pop().trim()
                        : option.textContent.trim();
                    optionButton.type = "button";
                    optionButton.className = `venue-field-type-option${isSelected ? " is-selected" : ""}`;
                    optionButton.textContent = optionLabel;
                    optionButton.dataset.value = option.value;
                    optionButton.setAttribute("aria-pressed", String(isSelected));
                    optionButton.addEventListener("click", () => {
                        fieldTypeInput.value = isSelected ? "" : option.value;
                        submitFilters();
                    });
                    fieldTypeOptionsElement.appendChild(optionButton);
                });

            if (helpElement) {
                helpElement.textContent = selectedSport
                    ? `Các loại sân thuộc ${selectedSportLabel}. Bấm lại loại đang chọn để bỏ lọc chi tiết.`
                    : "Chọn bộ môn để chỉ hiển thị những loại sân tương ứng.";
            }
        };

        sportInput.addEventListener("change", () => {
            syncFieldTypes();
            submitFilters();
        });
        syncFieldTypes();
    }
})();
