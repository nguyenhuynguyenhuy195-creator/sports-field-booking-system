(function () {
    "use strict";

    const mapElement = document.getElementById("venue-location-map");
    const form = mapElement ? mapElement.closest("form") : null;
    const latitudeInput = document.getElementById("latitude");
    const longitudeInput = document.getElementById("longitude");
    const confirmedInput = document.getElementById("location_confirmed");
    const addressInput = document.getElementById("address");
    const provinceInput = document.getElementById("province_code");
    const wardInput = document.getElementById("ward_code");
    const searchButton = document.getElementById("venue-location-search");
    const confirmButton = document.getElementById("venue-location-confirm");
    const stateElement = document.getElementById("venue-location-state");
    const statusElement = document.getElementById("venue-location-status");
    const coordinatesElement = document.getElementById("venue-location-coordinates");
    if (!mapElement || !form || !latitudeInput || !longitudeInput ||
        !confirmedInput || !addressInput || !provinceInput || !wardInput ||
        !searchButton || !confirmButton || !stateElement || !statusElement ||
        !coordinatesElement) {
        return;
    }

    if (typeof window.L === "undefined") {
        statusElement.textContent = "Không tải được bản đồ. Vui lòng tải lại trang trước khi lưu vị trí.";
        statusElement.classList.add("is-error");
        return;
    }

    const originalIdentity = [
        mapElement.dataset.originalAddress.trim(),
        mapElement.dataset.originalProvince,
        mapElement.dataset.originalWard,
    ];
    const isNewVenue = mapElement.dataset.isNew === "1";
    const submittedWasConfirmed = confirmedInput.value === "1";
    const map = window.L.map(mapElement, { scrollWheelZoom: false }).setView([16.0, 106.0], 5);
    window.L.tileLayer(mapElement.dataset.tileUrl, {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    let marker = null;
    const initialLatitude = parseCoordinate(latitudeInput.value, -90, 90);
    const initialLongitude = parseCoordinate(longitudeInput.value, -180, 180);
    const originalLatitude = parseCoordinate(mapElement.dataset.originalLatitude, -90, 90);
    const originalLongitude = parseCoordinate(mapElement.dataset.originalLongitude, -180, 180);
    let locationDirty = identityChanged() || (
        initialLatitude !== null && initialLongitude !== null &&
        (initialLatitude !== originalLatitude || initialLongitude !== originalLongitude)
    );
    if (initialLatitude !== null && initialLongitude !== null) {
        setMarker(initialLatitude, initialLongitude, { zoom: 16, markDirty: locationDirty });
        confirmedInput.value = submittedWasConfirmed ? "1" : "0";
    }
    setLocationState(
        !locationDirty && (submittedWasConfirmed || mapElement.dataset.existingCoordinates === "1")
            ? "confirmed"
            : "unconfirmed"
    );

    addressInput.addEventListener("input", invalidateIfIdentityChanged);
    provinceInput.addEventListener("change", invalidateIfIdentityChanged);
    wardInput.addEventListener("change", invalidateIfIdentityChanged);
    searchButton.addEventListener("click", searchLocation);
    confirmButton.addEventListener("click", confirmMarker);
    map.on("click", function (event) {
        setMarker(event.latlng.lat, event.latlng.lng, { zoom: null, markDirty: true });
        setLocationState("unconfirmed");
        setStatus("Ghim đã được đặt thủ công. Hãy kiểm tra và bấm “Xác nhận ghim”.", "warning");
    });
    form.addEventListener("submit", validateBeforeSubmit);

    function currentIdentity() {
        return [addressInput.value.trim(), provinceInput.value, wardInput.value];
    }

    function identityChanged() {
        const current = currentIdentity();
        return current.some(function (value, index) { return value !== originalIdentity[index]; });
    }

    function invalidateIfIdentityChanged() {
        if (!identityChanged()) {
            return;
        }
        clearMarkerAndCoordinates(true);
        setLocationState("unconfirmed");
        setStatus("Địa chỉ đã thay đổi. Tọa độ cũ không còn được tin cậy; hãy tìm hoặc đặt và xác nhận lại ghim.", "warning");
    }

    async function searchLocation() {
        if (!addressInput.value.trim() || !provinceInput.value || !wardInput.value) {
            setStatus("Vui lòng nhập đủ địa chỉ, tỉnh/thành phố và phường/xã trước khi tìm.", "error");
            return;
        }
        const csrfInput = form.querySelector('input[name="csrf_token"]');
        const body = new URLSearchParams({
            address: addressInput.value.trim(),
            province_code: provinceInput.value,
            ward_code: wardInput.value,
        });
        if (csrfInput) {
            body.set("csrf_token", csrfInput.value);
        }
        searchButton.disabled = true;
        searchButton.setAttribute("aria-busy", "true");
        setStatus("Đang tìm vị trí gợi ý…", "loading");
        try {
            const response = await fetch(mapElement.dataset.geocodeUrl, {
                method: "POST",
                headers: { "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
                body: body.toString(),
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.error || "Không tìm được vị trí.");
            }
            setMarker(Number(payload.latitude), Number(payload.longitude), { zoom: 17, markDirty: true });
            setLocationState("suggestion");
            setStatus("Đã tìm thấy vị trí gợi ý. Hãy kéo/bấm để sửa nếu cần, rồi xác nhận ghim.", "warning");
        } catch (error) {
            setStatus(error.message + " Bạn có thể bấm trực tiếp lên bản đồ để đặt ghim.", "error");
        } finally {
            searchButton.disabled = false;
            searchButton.removeAttribute("aria-busy");
        }
    }

    function setMarker(latitude, longitude, options) {
        if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
            return;
        }
        const latlng = window.L.latLng(latitude, longitude);
        if (!marker) {
            marker = window.L.marker(latlng, { draggable: true }).addTo(map);
            marker.on("dragend", function () {
                const position = marker.getLatLng();
                updateCoordinates(position.lat, position.lng, true);
                setLocationState("unconfirmed");
                setStatus("Ghim đã được di chuyển. Hãy kiểm tra và xác nhận lại.", "warning");
            });
        } else {
            marker.setLatLng(latlng);
        }
        updateCoordinates(latitude, longitude, options.markDirty);
        if (options.zoom) {
            map.setView(latlng, options.zoom);
        }
    }

    function updateCoordinates(latitude, longitude, markDirty) {
        latitudeInput.value = latitude.toFixed(6);
        longitudeInput.value = longitude.toFixed(6);
        confirmedInput.value = "0";
        if (markDirty) {
            locationDirty = true;
        }
        confirmButton.disabled = false;
        coordinatesElement.textContent = latitudeInput.value + ", " + longitudeInput.value;
    }

    function clearMarkerAndCoordinates(markDirty) {
        if (marker) {
            map.removeLayer(marker);
            marker = null;
        }
        latitudeInput.value = "";
        longitudeInput.value = "";
        confirmedInput.value = "0";
        if (markDirty) {
            locationDirty = true;
        }
        confirmButton.disabled = true;
        coordinatesElement.textContent = "";
    }

    function confirmMarker() {
        if (!marker) {
            setStatus("Hãy đặt ghim trên bản đồ trước khi xác nhận.", "error");
            return;
        }
        const position = marker.getLatLng();
        updateCoordinates(position.lat, position.lng, true);
        confirmedInput.value = "1";
        setLocationState("confirmed");
        setStatus("Đã xác nhận ghim. Tọa độ này sẽ được gửi khi bạn lưu cơ sở.", "success");
    }

    function validateBeforeSubmit(event) {
        const hasCoordinates = Boolean(latitudeInput.value && longitudeInput.value);
        const requiresCoordinates = isNewVenue || locationDirty;
        if ((requiresCoordinates && !hasCoordinates) ||
            (locationDirty && confirmedInput.value !== "1") ||
            (isNewVenue && confirmedInput.value !== "1")) {
            event.preventDefault();
            setStatus("Vui lòng đặt và xác nhận ghim vị trí trước khi lưu.", "error");
            mapElement.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }

    function parseCoordinate(value, minimum, maximum) {
        if (!value) {
            return null;
        }
        const number = Number(value);
        return Number.isFinite(number) && number >= minimum && number <= maximum ? number : null;
    }

    function setStatus(message, state) {
        statusElement.textContent = message;
        statusElement.classList.remove("is-error", "is-warning", "is-success", "is-loading");
        statusElement.classList.add("is-" + state);
    }

    function setLocationState(state) {
        const states = {
            unconfirmed: {
                label: "Chưa xác nhận vị trí",
                icon: "bi-exclamation-circle",
            },
            suggestion: {
                label: "Vị trí gợi ý — hãy kiểm tra và xác nhận",
                icon: "bi-pin-map",
            },
            confirmed: {
                label: "Đã xác nhận vị trí",
                icon: "bi-check-circle-fill",
            },
        };
        const current = states[state];
        stateElement.className = "owner-location-state is-" + state;
        stateElement.innerHTML = '<i class="bi ' + current.icon + '" aria-hidden="true"></i><span>' + current.label + "</span>";
        confirmButton.classList.toggle("is-confirmed", state === "confirmed");
        confirmButton.disabled = state === "confirmed" || !marker;
        confirmButton.innerHTML = state === "confirmed"
            ? '<i class="bi bi-check-circle-fill" aria-hidden="true"></i>Đã xác nhận'
            : '<i class="bi bi-check2-circle" aria-hidden="true"></i>Xác nhận ghim';
    }
})();
