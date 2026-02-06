// Live Tracking JavaScript for Trip Admin
let map;
let marker;
let ws;
let currentTripId;
let updateInterval;

// Initialize Google Map
function initMap(latitude, longitude) {
  const initialLocation = {
    lat: parseFloat(latitude) || -17.8252,
    lng: parseFloat(longitude) || 31.0335,
  }; // Default to Zimbabwe

  if (!map) {
    map = new google.maps.Map(document.getElementById("live-map"), {
      zoom: 15,
      center: initialLocation,
      mapTypeId: google.maps.MapTypeId.ROADMAP,
    });
  }

  // Remove old marker if exists
  if (marker) {
    marker.setMap(null);
  }

  // Add marker for current location
  marker = new google.maps.Marker({
    position: initialLocation,
    map: map,
    title: "Driver Location",
    icon: "http://maps.google.com/mapfiles/ms/icons/blue-dot.png",
  });

  map.setCenter(initialLocation);
}

// Initialize Live Tracking
function initLiveTracking(tripId) {
  currentTripId = tripId;
  const container = document.getElementById("trip-map-container");

  if (!container) {
    console.error("Map container not found");
    alert("Map container not found. Please refresh the page.");
    return;
  }

  // Show the map container
  container.style.display = "block";

  // Fetch initial location from the API
  fetchInitialLocation(tripId);

  // Poll for updates every 5 seconds instead of relying on WebSocket
  if (updateInterval) {
    clearInterval(updateInterval);
  }
  updateInterval = setInterval(() => {
    fetchInitialLocation(tripId);
  }, 5000);
}

// Fetch initial location via REST API
function fetchInitialLocation(tripId) {
  const apiUrl = `/api/v1/trips/${tripId}/live-location/`;

  fetch(apiUrl)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      if (data.status === "success") {
        const lat = data.lat || data.latitude;
        const lng = data.lng || data.longitude;

        if (lat && lng) {
          updateMarkerLocation(lat, lng);
          // Update the info display
          updateLocationInfo(data);
        } else {
          console.warn("No latitude/longitude in response");
        }
      } else {
        console.warn("API returned error:", data.message);
      }
    })
    .catch((error) => {
      console.error("Error fetching location:", error);
      // Initialize with default location on first load error
      if (!map) {
        initMap(-17.8252, 31.0335);
      }
    });
}

// Update location info display
function updateLocationInfo(data) {
  let infoDiv = document.getElementById("location-info");
  if (!infoDiv) {
    infoDiv = document.createElement("div");
    infoDiv.id = "location-info";
    infoDiv.style.cssText =
      "padding:10px; background:#e8f4f8; border-radius:4px; margin-bottom:10px; font-size:12px;";
    const mapDiv = document.getElementById("live-map");
    if (mapDiv && mapDiv.parentNode) {
      mapDiv.parentNode.insertBefore(infoDiv, mapDiv);
    }
  }

  infoDiv.innerHTML = `
        <strong>Driver:</strong> ${data.username || "Unknown"} | 
        <strong>Last Updated:</strong> ${data.updated_at || "N/A"}
    `;
}

// Update marker location on the map
function updateMarkerLocation(lat, lng) {
  const newLocation = { lat: parseFloat(lat), lng: parseFloat(lng) };

  if (!map) {
    initMap(lat, lng);
  } else {
    if (marker) {
      marker.setPosition(newLocation);
    } else {
      marker = new google.maps.Marker({
        position: newLocation,
        map: map,
        title: "Driver Location",
        icon: "http://maps.google.com/mapfiles/ms/icons/blue-dot.png",
      });
    }
    map.setCenter(newLocation);
  }
}

// Stop live tracking
function stopLiveTracking() {
  if (updateInterval) {
    clearInterval(updateInterval);
  }

  if (ws) {
    ws.close();
  }

  const container = document.getElementById("trip-map-container");
  if (container) {
    container.style.display = "none";
  }

  // Reset map and marker
  map = null;
  marker = null;
}
