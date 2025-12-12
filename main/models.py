from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    phone = models.CharField(max_length=15, blank=True, null=True, unique=True)
    profile_picture = models.ImageField(
        upload_to='kyc/profile_pictures/', blank=True, null=True)
    is_driver = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    is_private = models.BooleanField(default=False)


class DriverProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='driver_profile')
    company = models.ForeignKey(
        'Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='drivers')
    license_number = models.CharField(max_length=20, unique=True)
    national_id_number = models.CharField(max_length=20, unique=True)
    license_upload = models.FileField(
        upload_to='kyc/licenses/', blank=True, null=True)
    license_upload_backside = models.FileField(upload_to='kyc/licenses/')
    national_id_upload = models.FileField(
        upload_to='kyc/national_ids/', blank=True, null=True)
    verification_status = models.CharField(max_length=20, choices=[(
        'pending', 'Pending'), ('verified', 'Verified'), ('rejected', 'Rejected')], default='pending')

    def __str__(self):
        return f"{self.user.username} - {self.verification_status}"


class Company(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name + " by " + self.owner.username


class Vehicle(models.Model):
    driver = models.ForeignKey(
        DriverProfile, on_delete=models.CASCADE, related_name='vehicles',null=True,blank=True)
    owner = models.ForeignKey(Company, on_delete=models.DO_NOTHING,null=True,blank=True)
    vehicle_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=[(
        'car', 'Car'), ('bike', 'Bike'), ('truck', 'Truck')])
    vehicle_model = models.CharField(max_length=50)
    vehicle_make = models.CharField(max_length=50)
    vehicle_color = models.CharField(max_length=20)
    vehicle_registration_upload = models.FileField(
        upload_to='vehicles/registration/', blank=True, null=True)
    insurance_upload = models.FileField(
        upload_to='vehicles/insurance/', blank=True, null=True)
    vehicle_year = models.IntegerField()
    vehicle_capacity = models.IntegerField(default=1)
    vehicle_description = models.TextField(blank=True, null=True)
    verified = models.BooleanField(default=False)
    vehicle_picture = models.ImageField(
        upload_to='vehicles/pictures/', blank=True, null=True)

    def __str__(self):
        return f"{self.vehicle_make} {self.vehicle_model} ({self.vehicle_number}) - {self.driver.user.username}"


class Trip(models.Model):
    driver = models.ForeignKey(
        DriverProfile, on_delete=models.CASCADE, related_name='trips')
    destination = models.CharField(max_length=255)
    start_location = models.CharField(max_length=255)
    start_x_coordinates = models.CharField(
        max_length=100, null=True, blank=True)
    start_y_coordinates = models.CharField(
        max_length=100, null=True, blank=True)
    destination_x_coordinates = models.CharField(
        max_length=100, null=True, blank=True)
    destination_y_coordinates = models.CharField(
        max_length=100, null=True, blank=True)
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name='trips')
    start_time = models.DateTimeField()
    estimated_end_time = models.DateTimeField()
    available_seats = models.IntegerField(default=1)
    price_per_seat = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[(
        'scheduled', 'Scheduled'), ('ongoing', 'Ongoing'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='scheduled')

    def __str__(self):
        return f"Trip {self.id} by {self.driver.user.username} to {self.destination}"


class Booking(models.Model):
    trip = models.ForeignKey(
        Trip, on_delete=models.CASCADE, related_name='bookings')
    passenger = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='bookings')
    booking_time = models.DateTimeField(auto_now_add=True)
    number_of_seats = models.IntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), (
        'confirmed', 'Confirmed'), ('cancelled', 'Cancelled'), ('rejected', 'Rejected')], default='pending')
    code = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('trip', 'passenger')

    def __str__(self):
        return f"Booking {self.id} for {self.passenger.username} on trip {self.trip.id}"

    def save(self, *args, **kwargs):
        if not self.total_price:  # Only calculate if not already set
            self.total_price = self.number_of_seats * self.trip.price_per_seat
        super().save(*args, **kwargs)  # This was missing!


class ChatThread(models.Model):
    trip = models.ForeignKey(
        Trip, on_delete=models.CASCADE, related_name='chat_threads')
    passenger = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='chat_threads')
    driver = models.ForeignKey(
        DriverProfile, on_delete=models.CASCADE, related_name='chat_threads')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('trip', 'passenger', 'driver')


class ChatMessage(models.Model):
    thread = models.ForeignKey(
        ChatThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_messages')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    is_location = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']
        verbose_name_plural = 'Chat Messages'


class FavouriteDriver(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='favourite_drivers')
    driver = models.ForeignKey(
        DriverProfile, on_delete=models.CASCADE, related_name='favourited_by')

    class Meta:
        unique_together = ('user', 'driver')

    def __str__(self):
        return f"{self.user.username} favourites {self.driver.user.username}"


class FavouriteDestination(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='favourite_destinations')
    destination = models.CharField(max_length=255)
    save_as = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        unique_together = ('user', 'destination')

    def __str__(self):
        return f"{self.user.username} favourites {self.destination}"


class UserReport(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='reports_made')
    reported_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='reports_received')
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    chat_thread = models.ForeignKey(
        ChatThread, on_delete=models.CASCADE, related_name='reports', null=True, blank=True)

    def __str__(self):
        return f"Report by {self.user.username} against {self.reported_user.username}"


class OTP(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()

    def is_expired(self):
        return timezone.now() > self.expires_at


class FCMDevice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Review(models.Model):
    trip = models.ForeignKey(
        Trip, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='reviews_given')
    rating = models.IntegerField()
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('trip', 'reviewer')

    def __str__(self):
        return f"Review by {self.reviewer.username} for trip {self.trip.id}"


class PaymentTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reference = models.CharField(max_length=255, unique=True)
    email = models.EmailField()
    method = models.CharField(max_length=50)
    phone = models.CharField(max_length=50, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    poll_url = models.TextField(blank=True, null=True)
    redirect_url = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default="Initiated")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SOSAlert(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sos_alerts')
    trip = models.ForeignKey(
        Trip, on_delete=models.SET_NULL, null=True, blank=True, related_name='sos_alerts')
    driver = models.ForeignKey(
        DriverProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='sos_alerts_involved')
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='sos_alerts_involved')
    location = models.CharField(max_length=255)
    destination = models.CharField(max_length=255, blank=True, null=True)
    source = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    attended_to = models.BooleanField(default=False)

    def __str__(self):
        return f"SOS Alert by {self.user.username} at {self.created_at}"
