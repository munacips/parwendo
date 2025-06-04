from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import User, DriverProfile, Vehicle, Trip, Booking, ChatThread, ChatMessage
from .serializers import UserSerializer, TripCreateSerializer, BookingCreateSerializer, DriverProfileSerializer, VehicleSerializer, TripSerializer, BookingSerializer, ChatThreadSerializer, ChatMessageSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
import django_filters
from rest_framework.pagination import PageNumberPagination
import requests
import os
from dotenv import load_dotenv
from pathlib import Path
from django.views.decorators.csrf import csrf_exempt
import math
import django

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
                booking_count=Count('booking', filter=models.Q(booking__status__in=['confirmed', 'pending']))
            ).filter(
                booking_count__lt=F('available_seats')
            )
        elif value is False:
            # Get trips that are fully booked
            from django.db.models import Count, F
            
            return queryset.annotate(
                booking_count=Count('booking', filter=models.Q(booking__status__in=['confirmed', 'pending']))
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
    user = django_filters.NumberFilter(field_name='passenger__id', lookup_expr='exact')
    
    class Meta:
        model = Booking
        fields = ['trip', 'passenger', 'status', 'user']


class ChatThreadFilter(django_filters.FilterSet):
    class Meta:
        model = ChatThread
        fields = ['trip', 'passenger', 'driver']


class ChatMessageFilter(django_filters.FilterSet):
    class Meta:
        model = ChatMessage
        fields = ['thread', 'sender']

# ========== UTILS ==========


def apply_filter_and_respond(model, filter_class, serializer_class, request):
    filterset = filter_class(request.query_params,
                             queryset=model.objects.all())
    if not filterset.is_valid():
        return Response(filterset.errors, status=status.HTTP_400_BAD_REQUEST)

    paginator = PageNumberPagination()
    paginated_qs = paginator.paginate_queryset(filterset.qs, request)
    serializer = serializer_class(paginated_qs, many=True)
    return paginator.get_paginated_response(serializer.data)


def get_and_respond(model, pk, serializer_class):
    obj = get_object_or_404(model, id=pk)
    serializer = serializer_class(obj)
    return Response(serializer.data, status=status.HTTP_200_OK)

# ========== GENERIC CRUD VIEWS ==========


def create_object(request, serializer_class, extra_fields=None):
    data = request.data.copy()
    if extra_fields:
        data.update(extra_fields)
    serializer = serializer_class(data=data, context={'request': request})  # Add context
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
def get_token_from_oauth(request, username=None, password=None):
    if username is None:
        username = request.POST.get('username') or request.data.get('username')
    if password is None:
        password = request.POST.get('password') or request.data.get('password')

    if not username or not password:
        return Response(
            {'error': 'Username and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    response = requests.post(
        'http://localhost:8000/oauth2/token/',
        data={
            'grant_type': 'password',
            'username': username,
            'password': password,
            'client_id': os.getenv("CLIENT_ID"),
            'client_secret': os.getenv("CLIENT_SECRET"),
        })

    if response.status_code == 200:
        # Add User ID and Username to the response
        user_data = response.json()
        user = User.objects.get(username=username)
        user_data['user_id'] = user.id
        user_data['username'] = username

        return Response(user_data, status=status.HTTP_200_OK)
    else:
        return Response(
            {'error': 'Authentication failed', 'details': response.text},
            status=status.HTTP_401_UNAUTHORIZED
        )


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def trips(request):
    if request.method == 'GET':
        return apply_filter_and_respond(Trip, TripFilter, TripSerializer, request)
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
    return create_object(request, VehicleSerializer, {'driver': request.user.id})


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
def users(request):
    if request.method == 'GET':
        return apply_filter_and_respond(User, UserFilter, UserSerializer, request)
    return create_object(request, UserSerializer)


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
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def driver_profiles(request):
    if request.method == 'GET':
        return apply_filter_and_respond(DriverProfile, DriverProfileFilter, DriverProfileSerializer, request)
    return create_object(request, DriverProfileSerializer, {'user': request.user.id})


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
    return create_object(request, BookingCreateSerializer, {'passenger': request.user.id})


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def booking_details(request, id):
    if request.method == 'GET':
        return get_and_respond(Booking, id, BookingSerializer)
    elif request.method == 'PATCH':
        return update_object(request, Booking, id, BookingSerializer)
    return delete_object(Booking, id)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def chat_threads(request):
    if request.method == 'GET':
        return apply_filter_and_respond(ChatThread, ChatThreadFilter, ChatThreadSerializer, request)
    return create_object(request, ChatThreadSerializer)


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
    return create_object(request, ChatMessageSerializer, {'sender': request.user.id})


@csrf_exempt
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def chat_message_details(request, id):
    if request.method == 'GET':
        return get_and_respond(ChatMessage, id, ChatMessageSerializer)
    elif request.method == 'PATCH':
        return update_object(request, ChatMessage, id, ChatMessageSerializer)
    return delete_object(ChatMessage, id)
