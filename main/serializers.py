from rest_framework import serializers
from .models import Company, Booking, ChatMessage, ChatThread, DriverProfile, Trip, User, Vehicle, UserReport, Review, SOSAlert


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name',
                  'last_name', 'phone', 'is_driver', 'profile_picture', 'password', 'is_private']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class DriverProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = DriverProfile
        fields = ['id', 'user', 'license_number', 'national_id_number',
                  'license_upload', 'license_upload_backside', 'national_id_upload', 'verification_status']


class CreateDriverProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = DriverProfile
        fields = ['user', 'license_number', 'national_id_number',
                  'license_upload', 'license_upload_backside', 'national_id_upload']

    def create(self, validated_data):
        # Ensure the user is set to the current user from context
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class VehicleSerializer(serializers.ModelSerializer):
    driver = DriverProfileSerializer()

    class Meta:
        model = Vehicle
        fields = ['id', 'driver', 'owner', 'vehicle_number', 'vehicle_type', 'vehicle_make',
                  'vehicle_model', 'vehicle_color', 'vehicle_year', 'vehicle_capacity', 'vehicle_description', 'vehicle_picture']


class CreateVehicleSerializer(serializers.ModelSerializer):
    driver = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Vehicle
        fields = ['driver', 'owner', 'vehicle_number', 'vehicle_type', 'vehicle_make',
                  'vehicle_model', 'vehicle_color', 'vehicle_year', 'vehicle_capacity', 'vehicle_description', 'vehicle_registration_upload', 'insurance_upload', 'vehicle_picture']

    def create(self, validated_data):
        validated_data['driver'] = self.context['request'].user.driver_profile
        return super().create(validated_data)


class CompanySerializer(serializers.ModelSerializer):

    class Meta:
        model = Company
        fields = ['name', 'owner', 'created', 'updated']


class TripSerializer(serializers.ModelSerializer):
    driver = DriverProfileSerializer()
    vehicle = VehicleSerializer()
    driver_name = serializers.SerializerMethodField()
    vehicle_name = serializers.SerializerMethodField()
    vehicle_picture = serializers.ImageField(
        source='vehicle.vehicle_picture', read_only=True)

    class Meta:
        model = Trip
        fields = ['id', 'driver', 'destination', 'start_location', 'vehicle', 'vehicle_name', 'driver_name', 'start_time', 'estimated_end_time', 'available_seats',
                  'price_per_seat', 'start_x_coordinates', 'start_y_coordinates', 'destination_x_coordinates', 'destination_y_coordinates', 'status', 'vehicle_picture']

    def get_driver_name(self, obj):
        return obj.driver.user.first_name + ' ' + obj.driver.user.last_name if obj.driver and obj.driver.user else None

    def get_vehicle_name(self, obj):
        return f"{obj.vehicle.vehicle_color} {obj.vehicle.vehicle_make} {obj.vehicle.vehicle_model} - {obj.vehicle.vehicle_number}" if obj.vehicle else None


class TripCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ['driver', 'destination', 'start_location', 'vehicle',
                  'start_time', 'estimated_end_time', 'available_seats', 'price_per_seat', 'start_x_coordinates', 'start_y_coordinates', 'destination_x_coordinates', 'destination_y_coordinates']

    def create(self, validated_data):
        # Ensure the driver is set to the current user from context
        validated_data['driver'] = self.context['request'].user.driver_profile
        return super().create(validated_data)


class BookingSerializer(serializers.ModelSerializer):
    trip = TripSerializer()
    passenger = UserSerializer()

    class Meta:
        model = Booking
        fields = ['id', 'trip', 'passenger', 'booking_time',
                  'number_of_seats', 'total_price', 'status']


class BookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['trip', 'number_of_seats']

    def create(self, validated_data):
        # Set the passenger to the current user from context
        validated_data['passenger'] = self.context['request'].user
        return super().create(validated_data)


class ChatThreadSerializer(serializers.ModelSerializer):
    trip = TripSerializer()
    passenger = UserSerializer()
    driver = DriverProfileSerializer()

    class Meta:
        model = ChatThread
        fields = ['id', 'trip', 'passenger', 'driver',
                  'created_at', 'updated_at', 'is_active']


class CreateThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatThread
        fields = ['id', 'trip', 'passenger', 'driver']


class ChatMessageSerializer(serializers.ModelSerializer):
    thread = ChatThreadSerializer()
    sender = UserSerializer()

    class Meta:
        model = ChatMessage
        fields = ['id', 'thread', 'sender',
                  'message', 'timestamp', 'is_location']
        read_only_fields = ['timestamp']


class ChatCreateMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['thread', 'sender', 'message', 'is_location']

    def create(self, validated_data):
        # Set the sender to the current user from context
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)


class UserStatisticsSerializer(serializers.Serializer):
    total_bookings = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    pending_bookings = serializers.IntegerField()
    cancelled_bookings = serializers.IntegerField()
    total_trips = serializers.IntegerField()
    completed_trips = serializers.IntegerField()
    total_amount_spent = serializers.DecimalField(
        max_digits=10, decimal_places=2)
    total_amount_earned = serializers.DecimalField(
        max_digits=10, decimal_places=2)


class UserReportSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = UserReport
        fields = ['id', 'user', 'reason', 'reported_user',
                  'created_at', 'is_resolved', 'chat_thread']


class UserReportCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserReport
        fields = ['user', 'reason', 'reported_user', 'chat_thread']

    def create(self, validated_data):
        # Set the user to the current user from context
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ReviewSerializer(serializers.ModelSerializer):
    trip = TripSerializer()
    reviewer = UserSerializer()

    class Meta:
        model = Review
        fields = ['id', 'trip', 'reviewer', 'rating', 'comment', 'created_at']


class CreateReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['trip', 'reviewer', 'rating', 'comment']

    def create(self, validated_data):
        # Set the reviewer to the current user from context
        validated_data['reviewer'] = self.context['request'].user
        return super().create(validated_data)


class SOSAlertSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    trip = TripSerializer()
    driver = DriverProfileSerializer()
    vehicle = VehicleSerializer()

    class Meta:
        model = SOSAlert
        fields = ['id', 'user', 'trip', 'driver', 'vehicle', 'location',
                  'destination', 'source', 'created_at', 'attended_to']


class CreateSOSAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = SOSAlert
        fields = ['location']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
