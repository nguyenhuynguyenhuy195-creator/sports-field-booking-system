(function () {
    "use strict";

    const form = document.getElementById("venue-search-form");
    const sportInput = document.getElementById("sport");
    const fieldTypeInput = document.getElementById("field_type");
    const fieldTypeOptionsElement = document.getElementById(
        "field-type-filter-options"
    );
    if (!form || !sportInput || !fieldTypeInput || !fieldTypeOptionsElement) {
        return;
    }

    const fieldTypeOptions = Array.from(fieldTypeInput.options);

    const submitFilters = () => {
        if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
        } else {
            form.submit();
        }
    };

    const syncFieldTypes = () => {
        const selectedSport = sportInput.value;
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

        const showSportSpecificOptions = Boolean(selectedSport);
        fieldTypeInput.classList.toggle("d-none", showSportSpecificOptions);
        fieldTypeOptionsElement.classList.toggle("d-none", !showSportSpecificOptions);
        fieldTypeOptionsElement.replaceChildren();
        if (showSportSpecificOptions) {
            fieldTypeOptions
                .filter((option) => option.value && !option.disabled)
                .forEach((option) => {
                    const optionButton = document.createElement("button");
                    const isSelected = option.value === fieldTypeInput.value;
                    const optionLabel = option.textContent.split("—").pop().trim();
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
        }

    };

    sportInput.addEventListener("change", () => {
        syncFieldTypes();
        submitFilters();
    });
    fieldTypeInput.addEventListener("change", submitFilters);
    syncFieldTypes();
})();
