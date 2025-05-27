from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import User, DriverProfile, Vehicle, Trip, Booking, ChatThread, ChatMessage
from .serializers import UserSerializer, DriverProfileSerializer, VehicleSerializer, TripSerializer, BookingSerializer, ChatThreadSerializer, ChatMessageSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
import django_filters
from rest_framework.pagination import PageNumberPagination

# ========== FILTERS ==========

class TripFilter(django_filters.FilterSet):
    class Meta:
        model = Trip
        fields = ['driver', 'destination', 'start_location']

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
        fields = ['user', 'license_number', 'national_id_number', 'verification_status']

class BookingFilter(django_filters.FilterSet):
    class Meta:
        model = Booking
        fields = ['trip', 'passenger', 'status']

class ChatThreadFilter(django_filters.FilterSet):
    class Meta:
        model = ChatThread
        fields = ['trip', 'passenger', 'driver']

class ChatMessageFilter(django_filters.FilterSet):
    class Meta:
        model = ChatMessage
        fields = ['thread', 'sender']

# ========== UTILS ==========

from rest_framework.pagination import PageNumberPagination

def apply_filter_and_respond(model, filter_class, serializer_class, request):
    filterset = filter_class(request.query_params, queryset=model.objects.all())
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
    serializer = serializer_class(data=data)
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

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def trips(request):
    if request.method == 'GET':
        return apply_filter_and_respond(Trip, TripFilter, TripSerializer, request)
    return create_object(request, TripSerializer, {'driver': request.user.id})

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def trip_details(request, id):
    if request.method == 'GET':
        return get_and_respond(Trip, id, TripSerializer)
    elif request.method == 'PATCH':
        return update_object(request, Trip, id, TripSerializer)
    return delete_object(Trip, id)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def vehicles(request):
    if request.method == 'GET':
        return apply_filter_and_respond(Vehicle, VehicleFilter, VehicleSerializer, request)
    return create_object(request, VehicleSerializer, {'driver': request.user.id})

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def vehicle_details(request, id):
    if request.method == 'GET':
        return get_and_respond(Vehicle, id, VehicleSerializer)
    elif request.method == 'PATCH':
        return update_object(request, Vehicle, id, VehicleSerializer)
    return delete_object(Vehicle, id)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def users(request):
    if request.method == 'GET':
        return apply_filter_and_respond(User, UserFilter, UserSerializer, request)
    return create_object(request, UserSerializer)

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def user_details(request, id):
    if request.method == 'GET':
        return get_and_respond(User, id, UserSerializer)
    elif request.method == 'PATCH':
        return update_object(request, User, id, UserSerializer)
    return delete_object(User, id)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def driver_profiles(request):
    if request.method == 'GET':
        return apply_filter_and_respond(DriverProfile, DriverProfileFilter, DriverProfileSerializer, request)
    return create_object(request, DriverProfileSerializer, {'user': request.user.id})

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def driver_profile_details(request, id):
    if request.method == 'GET':
        return get_and_respond(DriverProfile, id, DriverProfileSerializer)
    elif request.method == 'PATCH':
        return update_object(request, DriverProfile, id, DriverProfileSerializer)
    return delete_object(DriverProfile, id)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def bookings(request):
    if request.method == 'GET':
        return apply_filter_and_respond(Booking, BookingFilter, BookingSerializer, request)
    return create_object(request, BookingSerializer, {'passenger': request.user.id})

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def booking_details(request, id):
    if request.method == 'GET':
        return get_and_respond(Booking, id, BookingSerializer)
    elif request.method == 'PATCH':
        return update_object(request, Booking, id, BookingSerializer)
    return delete_object(Booking, id)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def chat_threads(request):
    if request.method == 'GET':
        return apply_filter_and_respond(ChatThread, ChatThreadFilter, ChatThreadSerializer, request)
    return create_object(request, ChatThreadSerializer)

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def chat_thread_details(request, id):
    if request.method == 'GET':
        return get_and_respond(ChatThread, id, ChatThreadSerializer)
    elif request.method == 'PATCH':
        return update_object(request, ChatThread, id, ChatThreadSerializer)
    return delete_object(ChatThread, id)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def chat_messages(request):
    if request.method == 'GET':
        return apply_filter_and_respond(ChatMessage, ChatMessageFilter, ChatMessageSerializer, request)
    return create_object(request, ChatMessageSerializer, {'sender': request.user.id})

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def chat_message_details(request, id):
    if request.method == 'GET':
        return get_and_respond(ChatMessage, id, ChatMessageSerializer)
    elif request.method == 'PATCH':
        return update_object(request, ChatMessage, id, ChatMessageSerializer)
    return delete_object(ChatMessage, id)
