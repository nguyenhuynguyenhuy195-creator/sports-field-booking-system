document.addEventListener("DOMContentLoaded", () => {
    const modalElement = document.getElementById("confirmActionModal");
    if (!modalElement || typeof bootstrap === "undefined") {
        return;
    }

    const titleElement = modalElement.querySelector("#confirmActionModalLabel");
    const messageElement = modalElement.querySelector("[data-confirm-modal-message]");
    const confirmButton = modalElement.querySelector("[data-confirm-modal-submit]");
    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
    let pendingForm = null;
    let opener = null;
    let restoreOpenerFocus = false;

    document.addEventListener("submit", (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) {
            return;
        }
        const message = form.dataset.confirmMessage;
        if (!message || form.dataset.confirmed === "true") {
            return;
        }

        event.preventDefault();
        pendingForm = form;
        opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        restoreOpenerFocus = true;
        titleElement.textContent = form.dataset.confirmTitle || "Xác nhận thao tác";
        messageElement.textContent = message;
        confirmButton.textContent = form.dataset.confirmButton || "Xác nhận";
        modal.show();
    });

    confirmButton.addEventListener("click", () => {
        if (!pendingForm) {
            return;
        }
        pendingForm.dataset.confirmed = "true";
        restoreOpenerFocus = false;
        modal.hide();
        pendingForm.requestSubmit();
    });

    modalElement.addEventListener("hidden.bs.modal", () => {
        const focusTarget = restoreOpenerFocus ? opener : null;
        pendingForm = null;
        opener = null;
        restoreOpenerFocus = false;
        if (focusTarget?.isConnected && focusTarget.checkVisibility()) {
            window.requestAnimationFrame(() => focusTarget.focus());
        }
    });
});
