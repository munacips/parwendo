// Live Tracking JavaScript for Trip Admin - WebSocket Implementation
let map;
let marker;
let ws;
let currentTripId;
let updateInterval;
let isWebSocketConnected = false;

// Initialize Google Map
function initMap(latitude, longitude) {
    const initialLocation = {
        lat: parseFloat(latitude) || -17.8252,
        lng: parseFloat(longitude) || 31.0335
    };

    if (!map) {
        map = new google.maps.Map(document.getElementById("live-map"), {
            zoom: 16,
            center: initialLocation,
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            fullscreenControl: true,
            zoomControl: true,
            mapTypeControl: true,
            streetViewControl: true
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
        animation: google.maps.Animation.DROP
    });

    map.setCenter(initialLocation);
}

// Update status indicator
function updateConnectionStatus(connected) {
    const statusElement = document.getElementById("connection-status");
    if (statusElement) {
        if (connected) {
            statusElement.textContent = "🟢 Connected";
            statusElement.style.background = "#28a745";
        } else {
            statusElement.textContent = "🟡 Polling";
            statusElement.style.background = "#ffc107";
        }
    }
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

    // Try to establish WebSocket connection first (real-time)
    connectWebSocket(tripId);

    // Fallback: Poll for updates every 5 seconds if WebSocket fails
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    updateInterval = setInterval(() => {
        if (!isWebSocketConnected) {
            fetchInitialLocation(tripId);
        }
    }, 5000);

    updateConnectionStatus(false); // Start with polling status
}

// Fetch initial location via REST API
function fetchInitialLocation(tripId) {
    const apiUrl = `/api/v1/trips/${tripId}/live-location/`;

    fetch(apiUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                const lat = data.lat || data.latitude;
                const lng = data.lng || data.longitude;

                if (lat && lng) {
                    updateMarkerLocation(lat, lng);
                    updateLocationInfo(data);
                } else {
                    console.warn("No latitude/longitude in response");
                    updateTrackingInfo("Location data unavailable");
                }
            } else {
                console.warn("API returned error:", data.message);
                updateTrackingInfo("Error: " + data.message);
            }
        })
        .catch(error => {
            console.error("Error fetching location:", error);
            if (!map) {
                initMap(-17.8252, 31.0335);
            }
            updateTrackingInfo("Connection error: " + error.message);
        });
}

// Connect to WebSocket for real-time updates
function connectWebSocket(tripId) {
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/location/`;

        ws = new WebSocket(wsUrl);

        ws.onopen = function () {
            console.log("✅ WebSocket connection established");
            isWebSocketConnected = true;
            updateConnectionStatus(true);
            updateTrackingInfo("Connected via WebSocket - Real-time updates");

            // Send trip ID to subscribe to this trip's location updates
            ws.send(JSON.stringify({
                type: 'subscribe',
                trip_id: tripId
            }));
        };

        ws.onmessage = function (event) {
            try {
                const data = JSON.parse(event.data);

                // Handle different message types
                if (data.type === 'location_update') {
                    console.log("📍 Location update received via WebSocket");
                    updateMarkerLocation(data.latitude, data.longitude);
                    updateLocationInfo({
                        username: data.user,
                        lat: data.latitude,
                        lng: data.longitude,
                        updated_at: new Date().toLocaleTimeString()
                    });
                }
            } catch (error) {
                console.error("Error parsing WebSocket message:", error);
            }
        };

        ws.onerror = function (error) {
            console.error("⚠️ WebSocket error:", error);
            isWebSocketConnected = false;
            updateConnectionStatus(false);
            updateTrackingInfo("WebSocket error - Falling back to polling");
        };

        ws.onclose = function () {
            console.log("🔴 WebSocket connection closed");
            isWebSocketConnected = false;
            updateConnectionStatus(false);
            updateTrackingInfo("WebSocket disconnected - Using polling");
        };
    } catch (error) {
        console.error("Error establishing WebSocket:", error);
        isWebSocketConnected = false;
        updateConnectionStatus(false);
    }
}

// Update location info display
function updateLocationInfo(data) {
    let infoDiv = document.getElementById("location-info");
    if (!infoDiv) {
        infoDiv = document.getElementById("tracking-info-display");
    }

    if (infoDiv) {
        infoDiv.innerHTML = `
            <strong>Driver:</strong> ${data.username || 'Unknown'} | 
            <strong>Lat:</strong> ${parseFloat(data.lat).toFixed(6)} | 
            <strong>Lng:</strong> ${parseFloat(data.lng).toFixed(6)} | 
            <strong>Last Updated:</strong> ${data.updated_at || 'N/A'}
        `;
    }
}

// Update tracking info messages
function updateTrackingInfo(message) {
    const infoDiv = document.getElementById("tracking-info-display");
    if (infoDiv) {
        infoDiv.innerHTML = `<strong>Status:</strong> ${message}`;
    }
}

// Update marker location on the map
function updateMarkerLocation(lat, lng) {
    const newLocation = { lat: parseFloat(lat), lng: parseFloat(lng) };

    if (!map) {
        initMap(lat, lng);
    } else {
        if (marker) {
            // Animate marker movement
            marker.setPosition(newLocation);
        } else {
            marker = new google.maps.Marker({
                position: newLocation,
                map: map,
                title: "Driver Location",
                icon: "http://maps.google.com/mapfiles/ms/icons/blue-dot.png",
                animation: google.maps.Animation.DROP
            });
        }
        map.setCenter(newLocation);
    }
}

// Stop live tracking
function stopLiveTracking() {
    // Clear polling interval
    if (updateInterval) {
        clearInterval(updateInterval);
    }

    // Close WebSocket connection
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        ws.close();
    }

    const container = document.getElementById("trip-map-container");
    if (container) {
        container.style.display = "none";
    }

    // Reset variables
    map = null;
    marker = null;
    currentTripId = null;
    isWebSocketConnected = false;
    updateConnectionStatus(false);

    console.log("Live tracking stopped");
}
