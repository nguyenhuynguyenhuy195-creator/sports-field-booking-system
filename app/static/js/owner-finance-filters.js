document.addEventListener("DOMContentLoaded", () => {
    const venueSelect = document.querySelector(
        '.owner-finance-scope select[name="venue_id"]',
    );
    const fieldSelect = document.querySelector(
        '.owner-finance-scope select[name="field_id"]',
    );
    if (!venueSelect || !fieldSelect) {
        return;
    }

    const syncFieldOptions = () => {
        const venueId = venueSelect.value;
        for (const option of fieldSelect.options) {
            if (!option.value) {
                continue;
            }
            const unavailable = Boolean(
                venueId && option.dataset.venueId !== venueId,
            );
            option.hidden = unavailable;
            option.disabled = unavailable;
        }
        if (fieldSelect.selectedOptions[0]?.disabled) {
            fieldSelect.value = "";
        }
    };

    venueSelect.addEventListener("change", syncFieldOptions);
    syncFieldOptions();
});
