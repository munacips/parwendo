# Live Location Tracking - Setup & Testing Guide

## Prerequisites

✅ Django admin is set up
✅ Google Maps API is configured
✅ UserLocation model is populated with location data
✅ Static files are configured

## Setup Steps

### 1. Collect Static Files

Run this command to ensure the JavaScript file is available in your static directory:

```bash
python manage.py collectstatic --noinput
```

### 2. Verify the API Endpoint

Test that the live location endpoint works:

```bash
# Replace TRIP_ID with an actual trip ID
curl http://localhost:8000/api/v1/trips/TRIP_ID/live-location/
```

Expected response:

```json
{
  "status": "success",
  "username": "driver_username",
  "lat": 31.0335,
  "lng": -17.8252,
  "updated_at": "14:30:45"
}
```

### 3. Test in Admin Panel

1. Go to Django Admin → Trips
2. Open any trip's change form
3. Scroll to the bottom to find the "Start Live Tracking" button
4. Click the button
5. The map should appear below with the driver's current location

## What You Should See

### Before Clicking "Start Live Tracking"

- Trip information displayed (ID, Driver, Status)
- Instructions to click the button to view location

### After Clicking "Start Live Tracking"

- A map container appears
- Driver's current location is marked with a blue pin
- Driver name and last update time shown below the map
- "Stop Tracking" button in the top right

### Live Updates

- The map updates automatically every 5 seconds
- Marker moves as the driver's location changes
- Timestamp updates to show the latest location update

## Key Files

| File                                                   | Purpose                               |
| ------------------------------------------------------ | ------------------------------------- |
| `main/templates/admin/main/trip/change_form.html`      | Admin template with map container     |
| `static/static_files/admin/main/trip/live_tracking.js` | JavaScript for map functionality      |
| `main/admin.py`                                        | TripAdmin class configuration         |
| `main/views.py`                                        | API endpoint (get_trip_live_location) |
| `main/models.py`                                       | UserLocation model                    |

## Troubleshooting Checklist

- [ ] Is the trip in "ongoing" status? (API only returns location for ongoing trips)
- [ ] Does the driver have a UserLocation record with coordinates?
- [ ] Is the Google Maps API key valid and has proper permissions?
- [ ] Have you run `collectstatic`?
- [ ] Check browser console (F12 → Console) for JavaScript errors
- [ ] Are you using the correct API endpoint path?

## Common Issues & Solutions

### Issue: Map doesn't appear

**Solution:**

- Check browser console for errors
- Verify the `trip-map-container` div is present in the HTML
- Make sure Google Maps script loaded successfully

### Issue: "No latitude/longitude in response"

**Solution:**

- Ensure the trip status is "ongoing"
- Check that driver.user has a UserLocation record
- Verify coordinates are stored in the database

### Issue: "HTTP error! status: 404"

**Solution:**

- Verify the URL path is correct: `/api/v1/trips/{trip_id}/live-location/`
- Check that the trip ID is valid
- Ensure Django URLs are properly configured

### Issue: Static file not loading (live_tracking.js 404)

**Solution:**

```bash
# Clear and recollect static files
python manage.py collectstatic --clear --noinput
```

## Real-Time Location Updates

Currently, the system polls the API every 5 seconds. For true real-time updates using WebSocket:

1. WebSocket infrastructure is already configured (`consumer.py`, `routing.py`)
2. To enable, modify `live_tracking.js` to use `connectWebSocket()` instead of polling
3. This would provide instant updates instead of 5-second polling

## Performance Notes

- Polling every 5 seconds is reasonable for most use cases
- Reduces server load compared to real-time WebSocket
- Can be adjusted based on your requirements
- For high-traffic scenarios, consider caching or optimizing queries

## Next Steps

1. Test with actual driver location data
2. Monitor performance metrics
3. Adjust polling interval if needed
4. Consider implementing full WebSocket for real-time tracking
5. Add notifications when driver location changes significantly
