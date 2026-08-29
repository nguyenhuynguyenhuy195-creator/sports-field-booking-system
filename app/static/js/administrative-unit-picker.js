(function () {
    "use strict";

    const provinceSelect = document.getElementById("province_code");
    const wardSelect = document.getElementById("ward_code");
    const statusElement = document.getElementById("administrative-unit-status");
    if (!provinceSelect || !wardSelect || !statusElement) {
        return;
    }

    const wardsUrl = provinceSelect.dataset.wardsUrl;
    if (!wardsUrl) {
        return;
    }

    setWardAvailability();
    provinceSelect.addEventListener("change", loadWards);

    async function loadWards() {
        const provinceCode = provinceSelect.value;
        replaceWardOptions("Đang tải danh sách...", true);
        if (!provinceCode) {
            replaceWardOptions("Chọn phường, xã", true);
            statusElement.textContent = "";
            return;
        }

        wardSelect.setAttribute("aria-busy", "true");
        try {
            const response = await fetch(
                `${wardsUrl}?province_code=${encodeURIComponent(provinceCode)}`,
                { headers: { Accept: "application/json" } }
            );
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.error || "Không thể tải danh sách phường/xã.");
            }

            replaceWardOptions("Chọn phường, xã", false);
            for (const ward of payload.wards) {
                wardSelect.add(new Option(ward.name, ward.code));
            }
            statusElement.textContent = "";
        } catch (error) {
            replaceWardOptions("Không tải được danh sách", true);
            statusElement.textContent = error.message;
        } finally {
            wardSelect.removeAttribute("aria-busy");
        }
    }

    function replaceWardOptions(label, disabled) {
        wardSelect.replaceChildren(new Option(label, ""));
        wardSelect.disabled = disabled;
        wardSelect.value = "";
    }

    function setWardAvailability() {
        const hasProvince = Boolean(provinceSelect.value);
        const hasWardOptions = wardSelect.options.length > 1;
        wardSelect.disabled = !hasProvince || !hasWardOptions;
    }
})();
