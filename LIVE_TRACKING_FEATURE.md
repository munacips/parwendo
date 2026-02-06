# Live Location Tracking Feature for Admin Panel

## Overview

This feature allows admins to view the live location of drivers on a Google Map directly from the Trip admin change form.

## How It Works

### 1. **Frontend Components**

#### a. Template (`main/templates/admin/main/trip/change_form.html`)

- Extends Django's admin change form
- Includes Google Maps API script
- Provides a "Start Live Tracking" button at the bottom of the form
- Contains a hidden map container that displays when tracking is initiated
- Includes CSS styling for the map and UI elements

#### b. JavaScript (`static/static_files/admin/main/trip/live_tracking.js`)

The JavaScript file handles:

- **`initLiveTracking(tripId)`**: Initiates the tracking process

  - Shows the map container
  - Fetches initial location from the API
  - Sets up polling interval (every 5 seconds)

- **`fetchInitialLocation(tripId)`**: Fetches location data from the REST API

  - Calls `/api/v1/trips/{trip_id}/live-location/`
  - Handles response with latitude and longitude
  - Updates the map with the new location

- **`updateMarkerLocation(lat, lng)`**: Updates the marker on the Google Map

  - Creates or repositions the marker
  - Centers the map on the driver's location

- **`updateLocationInfo(data)`**: Displays driver info and last update time

- **`stopLiveTracking()`**: Stops the tracking and hides the map
  - Clears the polling interval
  - Closes WebSocket connection (if used)
  - Resets map and marker variables

### 2. **Backend Components**

#### a. Admin Configuration (`main/admin.py`)

```python
@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    change_form_template = "admin/main/trip/change_form.html"
    list_display = ('id', 'driver', 'destination', 'status', 'view_location_button')
    readonly_fields = ('live_location_map',)

    def live_location_map(self, obj):
        # Displays trip info and instructions

    def view_location_button(self, obj):
        # Shows a quick link to view location in list view
```

#### b. REST API Endpoint (`main/views.py`)

- **URL**: `/api/v1/trips/<trip_id>/live-location/`
- **Method**: GET
- **Response Format**:

```json
{
  "status": "success",
  "username": "driver_username",
  "lat": 31.0335,
  "lng": -17.8252,
  "updated_at": "14:30:45"
}
```

#### c. Data Model

- **UserLocation**: Stores current location for each user
  - Fields: `user`, `latitude`, `longitude`, `updated_at`
  - Updated in real-time via WebSocket (consumer.py)

### 3. **Data Flow**

1. Admin clicks "Start Live Tracking" button on Trip change form
2. JavaScript fetches the API endpoint for the trip's location
3. Google Map is initialized with the driver's coordinates
4. Polling interval requests location updates every 5 seconds
5. Marker position updates on the map as location data changes
6. Admin can click "Stop Tracking" to close the map and stop polling

## File Structure

```
parwendo/
├── main/
│   ├── admin.py (TripAdmin with live_location_map method)
│   ├── templates/
│   │   └── admin/main/trip/
│   │       ├── change_form.html (updated template)
│   │       └── live_tracking.js (template version)
│   └── views.py (get_trip_live_location endpoint)
└── static/
    └── static_files/
        └── admin/main/trip/
            └── live_tracking.js (static version - used by template)
```

## Features

✅ Real-time location tracking using Google Maps
✅ Auto-refresh every 5 seconds (configurable)
✅ Driver name and last update time display
✅ Clean, user-friendly UI
✅ Stop tracking button to close map
✅ Responsive design that works on different screen sizes
✅ Error handling for missing or invalid data

## Configuration

### Google Maps API Key

The template includes the Google Maps API key. Make sure it has the following permissions:

- Maps JavaScript API
- Marker support

To update the API key, edit the script tag in `change_form.html`:

```html
<script src="https://maps.googleapis.com/maps/api/js?key=YOUR_API_KEY"></script>
```

### Polling Interval

The default polling interval is 5 seconds. To change it, modify this line in `live_tracking.js`:

```javascript
updateInterval = setInterval(() => {
  fetchInitialLocation(tripId);
}, 5000); // Change 5000 to desired milliseconds
```

## Troubleshooting

### Map doesn't load

- Check if Google Maps API key is valid
- Verify the `/api/v1/trips/{trip_id}/live-location/` endpoint is accessible
- Check browser console for JavaScript errors

### Location not updating

- Ensure the UserLocation model has data for the driver
- Verify the trip status is "ongoing"
- Check that the driver has a UserLocation record in the database

### Static files not loading

- Run `python manage.py collectstatic` to collect static files
- Ensure `DEBUG = True` in development or static files are properly configured
- Check STATIC_URL and STATIC_ROOT settings

## Future Enhancements

1. Add real-time updates using WebSocket (already configured in consumer.py)
2. Add route polyline showing the driver's path
3. Add multiple marker support for multiple drivers
4. Add distance and ETA calculations
5. Add geofencing alerts
6. Add trip history with location trail
