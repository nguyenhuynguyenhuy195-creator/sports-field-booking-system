(function () {
    "use strict";

    let mapsReady = false;

    window.initAdminVenueMap = function () {
        mapsReady = Boolean(window.google?.maps);
        renderSelectedVenueMap();
    };

    function renderSelectedVenueMap() {
        if (!mapsReady) {
            return;
        }

        const selectedPanel = document.querySelector(
            ".admin-venue-detail.show.active"
        );
        const selectedSlot = selectedPanel?.querySelector(
            "[data-admin-venue-map-slot]"
        );
        const mapElement = document.getElementById("admin-venue-selected-map");
        if (!mapElement) {
            return;
        }
        if (!selectedSlot) {
            mapElement.hidden = true;
            mapElement.replaceChildren();
            return;
        }

        selectedSlot.append(mapElement);
        mapElement.hidden = false;
        mapElement.replaceChildren();
        const latitude = Number.parseFloat(selectedSlot.dataset.latitude || "");
        const longitude = Number.parseFloat(selectedSlot.dataset.longitude || "");
        if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
            return;
        }

        const position = { lat: latitude, lng: longitude };
        const map = new google.maps.Map(mapElement, {
            center: position,
            zoom: 16,
            mapTypeControl: false,
            streetViewControl: false,
        });
        new google.maps.Marker({
            map,
            position,
            title: selectedSlot.dataset.venueName || "Cơ sở thể thao",
        });
    }

    function setUpVenueSelection() {
        document.addEventListener("shown.bs.tab", (event) => {
            if (!(event.target instanceof HTMLElement)) {
                return;
            }
            if (!event.target.matches("[data-admin-venue-tab]")) {
                return;
            }
            renderSelectedVenueMap();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setUpVenueSelection, {
            once: true,
        });
    } else {
        setUpVenueSelection();
    }
})();
