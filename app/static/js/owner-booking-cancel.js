(() => {
    document.addEventListener("DOMContentLoaded", () => {
        const modalElement = document.querySelector("[data-owner-booking-cancel-modal]");
        if (!modalElement || typeof bootstrap === "undefined") {
            return;
        }

        const form = modalElement.querySelector("[data-owner-booking-cancel-form]");
        const reason = form?.querySelector("textarea[name$='reason']");
        const error = modalElement.querySelector("[data-owner-booking-cancel-error]");
        const submitButton = modalElement.querySelector("[data-owner-booking-cancel-submit]");
        if (!form || !reason || !error || !submitButton) {
            return;
        }

        const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        let hasServerError = modalElement.dataset.hasServerError === "true";

        const clearError = () => {
            reason.classList.remove("is-invalid");
            error.textContent = "";
            error.classList.remove("d-block");
        };

        const showError = (message) => {
            reason.classList.add("is-invalid");
            error.textContent = message;
            error.classList.add("d-block");
            reason.focus();
        };

        modalElement.addEventListener("show.bs.modal", () => {
            if (!hasServerError) {
                clearError();
            }
            hasServerError = false;
        });

        form.addEventListener("submit", (event) => {
            if (!reason.value.trim()) {
                event.preventDefault();
                showError("Vui lòng nhập lý do hủy.");
                return;
            }

            submitButton.disabled = true;
            submitButton.textContent = "Đang hủy...";
        });

        if (modalElement.dataset.open === "true") {
            modal.show();
        }
    });
})();
