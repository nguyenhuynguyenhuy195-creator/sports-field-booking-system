(function () {
    "use strict";

    const mapElement = document.getElementById("venue-search-map");
    const unavailableMessage = document.getElementById(
        "venue-search-map-unavailable"
    );
    if (!mapElement) {
        return;
    }

    let venues;
    try {
        venues = JSON.parse(mapElement.dataset.venues || "[]");
    } catch (_error) {
        showFallback();
        return;
    }

    const mappedVenues = venues.filter((venue) => {
        const latitude = Number(venue.latitude);
        const longitude = Number(venue.longitude);
        return (
            Number.isFinite(latitude)
            && Number.isFinite(longitude)
            && latitude >= -90
            && latitude <= 90
            && longitude >= -180
            && longitude <= 180
            && (latitude !== 0 || longitude !== 0)
        );
    });

    if (typeof window.L === "undefined" || !mappedVenues.length) {
        showFallback();
        return;
    }

    try {
        const map = window.L.map(mapElement, {
            keyboard: true,
            scrollWheelZoom: false,
        });
        window.L.tileLayer(mapElement.dataset.tileUrl, {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);

        const bounds = window.L.latLngBounds([]);
        const userLocation = parseUserLocation();
        if (userLocation) {
            bounds.extend(userLocation);
            window.L.circleMarker(userLocation, {
                color: "#0b5ed7",
                fillColor: "#4dabf7",
                fillOpacity: 0.95,
                radius: 8,
                weight: 3,
            }).addTo(map).bindPopup(buildUserPopup());
        }
        mappedVenues.forEach((venue) => {
            const location = window.L.latLng(
                Number(venue.latitude),
                Number(venue.longitude)
            );
            bounds.extend(location);
            window.L.marker(location).addTo(map).bindPopup(buildPopup(venue));
        });

        if (mappedVenues.length === 1 && !userLocation) {
            map.setView(bounds.getCenter(), 15);
        } else {
            map.fitBounds(bounds, { padding: [32, 32], maxZoom: 15 });
        }
    } catch (_error) {
        showFallback();
    }

    function buildPopup(venue) {
        const popup = document.createElement("div");
        const name = document.createElement("strong");
        const address = document.createElement("div");
        const detailLink = document.createElement("a");
        const distance = document.createElement("div");
        name.textContent = venue.name;
        address.textContent = venue.address;
        detailLink.href = venue.detail_url;
        detailLink.textContent = "Xem chi tiết";
        popup.append(name, address);
        if (venue.distance_label) {
            distance.textContent = `Cách bạn ${venue.distance_label}`;
            distance.className = "venue-map-popup-distance";
            popup.append(distance);
        }
        popup.append(detailLink);
        return popup;
    }

    function parseUserLocation() {
        if (!mapElement.dataset.userLocation) {
            return null;
        }
        try {
            const location = JSON.parse(mapElement.dataset.userLocation);
            const latitude = Number(location.latitude);
            const longitude = Number(location.longitude);
            if (
                Number.isFinite(latitude)
                && Number.isFinite(longitude)
                && latitude >= -90
                && latitude <= 90
                && longitude >= -180
                && longitude <= 180
            ) {
                return window.L.latLng(latitude, longitude);
            }
        } catch (_error) {
            return null;
        }
        return null;
    }

    function buildUserPopup() {
        const popup = document.createElement("div");
        const label = document.createElement("strong");
        label.textContent = "Vị trí hiện tại của bạn";
        popup.append(label);
        return popup;
    }

    function showFallback() {
        mapElement.hidden = true;
        if (unavailableMessage) {
            unavailableMessage.hidden = false;
        }
    }
})();
