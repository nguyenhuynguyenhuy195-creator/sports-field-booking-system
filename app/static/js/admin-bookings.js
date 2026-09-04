(function () {
    "use strict";

    const root = document.querySelector("[data-admin-dependent-location]");
    const provinceSelect = root?.querySelector("#province_code");
    const wardSelect = root?.querySelector("#ward_code");
    const venueSelect = root?.querySelector("[data-admin-venue-filter]");
    const fieldSelect = root?.querySelector("[data-admin-field-filter]");
    if (!root || !provinceSelect || !wardSelect || !venueSelect || !fieldSelect) {
        return;
    }

    provinceSelect.addEventListener("change", function () {
        venueSelect.value = "";
        fieldSelect.value = "";
        filterVenues();
        filterFields();
    });
    wardSelect.addEventListener("change", function () {
        venueSelect.value = "";
        fieldSelect.value = "";
        filterVenues();
        filterFields();
    });
    venueSelect.addEventListener("change", function () {
        fieldSelect.value = "";
        filterFields();
    });

    filterVenues(true);
    filterFields(true);

    function filterVenues(preserveSelection) {
        const provinceCode = provinceSelect.value;
        const provinceName = provinceSelect.selectedOptions[0]?.dataset.provinceName || "";
        const wardCode = wardSelect.value;
        const wardName = wardSelect.selectedOptions[0]?.textContent.trim() || "";
        const selectedValue = preserveSelection ? venueSelect.value : "";

        for (const option of venueSelect.options) {
            if (!option.value) {
                option.hidden = false;
                option.disabled = false;
                continue;
            }
            const provinceMatches = !provinceCode
                || option.dataset.provinceCode === provinceCode
                || (!option.dataset.provinceCode && option.dataset.provinceName === provinceName);
            const wardMatches = !wardCode
                || option.dataset.wardCode === wardCode
                || (!option.dataset.wardCode && option.dataset.wardName === wardName);
            const visible = provinceMatches && wardMatches;
            option.hidden = !visible;
            option.disabled = !visible;
        }
        if (selectedValue && venueSelect.querySelector(`option[value="${selectedValue}"]:not(:disabled)`)) {
            venueSelect.value = selectedValue;
        } else if (!preserveSelection) {
            venueSelect.value = "";
        }
    }

    function filterFields(preserveSelection) {
        const venueId = venueSelect.value;
        const selectedValue = preserveSelection ? fieldSelect.value : "";
        for (const option of fieldSelect.options) {
            if (!option.value) {
                option.hidden = false;
                option.disabled = false;
                continue;
            }
            const visible = Boolean(venueId) && option.dataset.venueId === venueId;
            option.hidden = !visible;
            option.disabled = !visible;
        }
        fieldSelect.disabled = !venueId;
        if (selectedValue && fieldSelect.querySelector(`option[value="${selectedValue}"]:not(:disabled)`)) {
            fieldSelect.value = selectedValue;
        } else if (!preserveSelection) {
            fieldSelect.value = "";
        }
    }
})();
