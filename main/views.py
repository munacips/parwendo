from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404, render
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import Company, PaymentTransaction, User, DriverProfile, FCMDevice, Vehicle, Trip, Booking, ChatThread, ChatMessage, UserReport, OTP, FCMDevice, Review, SOSAlert
from .serializers import CreateCompanySerializer, CompanySerializer, UserReportCreateSerializer, UserReportSerializer, ChatCreateMessageSerializer, CreateThreadSerializer, UserStatisticsSerializer, CreateVehicleSerializer, UserSerializer, TripCreateSerializer, BookingCreateSerializer, CreateDriverProfileSerializer, DriverProfileSerializer, VehicleSerializer, TripSerializer, BookingSerializer, ChatThreadSerializer, ChatMessageSerializer, ReviewSerializer, CreateReviewSerializer, SOSAlertSerializer, CreateSOSAlertSerializer
import django_filters
from rest_framework.pagination import PageNumberPagination
import os
import math
import requests
from dotenv import load_dotenv
from pathlib import Path
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Sum, Count
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import random
from django.core.mail import send_mail
from django.http import Http404, FileResponse
from django.conf import settings
import firebase_admin
from firebase_admin import credentials, messaging
from django.http import HttpRequest, JsonResponse, HttpResponseBadRequest, HttpResponse
from oauth2_provider.views.base import TokenView
import json
from paynow import Paynow
from django.contrib.auth import get_user_model


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Initialise Paynow
PAYNOW = Paynow(
    integration_id=os.getenv("PAYNOW_INTEGRATION_ID"),
    integration_key=os.getenv("PAYNOW_INTEGRATION_KEY"),
    result_url='https://parwendo-eqps.onrender.com/api/v1/paynow_result',
    return_url='https://parwendo-eqps.onrender.com/api/v1/paynow_return',
)

PAYNOW.sandbox = True  # Set to False in production


# ========== FILTERS ==========


class TripFilter(django_filters.FilterSet):
    destination = django_filters.CharFilter(lookup_expr='icontains')
    start_location = django_filters.CharFilter(lookup_expr='icontains')
    start_time = django_filters.DateFilter(method='filter_by_date')
    near_x = django_filters.NumberFilter(method='filter_by_coordinates')
    near_y = django_filters.NumberFilter(method='filter_by_coordinates')
    radius_km = django_filters.NumberFilter(method='filter_by_coordinates')
    available = django_filters.BooleanFilter(method='filter_by_availability')

    class Meta:
        model = Trip
        fields = ['driver', 'destination', 'start_location',
                  'near_x', 'near_y', 'radius_km', 'available']

    def filter_by_date(self, queryset, name, value):
        """Filter trips by date, ignoring time"""
        if value:
            return queryset.filter(start_time__date=value)
        return queryset

    def filter_by_coordinates(self, queryset):
        """
        Filter using improved geographic distance calculation
        Usage: ?near_lat=40.7128&near_lon=-74.0060&radius_km=1

        Uses Haversine formula for more accurate distance on lat/lon coordinates
        """
        request = self.request
        if not request:
            return queryset

        near_lat = request.GET.get('near_x')
        near_lon = request.GET.get('near_y')
        radius_km = float(request.GET.get('radius_km', 1))

        if near_lat and near_lon:
            try:
                near_lat = float(near_lat)
                near_lon = float(near_lon)

                # More accurate bounding box calculation
                # Latitude: 1 degree ≈ 111 km everywhere
                lat_degree_radius = radius_km / 111.0

                # Longitude: varies by latitude
                lon_degree_radius = radius_km / \
                    (111.0 * math.cos(math.radians(near_lat)))

                # Filter by bounding box first (fast database operation)
                bbox_queryset = queryset.filter(
                    latitude__gte=near_lat - lat_degree_radius,
                    latitude__lte=near_lat + lat_degree_radius,
                    longitude__gte=near_lon - lon_degree_radius,
                    longitude__lte=near_lon + lon_degree_radius
                )

                # Then filter by actual circular distance using raw SQL
                # Haversine formula for accurate distance calculation
                return bbox_queryset.extra(
                    where=["""
                        6371 * acos(
                            cos(radians(%s)) * cos(radians(latitude)) * 
                            cos(radians(longitude) - radians(%s)) + 
                            sin(radians(%s)) * sin(radians(latitude))
                        ) <= %s
                    """],
                    params=[near_lat, near_lon, near_lat, radius_km]
                )

            except (ValueError, TypeError, ZeroDivisionError):
                pass

        return queryset

    def filter_by_availability(self, queryset, name, value):
        """Filter trips by availability (i.e., if there are available seats)"""
        if value is True:
            # Get trips that have available seats (not fully booked)
            from django.db.models import Count, F

            # Annotate queryset with booking count and filter where bookings < available_seats
            return queryset.annotate(
                booking_count=Count('bookings', filter=Q(
                    bookings__status__in=['confirmed', 'pending']))
            ).filter(
                booking_count__lt=F('available_seats'),
                start_time__gt=timezone.now()
            )
        elif value is False:
            # Get trips that are fully booked
            from django.db.models import Count, F

            return queryset.annotate(
                booking_count=Count('bookings', filter=Q(
                    bookings__status__in=['confirmed', 'pending']))
            ).filter(
                booking_count__gte=F('available_seats')
            )

        # If value is None or not specified, return all trips
        return queryset


