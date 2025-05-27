from rest_framework import serializers
from .models import Booking, ChatMessage, ChatThread, DriverProfile, Trip, User, Vehicle

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone', 'is_driver']


class DriverProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = DriverProfile
        fields = ['id', 'user', 'license_number', 'national_id_number', 'license_upload', 'national_id_upload', 'verification_status']

    
class VehicleSerializer(serializers.ModelSerializer):
    driver = DriverProfileSerializer()

    class Meta:
        model = Vehicle
        fields = ['id', 'driver', 'vehicle_number', 'vehicle_type', 'vehicle_make', 'vehicle_model', 'vehicle_color', 'vehicle_registration_upload', 'insurance_upload']


class TripSerializer(serializers.ModelSerializer):
    driver = DriverProfileSerializer()
    vehicle = VehicleSerializer()

    class Meta:
        model = Trip
        fields = ['id', 'driver', 'destination', 'start_location', 'vehicle', 'start_time', 'estimated_end_time', 'available_seats', 'price_per_seat']

    
class BookingSerializer(serializers.ModelSerializer):
    trip = TripSerializer()
    passenger = UserSerializer()

    class Meta:
        model = Booking
        fields = ['id', 'trip', 'passenger', 'booking_time', 'number_of_seats', 'total_price', 'status']


class ChatThreadSerializer(serializers.ModelSerializer):
    trip = TripSerializer()
    passenger = UserSerializer()
    driver = DriverProfileSerializer()

    class Meta:
        model = ChatThread
        fields = ['id', 'trip', 'passenger', 'driver', 'created_at', 'updated_at', 'is_active']


class ChatMessageSerializer(serializers.ModelSerializer):
    thread = ChatThreadSerializer()
    sender = UserSerializer()

    class Meta:
        model = ChatMessage
        fields = ['id', 'thread', 'sender', 'content', 'timestamp']
        read_only_fields = ['timestamp']


