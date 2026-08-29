(function () {
    "use strict";

    const form = document.getElementById("venue-search-form");
    const sportInput = document.getElementById("sport");
    const fieldTypeInput = document.getElementById("field_type");
    const fieldTypeOptionsElement = document.getElementById(
        "field-type-filter-options"
    );
    const helpElement = document.getElementById("field-type-filter-help");
    if (!form || !sportInput || !fieldTypeInput || !fieldTypeOptionsElement) {
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
})();
