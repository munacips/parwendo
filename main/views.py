from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import User, DriverProfile, FCMDevice, Vehicle, Trip, Booking, ChatThread, ChatMessage, UserReport, OTP, FCMDevice, Review
from .serializers import UserReportCreateSerializer, UserReportSerializer, ChatCreateMessageSerializer, CreateThreadSerializer, UserStatisticsSerializer, CreateVehicleSerializer, UserSerializer, TripCreateSerializer, BookingCreateSerializer, CreateDriverProfileSerializer, DriverProfileSerializer, VehicleSerializer, TripSerializer, BookingSerializer, ChatThreadSerializer, ChatMessageSerializer, ReviewSerializer, CreateReviewSerializer
import django_filters
from rest_framework.pagination import PageNumberPagination
import os
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
from django.http import HttpRequest
from oauth2_provider.views.base import TokenView
from django.http import JsonResponse


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, '.env'))

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

    def filter_by_coordinates(self, queryset, name, value):
        """
        Filter using simple distance calculation
        Usage: ?near_x=40.7128&near_y=-74.0060&radius_km=1
        """
        request = self.request
        if not request:
            return queryset

        near_x = request.GET.get('near_x')
        near_y = request.GET.get('near_y')
        radius_km = float(request.GET.get('radius_km', 1))

        if near_x and near_y:
            try:
                near_x = float(near_x)
                near_y = float(near_y)

                # Simple bounding box filter (approximate)
                # 1 degree ≈ 111 km
                degree_radius = radius_km / 111.0

                return queryset.filter(
                    start_location_x__gte=near_x - degree_radius,
                    start_location_x__lte=near_x + degree_radius,
                    start_location_y__gte=near_y - degree_radius,
                    start_location_y__lte=near_y + degree_radius
                )
            except (ValueError, TypeError):
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
        fields = ['driver', 'vehicle_type', 'vehicle_make', 'vehicle_model']


class UserFilter(django_filters.FilterSet):
    class Meta:
        model = User
        fields = ['id', 'username', 'is_driver']


class DriverProfileFilter(django_filters.FilterSet):
    class Meta:
        model = DriverProfile
        fields = ['user', 'license_number',
                  'national_id_number', 'verification_status']


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
    phone = getattr(user, 'phone_number', None)

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
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        data=data or {}

    )
    response = messaging.send(message)


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

    token_view = TokenView.as_view()
    response = token_view(oauth_request)
    if response.status_code == 200:
        import json
        token_data = json.loads(response.content)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(username=username)
        token_data['user_id'] = user.id
        token_data['username'] = username

        return Response(token_data, status=200)
    else:
        return Response({'error': 'Authentication failed', 'details': response.content.decode()}, status=response.status_code)


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
@permission_classes([AllowAny])
def users(request):
    if request.method == 'GET':
        return apply_filter_and_respond(User, UserFilter, UserSerializer, request)

    serializer = UserSerializer(data=request.data, context={'request': request})
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
        serializer.save()

        # Send notification to the driver
        trip = Trip.objects.get(id=data["trip"])
        driver = User.objects.get(id=trip.driver)
        passenger = User.objects.get(id=serializer.data['passenger'])

        fcm_tokens = FCMDevice.objects.filter(
            user=driver).values_list('token', flat=True)
        data = {
            "booking_id": serializer.data['id'],
            "screen": "booking",
        }
        for token in fcm_tokens:
            send_push_notification(
                token, "New Booking", "You have recieved a new booking from " + passenger.username, data)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
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
                        for token in fcm_tokens:
                            send_push_notification(
                                token, "Booking Accepted", f"Your booking for the trip [{trip.start_location} -> {trip.destination}] has been accepted", data)
                        return
                    case 'rejected':
                        for token in fcm_tokens:
                            send_push_notification(
                                token, "Booking Rejected", f"Your booking for the trip [{trip.start_location} -> {trip.destination}] has been rejected", data)
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
            other_user = driver.username
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


def debug_time(request):
    return JsonResponse({
        'server_time': timezone.now().isoformat(),
        'user': str(request.user),
    })