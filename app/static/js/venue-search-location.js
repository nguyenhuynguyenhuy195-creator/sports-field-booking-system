(function () {
    "use strict";

    const button = document.getElementById("use-current-location");
    const form = document.getElementById("venue-search-form");
    if (!button || !form) {
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
})();
