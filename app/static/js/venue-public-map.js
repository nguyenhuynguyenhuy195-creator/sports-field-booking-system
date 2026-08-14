(function () {
    "use strict";

    window.initVenuePublicMap = function () {
        const mapElement = document.getElementById("venue-public-map");
        if (!mapElement || !window.google?.maps) {
            return;
        }

        let markers;
        try {
            markers = JSON.parse(mapElement.dataset.markers || "[]");
        } catch (_error) {
            markers = [];
        }
        if (!markers.length) {
            return;
        }

        const map = new google.maps.Map(mapElement, {
            center: { lat: markers[0].latitude, lng: markers[0].longitude },
            zoom: markers.length === 1 ? 16 : 12,
            mapTypeControl: false,
            streetViewControl: false,
        });
        const bounds = new google.maps.LatLngBounds();
        const infoWindow = new google.maps.InfoWindow();

        markers.forEach((item) => {
            const position = { lat: item.latitude, lng: item.longitude };
            const marker = new google.maps.Marker({
                map,
                position,
                title: item.name,
            });
            bounds.extend(position);
            marker.addListener("click", () => {
                const safeName = escapeHtml(item.name);
                const safeUrl = encodeURI(item.detail_url);
                infoWindow.setContent(`<strong>${safeName}</strong><br><a href="${safeUrl}">Xem chi tiết</a>`);
                infoWindow.open({ map, anchor: marker });
            });
        });

        if (markers.length > 1) {
            map.fitBounds(bounds, 48);
        }
    };

    function escapeHtml(value) {
        const element = document.createElement("div");
        element.textContent = value || "";
        return element.innerHTML;
    }
})();
