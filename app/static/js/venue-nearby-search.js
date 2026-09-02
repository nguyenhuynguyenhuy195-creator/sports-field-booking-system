(function () {
    "use strict";

    const form = document.getElementById("venue-search-form");
    const locationButton = document.getElementById("use-current-location");
    const statusElement = document.getElementById("location-search-status");
    const latitudeInput = document.getElementById("latitude");
    const longitudeInput = document.getElementById("longitude");
    const sortInput = document.getElementById("sort");
    if (
        !form
        || !locationButton
        || !statusElement
        || !latitudeInput
        || !longitudeInput
        || !sortInput
    ) {
        return;
    }

    locationButton.addEventListener("click", () => {
        if (!navigator.geolocation) {
            showError(
                "Trình duyệt của bạn không hỗ trợ xác định vị trí. Bạn vẫn có thể tìm sân bằng các bộ lọc thông thường."
            );
            return;
        }

        setLoading(true);
        statusElement.classList.remove("is-error");
        statusElement.textContent = "Đang xác định vị trí hiện tại…";
        navigator.geolocation.getCurrentPosition(
            useCurrentPosition,
            handleLocationError,
            {
                enableHighAccuracy: false,
                maximumAge: 300000,
                timeout: 10000,
            }
        );
    });

    function useCurrentPosition(position) {
        const latitude = Number(position.coords.latitude);
        const longitude = Number(position.coords.longitude);
        if (
            !Number.isFinite(latitude)
            || !Number.isFinite(longitude)
            || latitude < -90
            || latitude > 90
            || longitude < -180
            || longitude > 180
        ) {
            showError(
                "Vị trí trình duyệt trả về không hợp lệ. Vui lòng thử lại hoặc dùng các bộ lọc thông thường."
            );
            return;
        }

        latitudeInput.value = latitude.toFixed(6);
        longitudeInput.value = longitude.toFixed(6);
        sortInput.value = "nearest";
        statusElement.textContent = "Đã lấy vị trí. Đang tìm các sân gần bạn…";
        setLoading(false);
        if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
        } else {
            form.submit();
        }
    }

    function handleLocationError(error) {
        const messages = {
            1: "Bạn đã từ chối quyền truy cập vị trí. Hãy cấp quyền trong trình duyệt rồi thử lại, hoặc tiếp tục dùng các bộ lọc thông thường.",
            2: "Không thể xác định vị trí hiện tại. Vui lòng kiểm tra dịch vụ vị trí trên thiết bị rồi thử lại.",
            3: "Hết thời gian chờ vị trí. Vui lòng thử lại hoặc tiếp tục dùng các bộ lọc thông thường.",
        };
        showError(
            messages[error.code]
            || "Không thể lấy vị trí hiện tại. Bạn vẫn có thể tìm sân bằng các bộ lọc thông thường."
        );
    }

    function showError(message) {
        setLoading(false);
        statusElement.classList.add("is-error");
        statusElement.textContent = message;
    }

    function setLoading(isLoading) {
        locationButton.disabled = isLoading;
        locationButton.setAttribute("aria-busy", String(isLoading));
    }
})();