class VehicleFilter(django_filters.FilterSet):
    class Meta:
        model = Vehicle
        fields = ['driver', 'vehicle_type', 'vehicle_make', 'vehicle_model', 'owner']


class CompanyFilter(django_filters.FilterSet):
    class Meta:
        model = Company
        fields = ['name', 'owner']


class UserFilter(django_filters.FilterSet):
    class Meta:
        model = User
        fields = ['id', 'username', 'is_driver']


class DriverProfileFilter(django_filters.FilterSet):
    class Meta:
        model = DriverProfile
        fields = ['user', 'license_number',
                  'national_id_number', 'verification_status', 'company']


class BookingFilter(django_filters.FilterSet):
    user = django_filters.NumberFilter(
        field_name='passenger__id', lookup_expr='exact')

    class Meta:
        model = Booking
        fields = ['trip', 'passenger', 'status', 'user']


class ChatThreadFilter(django_filters.FilterSet):
    booking = django_filters.NumberFilter(method='filter_by_booking')

    class Meta:
        model = ChatThread
        fields = ['trip', 'passenger', 'driver', 'booking']

    def filter_by_booking(self, queryset, name, value):
        """Filter chat threads by booking ID."""
        if value:
            trip = Booking.objects.filter(
                id=value).values_list('trip', flat=True).first()
            passenger = Booking.objects.filter(
                id=value).values_list('passenger', flat=True).first()
            driver = Booking.objects.filter(id=value).values_list(
                'trip__driver', flat=True).first()
            return queryset.filter(
                Q(trip__id=trip),
                Q(passenger__id=passenger),
                Q(driver__id=driver)
            )


class ChatMessageFilter(django_filters.FilterSet):
    thread = django_filters.NumberFilter(
        field_name='thread__id', lookup_expr='exact')

    class Meta:
        model = ChatMessage
        fields = ['thread', 'sender']


class UserReportFilter(django_filters.FilterSet):
    user = django_filters.NumberFilter(
        field_name='user__id', lookup_expr='exact')
    reported_user = django_filters.NumberFilter(
        field_name='reported_user__id', lookup_expr='exact')
    chat_thread = django_filters.NumberFilter(
        field_name='chat_thread__id', lookup_expr='exact')

    class Meta:
        model = UserReport
        fields = ['user', 'reported_user', 'chat_thread']


class ReviewFilter(django_filters.FilterSet):
    trip = django_filters.NumberFilter(
        field_name='trip__id', lookup_expr='exact')
    reviewer = django_filters.NumberFilter(
        field_name='reviewer__id', lookup_expr='exact')

    class Meta:
        model = Review
        fields = ['trip', 'reviewer']


class SOSAlertFilter(django_filters.FilterSet):
    user = django_filters.NumberFilter(
        field_name='user__id', lookup_expr='exact')
    driver = django_filters.NumberFilter(
        field_name='driver__id', lookup_expr='exact')
    trip = django_filters.NumberFilter(
        field_name='trip__id', lookup_expr='exact')

    class Meta:
        model = SOSAlert
        fields = ['user', 'driver', 'trip']

# ========== UTILS ==========


