(function () {
    "use strict";

    const DEFAULT_CENTER = { lat: 10.7769, lng: 106.7009 };

    window.initVenueLocationPicker = async function () {
        const autocompleteHost = document.getElementById("venue-place-autocomplete");
        const mapElement = document.getElementById("venue-location-map");
        if (!autocompleteHost || !mapElement || !window.google?.maps) {
            return;
        }

        const addressInput = document.getElementById("address");
        const districtInput = document.getElementById("district");
        const cityInput = document.getElementById("city");
        const placeIdInput = document.getElementById("google_place_id");
        const latitudeInput = document.getElementById("latitude");
        const longitudeInput = document.getElementById("longitude");
        const statusElement = document.getElementById("venue-location-status");

        const initialLatitude = Number.parseFloat(mapElement.dataset.latitude);
        const initialLongitude = Number.parseFloat(mapElement.dataset.longitude);
        const hasInitialLocation = Number.isFinite(initialLatitude) && Number.isFinite(initialLongitude);
        const initialCenter = hasInitialLocation
            ? { lat: initialLatitude, lng: initialLongitude }
            : DEFAULT_CENTER;

        const { Map } = await google.maps.importLibrary("maps");
        const { PlaceAutocompleteElement } = await google.maps.importLibrary("places");
        const map = new Map(mapElement, {
            center: initialCenter,
            zoom: hasInitialLocation ? 16 : 12,
            mapTypeControl: false,
            streetViewControl: false,
        });
        let marker = hasInitialLocation
            ? new google.maps.Marker({ map, position: initialCenter })
            : null;

        const autocomplete = new PlaceAutocompleteElement({});
        autocomplete.placeholder = "Nhập tên đường hoặc cơ sở thể thao";
        autocomplete.includedRegionCodes = ["vn"];
        autocompleteHost.appendChild(autocomplete);

        const handleSelection = async (event) => {
            const prediction = event.placePrediction;
            const place = prediction?.toPlace ? prediction.toPlace() : event.place;
            if (!place) {
                return;
            }
            await place.fetchFields({
                fields: ["id", "formattedAddress", "location", "addressComponents"],
            });
            if (!place.id || !place.location) {
                setStatus("Google chưa trả đủ tọa độ. Hãy chọn một gợi ý khác.", true);
                clearLocation();
                return;
            }

            const position = {
                lat: place.location.lat(),
                lng: place.location.lng(),
            };
            placeIdInput.value = place.id;
            latitudeInput.value = position.lat.toFixed(6);
            longitudeInput.value = position.lng.toFixed(6);
            if (place.formattedAddress) {
                addressInput.value = place.formattedAddress;
            }
            fillAdministrativeArea(place.addressComponents || [], districtInput, cityInput);

            if (marker) {
                marker.setPosition(position);
            } else {
                marker = new google.maps.Marker({ map, position });
            }
            map.setCenter(position);
            map.setZoom(17);
            setStatus("Đã xác nhận vị trí Google và ghim trên bản đồ.", false);
        };

        autocomplete.addEventListener("gmp-select", handleSelection);
        autocomplete.addEventListener("gmp-placeselect", handleSelection);

        addressInput.addEventListener("input", () => {
            if (placeIdInput.value) {
                clearLocation();
                setStatus("Địa chỉ đã thay đổi. Hãy chọn lại gợi ý Google để xác nhận vị trí.", true);
            }
        });

        function clearLocation() {
            placeIdInput.value = "";
            latitudeInput.value = "";
            longitudeInput.value = "";
            if (marker) {
                marker.setMap(null);
                marker = null;
            }
        }

        function setStatus(message, isWarning) {
            statusElement.textContent = message;
            statusElement.classList.toggle("text-warning", isWarning);
            statusElement.classList.toggle("text-secondary", !isWarning);
        }
    };

    function fillAdministrativeArea(components, districtInput, cityInput) {
        let district = "";
        let city = "";
        for (const component of components) {
            const types = component.types || [];
            const value = component.longText || component.long_name || "";
            if (!district && types.includes("administrative_area_level_2")) {
                district = value;
            }
            if (!city && (types.includes("administrative_area_level_1") || types.includes("locality"))) {
                city = value;
            }
        }
        if (district && !districtInput.value.trim()) {
            districtInput.value = district;
        }
        if (city) {
            cityInput.value = city;
        }
    }
})();
