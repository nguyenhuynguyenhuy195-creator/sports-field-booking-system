(function () {
    "use strict";

    const mapElement = document.getElementById("venue-public-map");
    const unavailableMessage = document.getElementById("venue-public-map-unavailable");
    if (!mapElement) {
        return;
    }

    const latitude = Number(mapElement.dataset.latitude);
    const longitude = Number(mapElement.dataset.longitude);
    if (typeof window.L === "undefined" || !Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        showFallback();
        return;
    }

    try {
        const location = window.L.latLng(latitude, longitude);
        const map = window.L.map(mapElement, {
            keyboard: true,
            scrollWheelZoom: false,
        }).setView(location, 16);
        window.L.tileLayer(mapElement.dataset.tileUrl, {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);

        const popup = document.createElement("div");
        const name = document.createElement("strong");
        const address = document.createElement("div");
        name.textContent = mapElement.dataset.venueName;
        address.textContent = mapElement.dataset.venueAddress;
        popup.append(name, address);
        window.L.marker(location).addTo(map).bindPopup(popup).openPopup();
    } catch (_error) {
        showFallback();
    }

    function showFallback() {
        mapElement.hidden = true;
        if (unavailableMessage) {
            unavailableMessage.hidden = false;
        }
    }
})();