def apply_filter_and_respond(model, filter_class, serializer_class, request, paginate=False):
    filterset = filter_class(request.query_params,
                             queryset=model.objects.all())
    if not filterset.is_valid():
        return Response(filterset.errors, status=status.HTTP_400_BAD_REQUEST)

    if paginate:
        paginator = PageNumberPagination()
        paginated_qs = paginator.paginate_queryset(filterset.qs, request)
        serializer = serializer_class(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)
    else:
        serializer = serializer_class(filterset.qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


def get_and_respond(model, pk, serializer_class):
    obj = get_object_or_404(model, id=pk)
    serializer = serializer_class(obj)
    return Response(serializer.data, status=status.HTTP_200_OK)


def send_otp_to_user(user, code):
    email = getattr(user, 'email', None)
    phone = getattr(user, 'phone', None)

    if email:
        subject = "Your One-Time Password (OTP)"
        message = f"Your OTP code is: {code}\n\nThis code will expire in 5 minutes."
        from_email = None
        recipient_list = [email]

        try:
            send_mail(subject, message, from_email, recipient_list)
            print(f"OTP sent to email: {email}")
        except Exception as e:
            print(f"Failed to send email OTP to {email}: {e}")

    if phone:
        # Send OTP via SMS
        pass

    if not email and not phone:
        print(
            f"User {user.username} has no email or phone number to send OTP to.")


def generate_otp():
    return str(random.randint(100000, 999999))


def pdf_viewer(request, file_path):
    file_path = os.path.join(settings.MEDIA_ROOT, file_path)
    if not os.path.exists(file_path):
        raise Http404("File does not exist")

    response = FileResponse(open(file_path, 'rb'),
                            content_type='application/pdf')
    response["X-Frame-Options"] = "ALLOWALL"
    return response


def send_push_notification(token, title, body, data=None):
    # Ensure all values in data are strings
    if data:
        data = {str(k): str(v) for k, v in data.items()}
    else:
        data = {}
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        data=data
    )
    try:
        response = messaging.send(message)
    except messaging.UnregisteredError:
        print(
            f"Token {token} is invalid (UnregisteredError). Deleting from database.")
        FCMDevice.objects.filter(token=token).delete()
    except Exception as e:
        print(f"Failed to send push notification to {token}: {e}")


def send_whatsapp_message(to, name, message):

    # format to, add +263 if +263 is not there
    if to:
        to = to.strip()
        if to.startswith("0"):
            to = "+263" + to[1:]
        elif to.startswith("263"):
            to = "+" + to
        elif not to.startswith("+"):
            to = "+263" + to

    token = os.getenv("WHATSAPP_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    url = f"https://graph.facebook.com/v24.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": f"Hello {name}, {message}"
        }
    }

    response = requests.post(url, json=data, headers=headers)
    return response.json()


cred = credentials.Certificate(
    os.path.join(BASE_DIR, 'parwendo-c278c-firebase-adminsdk-fbsvc-46354a366f.json'))
firebase_admin.initialize_app(cred)

# ========== GENERIC CRUD VIEWS ==========


def create_object(request, serializer_class, extra_fields=None):
    data = request.data.copy()
    if extra_fields:
        data.update(extra_fields)
    serializer = serializer_class(
        data=data, context={'request': request})  # Add context
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def update_object(request, model, pk, serializer_class):
    obj = get_object_or_404(model, id=pk)
    serializer = serializer_class(obj, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def delete_object(model, pk):
    obj = get_object_or_404(model, id=pk)
    obj.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)

