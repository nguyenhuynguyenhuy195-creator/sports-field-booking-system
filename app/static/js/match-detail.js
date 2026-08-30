document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-match-join-form]").forEach((form) => {
        const consent = form.querySelector('input[name="share_contact"]');
        const error = form.querySelector("[data-consent-error]");

        if (!consent || !error) {
            return;
        }

        const clearError = () => {
            consent.classList.remove("is-invalid");
            error.classList.remove("d-block");
            consent.removeAttribute("aria-invalid");
        };

        consent.addEventListener("change", () => {
            if (consent.checked) {
                clearError();
            }
        });

        form.addEventListener("submit", (event) => {
            if (consent.checked) {
                clearError();
                return;
            }

            event.preventDefault();
            consent.classList.add("is-invalid");
            error.classList.add("d-block");
            consent.setAttribute("aria-invalid", "true");
            consent.focus();
        });
    });
});
