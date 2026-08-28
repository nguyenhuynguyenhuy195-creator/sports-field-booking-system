(function () {
    "use strict";

    const state = {
        bounds: null,
        failureTimer: null,
        infoWindow: null,
        map: null,
        markers: new Map(),
        pendingVenueId: null,
    };

    const mapElement = document.getElementById("venue-public-map");
    const fallbackElement = document.querySelector("[data-venue-map-fallback]");
    const mapPanel = document.getElementById("venue-map-panel");

    setupCardButtons();
    setupMapPanel();
    setupLoadFallback();

    window.handleVenuePublicMapError = function () {
        showFallback("Bản đồ không tải được. Bạn vẫn có thể dùng liên kết chỉ đường.");
    };

    window.initVenuePublicMap = function () {
        if (!mapElement) {
            return;
        }
        if (!window.google?.maps) {
            showFallback("Bản đồ không tải được. Bạn vẫn có thể dùng liên kết chỉ đường.");
            return;
        }

        const items = readMarkerItems();
        if (!items.length) {
            showFallback("Chưa có vị trí hợp lệ để hiển thị trên bản đồ.");
            return;
        }

        clearFailureTimer();
        try {
            mapElement.classList.remove("d-none");
            fallbackElement?.classList.add("d-none");
            state.map = new window.google.maps.Map(mapElement, {
                center: items[0].position,
                zoom: items.length === 1 ? 16 : 12,
                mapTypeControl: false,
                streetViewControl: false,
            });
            state.bounds = new window.google.maps.LatLngBounds();
            state.infoWindow = new window.google.maps.InfoWindow();

            items.forEach(({ item, position }) => {
                const marker = new window.google.maps.Marker({
                    map: state.map,
                    position,
                    title: String(item.name || "Cơ sở thể thao"),
                });
                state.bounds.extend(position);
                state.markers.set(String(item.venue_id), { item, marker });
                marker.addListener("click", () => {
                    openMarkerInfo(item, marker);
                    highlightVenueCard(item.venue_id);
                });
            });

            if (items.length > 1) {
                state.map.fitBounds(state.bounds, 48);
            }

            if (state.pendingVenueId !== null) {
                focusVenueMarker(state.pendingVenueId);
                state.pendingVenueId = null;
            }
        } catch (_error) {
            showFallback("Bản đồ không thể khởi tạo. Bạn vẫn có thể dùng liên kết chỉ đường.");
        }
    };

    function setupLoadFallback() {
        if (!mapElement) {
            return;
        }
        if (mapElement.dataset.mapApiEnabled !== "true") {
            showFallback("Bản đồ hiện chưa khả dụng. Bạn vẫn có thể dùng liên kết chỉ đường.");
            return;
        }
        state.failureTimer = window.setTimeout(() => {
            if (!state.map) {
                showFallback("Bản đồ tải quá lâu. Bạn vẫn có thể dùng liên kết chỉ đường.");
            }
        }, 15000);
    }

    function readMarkerItems() {
        let markerData;
        try {
            markerData = JSON.parse(mapElement.dataset.markers || "[]");
        } catch (_error) {
            return [];
        }
        if (!Array.isArray(markerData)) {
            return [];
        }
        return markerData.flatMap((item) => {
            const latitude = Number(item?.latitude);
            const longitude = Number(item?.longitude);
            if (
                !Number.isFinite(latitude)
                || !Number.isFinite(longitude)
                || latitude < -90
                || latitude > 90
                || longitude < -180
                || longitude > 180
            ) {
                return [];
            }
            return [{ item, position: { lat: latitude, lng: longitude } }];
        });
    }

    function setupCardButtons() {
        document.querySelectorAll("[data-venue-map-target]").forEach((button) => {
            button.addEventListener("click", () => {
                const venueId = button.dataset.venueMapTarget;
                if (mapPanel) {
                    mapPanel.open = true;
                    mapPanel.scrollIntoView({ behavior: "smooth", block: "start" });
                } else {
                    mapElement?.scrollIntoView({ behavior: "smooth", block: "center" });
                }

                if (state.map) {
                    window.setTimeout(() => focusVenueMarker(venueId), 50);
                } else {
                    state.pendingVenueId = venueId;
                }
            });
        });
    }

    function setupMapPanel() {
        mapPanel?.addEventListener("toggle", () => {
            if (!mapPanel.open || !state.map || !window.google?.maps) {
                return;
            }
            window.requestAnimationFrame(() => {
                window.google.maps.event.trigger(state.map, "resize");
                if (state.markers.size > 1 && state.bounds) {
                    state.map.fitBounds(state.bounds, 48);
                }
            });
        });
    }

    function focusVenueMarker(venueId) {
        const markerEntry = state.markers.get(String(venueId));
        if (!markerEntry || !state.map || !window.google?.maps) {
            return;
        }
        window.google.maps.event.trigger(state.map, "resize");
        state.map.panTo(markerEntry.marker.getPosition());
        const currentZoom = state.map.getZoom();
        if (!Number.isFinite(currentZoom) || currentZoom < 15) {
            state.map.setZoom(15);
        }
        openMarkerInfo(markerEntry.item, markerEntry.marker);
        highlightVenueCard(venueId);
    }

    function openMarkerInfo(item, marker) {
        if (!state.infoWindow || !state.map) {
            return;
        }
        state.infoWindow.setContent(buildInfoContent(item));
        state.infoWindow.open({ map: state.map, anchor: marker });
    }

    function buildInfoContent(item) {
        const content = document.createElement("div");
        content.className = "venue-map-info";

        const name = document.createElement("strong");
        name.textContent = String(item.name || "Cơ sở thể thao");
        content.appendChild(name);

        const distance = Number(item.distance_km);
        if (item.distance_km !== null && Number.isFinite(distance)) {
            appendMeta(content, `Cách ${distance.toFixed(1)} km`);
        }

        const startingPrice = Number(item.starting_price);
        if (item.starting_price !== null && Number.isFinite(startingPrice)) {
            const formattedPrice = new Intl.NumberFormat("vi-VN").format(startingPrice);
            appendMeta(content, `Giá từ ${formattedPrice} đ/giờ`);
        }

        const actions = document.createElement("div");
        actions.className = "venue-map-info-actions";
        appendSafeLink(actions, item.detail_url, "Xem chi tiết", false);
        appendSafeLink(actions, item.directions_url, "Mở chỉ đường", true);
        if (actions.childElementCount) {
            content.appendChild(actions);
        }
        return content;
    }

    function appendMeta(container, text) {
        const meta = document.createElement("span");
        meta.className = "venue-map-info-meta";
        meta.textContent = text;
        container.appendChild(meta);
    }

    function appendSafeLink(container, value, label, opensNewTab) {
        const safeUrl = getSafeUrl(value);
        if (!safeUrl) {
            return;
        }
        const link = document.createElement("a");
        link.href = safeUrl;
        link.textContent = label;
        if (opensNewTab) {
            link.target = "_blank";
            link.rel = "noopener noreferrer";
        }
        container.appendChild(link);
    }

    function getSafeUrl(value) {
        if (typeof value !== "string" || !value.trim()) {
            return null;
        }
        try {
            const parsedUrl = new URL(value, window.location.origin);
            return ["http:", "https:"].includes(parsedUrl.protocol)
                ? parsedUrl.href
                : null;
        } catch (_error) {
            return null;
        }
    }

    function highlightVenueCard(venueId) {
        document.querySelectorAll("[data-venue-card]").forEach((card) => {
            card.classList.toggle(
                "is-map-focused",
                card.dataset.venueCard === String(venueId)
            );
        });
    }

    function showFallback(message) {
        clearFailureTimer();
        mapElement?.classList.add("d-none");
        if (fallbackElement) {
            fallbackElement.textContent = message;
            fallbackElement.classList.remove("d-none");
        }
    }

    function clearFailureTimer() {
        if (state.failureTimer !== null) {
            window.clearTimeout(state.failureTimer);
            state.failureTimer = null;
        }
    }
})();
