(function () {
    "use strict";

    const sortSelect = document.querySelector("[data-match-sort]");
    const sortForm = sortSelect?.form;
    if (!sortSelect || !sortForm) {
        return;
    }

    sortSelect.addEventListener("change", () => {
        if (typeof sortForm.requestSubmit === "function") {
            sortForm.requestSubmit();
        } else {
            sortForm.submit();
        }
    });
})();