# ========== VIEWS ==========  # Organized by model


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def get_token_from_oauth(request):
    username = request.POST.get('username') or request.data.get('username')
    password = request.POST.get('password') or request.data.get('password')
    print(f"Getting token from oauth for user: {username}")

    if not username or not password:
        return Response({'error': 'Username and password are required'}, status=400)

    # Build a fake request mimicking OAuth2 token endpoint
    oauth_request = HttpRequest()
    oauth_request.method = "POST"
    oauth_request.POST = {
        "grant_type": "password",
        "username": username,
        "password": password,
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
    }

    # Call the token endpoint internally
    token_view = TokenView.as_view()
    response = token_view(oauth_request)

    try:
        response_data = json.loads(response.content)
    except json.JSONDecodeError:
        response_data = {}

    if response.status_code == 200:
        # Successful authentication
        User = get_user_model()
        user = User.objects.get(username=username)
        response_data['user_id'] = user.id
        response_data['username'] = username
        response_data['email'] = user.email
        return Response(response_data, status=200)

    elif response.status_code == 400 and response_data.get("error") == "invalid_grant":
        # Wrong username or password
        return Response({'error': 'Invalid username or password'}, status=401)

    elif response.status_code == 401 and response_data.get("error") == "invalid_client":
        # Invalid client credentials
        return Response({'error': 'Invalid client credentials'}, status=401)

    else:
        return Response({
            'error': response_data.get('error', 'Authentication failed'),
            'details': response_data.get('error_description', response.content.decode())
        }, status=response.status_code)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def trips(request):
    if request.method == 'GET':
        return apply_filter_and_respond(Trip, TripFilter, TripSerializer, request, paginate=True)
    return create_object(request, TripCreateSerializer, {'driver': request.user.id})


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def trip_details(request, id):
    if request.method == 'GET':
        return get_and_respond(Trip, id, TripSerializer)
    elif request.method == 'PATCH':
        return update_object(request, Trip, id, TripSerializer)
    return delete_object(Trip, id)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def vehicles(request):
    if request.method == 'GET':
        return apply_filter_and_respond(Vehicle, VehicleFilter, VehicleSerializer, request)
    return create_object(request, CreateVehicleSerializer, {'driver': request.user.id})


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def vehicle_details(request, id):
    if request.method == 'GET':
        return get_and_respond(Vehicle, id, VehicleSerializer)
    elif request.method == 'PATCH':
        return update_object(request, Vehicle, id, VehicleSerializer)
    return delete_object(Vehicle, id)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def companies(request):
    if request.method == 'GET':
        return apply_filter_and_respond(Company, CompanyFilter, CompanySerializer, request)
    return create_object(request, CreateCompanySerializer)


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def company_details(request, id):
    if request.method == 'GET':
        return get_and_respond(Company, id, CompanySerializer)
    elif request.method == 'PATCH':
        return update_object(request, Company, id, CompanySerializer)
    return delete_object(Company, id)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def users(request):
    if request.method == 'GET':
        return apply_filter_and_respond(User, UserFilter, UserSerializer, request)

    serializer = UserSerializer(
        data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.save()

    otp_code = generate_otp()
    otp_expiry = timezone.now() + timedelta(minutes=5)
    OTP.objects.create(user=user, code=otp_code, expires_at=otp_expiry)

    send_otp_to_user(user, otp_code)

    return Response(serializer.data, status=status.HTTP_201_CREATED)


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def user_details(request, id):
    if request.method == 'GET':
        return get_and_respond(User, id, UserSerializer)
    elif request.method == 'PATCH':
        return update_object(request, User, id, UserSerializer)
    return delete_object(User, id)


@csrf_exempt
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def users_statistics(request, id):
    user = User.objects.get(id=id)

    # Booking statistics for the user as a passenger
    booking_stats = Booking.objects.filter(passenger=user).aggregate(
        total_bookings=Count('id'),
        confirmed_bookings=Count('id', filter=Q(status='confirmed')),
        pending_bookings=Count('id', filter=Q(status='pending')),
        cancelled_bookings=Count('id', filter=Q(status='cancelled')),
        total_amount_spent=Sum('total_price', filter=Q(
            status='confirmed')) or Decimal('0.00')
    )

    # Trip statistics for the user as a driver (if they are a driver)
    trip_stats = {}
    if hasattr(user, 'driverprofile'):
        trip_stats = Trip.objects.filter(driver=user).aggregate(
            total_trips=Count('id'),
            completed_trips=Count('id', filter=Q(status='completed'))
        )

        # Calculate total amount earned from confirmed bookings on user's trips
        earned_amount = Booking.objects.filter(
            trip__driver=user,
            status='confirmed'
        ).aggregate(
            total_earned=Sum('total_price')
        )['total_earned'] or Decimal('0.00')

        trip_stats['total_amount_earned'] = earned_amount
    else:
        trip_stats = {
            'total_trips': 0,
            'completed_trips': 0,
            'total_amount_earned': Decimal('0.00')
        }

    # Combine all statistics
    statistics_data = {
        'total_bookings': booking_stats['total_bookings'],
        'confirmed_bookings': booking_stats['confirmed_bookings'],
        'pending_bookings': booking_stats['pending_bookings'],
        'cancelled_bookings': booking_stats['cancelled_bookings'],
        'total_trips': trip_stats['total_trips'],
        'completed_trips': trip_stats['completed_trips'],
        'total_amount_spent': booking_stats['total_amount_spent'],
        'total_amount_earned': trip_stats['total_amount_earned']
    }

    serializer = UserStatisticsSerializer(statistics_data)
    return Response(serializer.data, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def driver_profiles(request):
    if request.method == 'GET':
        return apply_filter_and_respond(DriverProfile, DriverProfileFilter, DriverProfileSerializer, request)
    user = User.objects.get(id=request.user.id)
    user.is_driver = True
    user.save()
    return create_object(request, CreateDriverProfileSerializer, {'user': request.user.id})


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def driver_profile_details(request, id):
    if request.method == 'GET':
        return get_and_respond(DriverProfile, id, DriverProfileSerializer)
    elif request.method == 'PATCH':
        return update_object(request, DriverProfile, id, DriverProfileSerializer)
    return delete_object(DriverProfile, id)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def bookings(request):
    if request.method == 'GET':
        return apply_filter_and_respond(Booking, BookingFilter, BookingSerializer, request)
    # return create_object(request, BookingCreateSerializer, {'passenger': request.user.id})
    data = request.data.copy()
    data.update({'passenger': request.user.id})
    serializer = BookingCreateSerializer(
        data=data, context={'request': request})
    if serializer.is_valid():
        booking = serializer.save()

        # Serialize the created booking to get all fields
        booking_data = BookingSerializer(booking).data

        # Send notification to the driver
        trip = booking.trip
        driver = trip.driver.user
        passenger = booking.passenger

        fcm_tokens = FCMDevice.objects.filter(
            user=driver).values_list('token', flat=True)
        notification_data = {
            "booking_id": booking_data['id'],
            "screen": "booking",
        }
        for token in fcm_tokens:
            send_push_notification(
                token, "New Booking", "You have received a new booking from " + passenger.username, notification_data)
        send_whatsapp_message(driver.phone, passenger.username,
                              "You have received a new booking from " + passenger.username)

        return Response(booking_data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def booking_details(request, id):
    if request.method == 'GET':
        return get_and_respond(Booking, id, BookingSerializer)
    elif request.method == 'PATCH':
        # return update_object(request, Booking, id, BookingSerializer)
        obj = Booking.objects.get(id=id)  # get_object_or_404(model, id=pk)
        serializer = BookingSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

            def handle_status(status):
                match status:
                    case 'confirmed':
                        # Generate and save confirmation code
                        code = random.randint(100000, 999999)
                        obj.code = code
                        obj.save()

                        # Notify Passenger
                        for token in fcm_tokens:
                            send_push_notification(
                                token, "Booking Accepted", f"Your booking for the trip [{trip.start_location} -> {trip.destination}] has been accepted. Code: {code}", data)
                        send_whatsapp_message(obj.passenger.phone, passenger.username,
                                              "Your booking for the trip [{trip.start_location} -> {trip.destination}] has been accepted. Code: {code}")

                        # Notify Driver
                        driver_user = trip.driver.user
                        driver_tokens = FCMDevice.objects.filter(
                            user=driver_user).values_list('token', flat=True)
                        for d_token in driver_tokens:
                            send_push_notification(
                                d_token, "Booking Confirmed", f"Booking confirmed for {passenger.username}. Code: {code}", data)
                        send_whatsapp_message(driver_user.phone, passenger.username,
                                              "Booking confirmed for {passenger.username}. Code: {code}")

                        return
                    case 'rejected':
                        for token in fcm_tokens:
                            send_push_notification(
                                token, "Booking Rejected", f"Your booking for the trip [{trip.start_location} -> {trip.destination}] has been rejected", data)
                        send_whatsapp_message(obj.passenger.phone, passenger.username,
                                              "Your booking for the trip [{trip.start_location} -> {trip.destination}] has been rejected")
                        return

            # Send notification to the passenger
            if 'status' in serializer.data:
                trip = Trip.objects.get(id=obj.trip.id)
                passenger = obj.passenger
                fcm_tokens = FCMDevice.objects.filter(
                    user=passenger).values_list('token', flat=True)

                data = {
                    "booking_id": serializer.data['id'],
                    "screen": "booking",
                }
                handle_status(serializer.data['status'])

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    return delete_object(Booking, id)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def chat_threads(request):
    if request.method == 'GET':
        return apply_filter_and_respond(ChatThread, ChatThreadFilter, ChatThreadSerializer, request)
    return create_object(request, CreateThreadSerializer)


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def chat_thread_details(request, id):
    if request.method == 'GET':
        return get_and_respond(ChatThread, id, ChatThreadSerializer)
    elif request.method == 'PATCH':
        return update_object(request, ChatThread, id, ChatThreadSerializer)
    return delete_object(ChatThread, id)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def chat_messages(request):
    if request.method == 'GET':
        return apply_filter_and_respond(ChatMessage, ChatMessageFilter, ChatMessageSerializer, request)
    # return create_object(request, ChatCreateMessageSerializer)
    data = request.data.copy()
    serializer = ChatCreateMessageSerializer(
        data=data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        # Send Push Notifiction
        thread = serializer.data['thread']

        passenger = ChatThread.objects.get(id=thread).passenger
        driver = ChatThread.objects.get(id=thread).driver
        if request.user == passenger:
            user = driver.user
            other_user = passenger.username
        else:
            user = passenger
            other_user = driver.user.username
        fcm_tokens = FCMDevice.objects.filter(
            user=user).values_list('token', flat=True)
        data = {
            "thread_id": serializer.data['thread'],
            "screen": "chat",
        }
        for fcm_token in fcm_tokens:
            if fcm_token:
                send_push_notification(
                    fcm_token, "New Message", other_user + ' : ' + serializer.data['message'], data)
        send_whatsapp_message(user.phone, other_user,
                              serializer.data['message'])
        print("Notification Sent!")
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def chat_message_details(request, id):
    if request.method == 'GET':
        return get_and_respond(ChatMessage, id, ChatMessageSerializer)
    elif request.method == 'PATCH':
        return update_object(request, ChatMessage, id, ChatMessageSerializer)
    return delete_object(ChatMessage, id)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_reports(request):
    if request.method == 'GET':
        return apply_filter_and_respond(UserReport, UserReportFilter, UserReportSerializer, request)
    return create_object(request, UserReportCreateSerializer, {'user': request.user.id})


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def user_report_details(request, id):
    if request.method == 'GET':
        return get_and_respond(UserReport, id, UserReportSerializer)
    elif request.method == 'PATCH':
        return update_object(request, UserReport, id, UserReportSerializer)
    return delete_object(UserReport, id)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    username = request.data.get("username")
    code = request.data.get("otp")

    try:
        print("Username : ", username)
        print("Code : ", code)
        user = User.objects.get(username=username)
        otp = OTP.objects.filter(user=user, code=code).order_by(
            '-expires_at').first()

        if not otp or otp.is_expired():
            return Response({"error": "Invalid or expired OTP"}, status=400)

        otp.delete()
        user.is_verified = True
        return Response({"message": "OTP verified successfully"}, status=200)

    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def resend_otp(request):
    username = request.data.get("username")

    try:
        user = User.objects.get(username=username)
        otp_code = generate_otp()
        otp_expiry = timezone.now() + timedelta(minutes=5)
        OTP.objects.create(user=user, code=otp_code, expires_at=otp_expiry)

        # delete any existing OTPs for the user
        OTP.objects.filter(user=user).exclude(code=otp_code).delete()

        send_otp_to_user(user, otp_code)

        return Response({"message": "OTP resent successfully"}, status=200)

    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_fcm_token(request):
    token = request.data.get('token')
    user_id = request.data.get('user_id')
    user = User.objects.get(id=user_id)
    if token:
        FCMDevice.objects.update_or_create(
            user=user,
            defaults={'token': token}
        )
        return Response({"message": "FCM token registered successfully"}, status=200)
    return Response({"error": "Token is required"}, status=400)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def sos_alerts(request):
    if request.method == 'GET':
        return apply_filter_and_respond(SOSAlert, SOSAlertFilter, SOSAlertSerializer, request)
    data = request.data.copy()
    serializer_class = CreateSOSAlertSerializer
    serializer = serializer_class(
        data=data, context={'request': request})
    if serializer.is_valid():
        sos_alert = serializer.save()

        # Auto-populate fields based on user's active trip
        user = request.user
        active_trip = None

        # 1. Check if user is a passenger in an active booking
        # We look for confirmed bookings where the trip is ongoing or scheduled (recently started?)
        # take the latest confirmed booking on an active trip.
        active_booking = Booking.objects.filter(
            passenger=user,
            status='confirmed',
            trip__status__in=['ongoing', 'scheduled']
        ).order_by('-trip__start_time').first()

        if active_booking:
            active_trip = active_booking.trip

        # 2. If not passenger, check if user is a driver of an active trip
        if not active_trip and hasattr(user, 'driverprofile'):
            active_trip = Trip.objects.filter(
                driver=user.driverprofile,
                status__in=['ongoing', 'scheduled']
            ).order_by('-start_time').first()

        if active_trip:
            sos_alert.trip = active_trip
            sos_alert.driver = active_trip.driver
            sos_alert.vehicle = active_trip.vehicle
            sos_alert.destination = active_trip.destination
            sos_alert.source = active_trip.start_location
            sos_alert.save()

            # Re-serialize to include populated fields
            return Response(SOSAlertSerializer(sos_alert).data, status=status.HTTP_201_CREATED)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def sos_alert_details(request, id):
    if request.method == 'GET':
        return get_and_respond(SOSAlert, id, SOSAlertSerializer)
    elif request.method == 'PATCH':
        return update_object(request, SOSAlert, id, SOSAlertSerializer)
    return delete_object(SOSAlert, id)

    # # Resolve user: prefer passed user_id, else use authenticated user
    # user = None
    # if user_id:
    #     try:
    #         user = User.objects.get(id=user_id)
    #     except User.DoesNotExist:
    #         return JsonResponse({'error': 'user_id not found'}, status=404)
    # else:
    #     if request.user and getattr(request.user, 'is_authenticated', False):
    #         user = request.user

    # # Create or update FCMDevice
    # try:
    #     device, created = FCMDevice.objects.update_or_create(
    #         token=token,
    #         defaults={'user': user} if user else {},
    #     )
    # except Exception as e:
    #     print("[ERROR] saving FCMDevice:", e)
    #     return JsonResponse({'error': 'failed to save token'}, status=500)

    # return JsonResponse({'token': device.token, 'created': created}, status=201 if created else 200)
    # try:
    #     user = User.objects.get(id=user_id)
    # except User.DoesNotExist:
    #     return Response({"error": "User not found"}, status=404)
    # if token:
    #     FCMDevice.objects.update_or_create(
    #         user=user,
    #         defaults={'token': token}
    #     )
    #     return Response({"message": "FCM token registered successfully"}, status=200)
    # return Response({"error": "Token is required"}, status=400)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def reviews(request):
    if request.method == 'GET':
        return apply_filter_and_respond(Review, None, ReviewSerializer, request, paginate=True)
    return create_object(request, CreateReviewSerializer, {'reviewer': request.user.id})


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def review_details(request, id):
    if request.method == 'GET':
        return get_and_respond(Review, id, ReviewSerializer)
    elif request.method == 'PATCH':
        return update_object(request, Review, id, ReviewSerializer)
    return delete_object(Review, id)


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def zipit_create_checkout(request):
    """
    Calls the OPPWA checkout API and returns the response.
    """

    url = "https://eu-test.oppwa.com/v1/checkouts"

    entityId = request.data.get("entityId")
    amount = request.data.get("amount")
    currency = request.data.get("currency")
    paymentType = request.data.get("paymentType")
    integrity = request.data.get("integrity")

    payload = {
        "entityId": entityId or "8a8294174b7ecb28014b9699220015ca",
        "amount": amount,
        "currency": currency,
        "paymentType":  paymentType or "DB",
        "integrity": integrity or "true"
    }

    headers = {
        "Authorization": "Bearer OGFjN2E0Yzc5Mzk0YmRjODAxOTM5NzM2ZjFhNzA2NDF8enlac1lYckc4QXk6bjYzI1NHNng="
    }

    try:
        res = requests.post(url, data=payload, headers=headers)
        res.raise_for_status()  # raises HTTPError for 4xx/5xx
        return Response(res.json(), status=res.status_code)

    except requests.exceptions.HTTPError as http_err:
        return Response(
            {"error": str(http_err), "details": res.text},
            status=res.status_code if res else status.HTTP_502_BAD_GATEWAY
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@csrf_exempt
@permission_classes([IsAuthenticated])
def zipit_payment_page(request, checkout_id):
    shopper_result_url = request.build_absolute_uri(
        "/api/v1/zipit_payment/result/")
    return render(request, "main/payment.html", {
        "checkoutId": checkout_id,
        "shopperResultUrl": shopper_result_url
    })


def zipit_payment_result(request):
    resource_path = request.GET.get("resourcePath")
    if not resource_path:
        return JsonResponse({"error": "Missing resourcePath"}, status=400)

    url = f"https://eu-test.oppwa.com{resource_path}"
    headers = {
        "Authorization": "Bearer YOUR_KEY"
    }

    res = requests.get(url, headers=headers)
    result = res.json()

    # Update your DB here (mark order as paid, etc.)

    # Send Notification to user
    user_id = result.get("customer", {}).get("id")
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            fcm_tokens = FCMDevice.objects.filter(
                user=user).values_list('token', flat=True)
            data = {
                "screen": "payments",
            }
            for token in fcm_tokens:
                send_push_notification(
                    token, "Payment Successful", "Your payment was successful!", data)
            send_whatsapp_message(
                user.phone, user.username, "Your payment was successful!")
        except User.DoesNotExist:
            pass

    return JsonResponse(result)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    """
    Expected POST JSON body:
    {
    "amount": 10.50,
    "method": "ecocash", # or "onemoney", "vmc", etc.
    "phone": "0777xxxxxx", # for mobile methods
    "email": "user@example.com",
    "reference": "ORDER123",
    "description": "Payment for order 123"
    }
    """

    payload = request.data

    # Extract fields (you should validate these)
    amount = payload.get("amount")
    method = payload.get("method")
    phone = payload.get("phone")
    email = payload.get("email")
    reference = payload.get("reference")
    description = payload.get("description") or "Payment"

    user = User.objects.get(id=request.user.id)

    if not (amount and method and reference and email):
        return HttpResponseBadRequest("Missing required fields")

    # Create Paynow payment object
    payment = PAYNOW.create_payment(reference, email)
    payment.add(description, amount)

    # Depending on method, send mobile or normal
    if method.lower() in ("ecocash", "onemoney"):
        # mobile express checkout
        response = PAYNOW.send_mobile(payment, phone, method.lower())
    else:
        # e.g. vmc, etc.
        response = PAYNOW.send(payment)
    # Save the transaction to DB
    # Model PaymentTransaction can store: reference, method, phone, email,
    # poll_url, status (initial, pending), any redirect_url, etc.
    tx = PaymentTransaction.objects.create(
        user=user,
        reference=reference,
        email=email,
        method=method.lower(),
        phone=phone,
        amount=amount,
        status="initiated",
        poll_url=response.poll_url if hasattr(response, "poll_url") else None,
        redirect_url=response.redirect_url if hasattr(
            response, "redirect_url") else None,
    )
    # Return details to frontend (ensure all fields are JSON serializable)

    def safe_get(obj, attr, default=None):
        value = getattr(obj, attr, default)
        # If value is a method or type, skip it
        if callable(value) or isinstance(value, type):
            return default
        return value

    result = {
        "success": bool(safe_get(response, "success", False)),
        "redirect_url": safe_get(response, "redirect_url"),
        "poll_url": safe_get(response, "poll_url"),
        "instructions": safe_get(response, "instructions"),
    }
    # Optionally, print only serializable dict for debugging
    try:
        print({k: v for k, v in result.items()})
    except Exception:
        pass
    return JsonResponse(result)


@csrf_exempt
def payment_status(request):
    """
    Endpoint to be called by front-end or by your scheduled task to check status.
    Expects POST JSON:
    {
    "poll_url": "...",
    "reference": "ORDER123"
    }
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Only POST")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except:
        return HttpResponseBadRequest("Bad JSON")

    poll_url = payload.get("poll_url")
    reference = payload.get("reference")
    if not (poll_url and reference):
        return HttpResponseBadRequest("Missing fields")

    # Find our transaction
    try:
        tx = PaymentTransaction.objects.get(
            reference=reference, poll_url=poll_url)
    except PaymentTransaction.DoesNotExist:
        return HttpResponseBadRequest("Transaction not found")

    # Check status from Paynow
    status = PAYNOW.check_transaction_status(poll_url)
    # status will have properties like .paid, .status (string) etc.
    # You can inspect its docs or print status to see possible attributes
    if status.paid:
        tx.status = "paid"
    else:
        tx.status = status.status or "unknown"
    tx.save()

    return JsonResponse({
        "reference": reference,
        "status": tx.status,
    })


def paynow_result(request):
    """
    Paynow sends a server to server POST here when payment is complete
    """
    if request.method == "POST":
        # Paynow sends reference, status and amount
        data = request.POST
        reference = data.get("reference")
        status = data.get("status")

        try:
            tx = PaymentTransaction.objects.get(reference=reference)
            tx.status = status.lower()
            tx.save()
        except PaymentTransaction.DoesNotExist:
            pass
        return HttpResponse("OK")
    return HttpResponse("Only POST allowed", status=405)


def paynow_return(request):
    """
    User is redirected here after completing/cancelling payment. Shows a friendly message.
    """
    reference = request.GET.get("reference")
    status = request.GEt.get("status")
    return HttpResponse(f"{status}")


def debug_time(request):
    return JsonResponse({
        'server_time': timezone.now().isoformat(),
        'user': str(request.user),
    })
