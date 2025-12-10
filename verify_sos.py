
from main.models import User, DriverProfile, Vehicle, Trip, Booking, SOSAlert
from main.views import sos_alerts
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
import os
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parwendo.settings')
django.setup()

# Imports after setup - CRITICAL: Do not move these up


def run_verification():
    print("Setting up test data...")
    try:
        # Clean up prior test data
        User.objects.filter(username__startswith='test_').delete()
        SOSAlert.objects.filter(location='Gweru').delete()
    except Exception as e:
        print(f"Cleanup warning: {e}")

    # Create Driver User
    driver_user = User.objects.create_user(
        username='test_driver', password='password123', is_driver=True)

    # Create Driver Profile
    driver_profile = DriverProfile.objects.create(
        user=driver_user,
        license_number='DL12345',
        national_id_number='ID12345'
    )

    # Create Vehicle
    vehicle = Vehicle.objects.create(
        driver=driver_profile,
        vehicle_number='ABC-123',
        vehicle_type='car',
        vehicle_make='Toyota',
        vehicle_model='Corolla',
        vehicle_color='White',
        vehicle_year=2020
    )

    # Create Trip
    trip = Trip.objects.create(
        driver=driver_profile,
        destination='Harare',
        start_location='Bulawayo',
        vehicle=vehicle,
        start_time=timezone.now() + timedelta(hours=1),
        estimated_end_time=timezone.now() + timedelta(hours=5),
        price_per_seat=10.00,
        status='ongoing'
    )

    # Create Passenger User
    passenger_user = User.objects.create_user(
        username='test_passenger', password='password123')

    # Create Booking
    Booking.objects.create(
        trip=trip,
        passenger=passenger_user,
        status='confirmed',
        number_of_seats=1
    )

    print("Test data created. Testing SOS Alert for Passenger...")

    factory = APIRequestFactory()
    request = factory.post('/api/v1/sos_alerts/',
                           {'location': 'Gweru'}, format='json')
    force_authenticate(request, user=passenger_user)

    response = sos_alerts(request)

    if response.status_code == status.HTTP_201_CREATED:
        print("SOS Alert created successfully.")
        alert_data = response.data

        # Validation
        success = True

        if alert_data.get('trip') and alert_data['trip']['id'] == trip.id:
            print("SUCCESS: Trip populated correctly.")
        else:
            print(
                f"FAILURE: Trip not populated correctly. Got: {alert_data.get('trip')}")
            success = False

        if alert_data.get('driver') and alert_data['driver']['id'] == driver_profile.id:
            print("SUCCESS: Driver populated correctly.")
        else:
            print("FAILURE: Driver not populated.")
            success = False

        if alert_data.get('destination') == 'Harare':
            print("SUCCESS: Destination populated.")
        else:
            print("FAILURE: Destination not populated.")
            success = False

        if success:
            print("VERIFICATION COMPLETE: ALL CHECKS PASSED")

    else:
        print(f"FAILURE: Status code {response.status_code}")
        print(response.data)

    # Cleanup
    print("Cleaning up...")
    try:
        User.objects.filter(username__startswith='test_').delete()
    except:
        pass


if __name__ == '__main__':
    try:
        run_verification()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"An error occurred: {e}")
