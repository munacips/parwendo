from . import views
from django.urls import path


urlpatterns = [
    path('verify_otp/', views.verify_otp, name='verify_otp'),
    path('get_token_from_oauth/', views.get_token_from_oauth,
         name='get_token_from_oauth'),
    path('trips/', views.trips, name='trips'),
    path('trips/<int:id>/', views.trip_details, name='trip_details'),
    path('vehicles/', views.vehicles, name='vehicles'),
    path('vehicles/<int:id>/', views.vehicle_details, name='vehicle_details'),
    path('bookings/', views.bookings, name='bookings'),
    path('bookings/<int:id>/', views.booking_details, name='booking_details'),
    path('drivers/', views.driver_profiles, name='drivers'),
    path('drivers/<int:id>/', views.driver_profile_details, name='driver_details'),
    path('chat/threads/', views.chat_threads, name='chat_threads'),
    path('chat/threads/<int:id>/', views.chat_thread_details,
         name='chat_thread_details'),
    path('chat/messages/', views.chat_messages, name='chat_messages'),
    path('chat/messages/<int:id>/', views.chat_message_details,
         name='chat_message_details'),
    path('users/', views.users, name='users'),
    path('users/<int:id>/', views.user_details, name='user_details'),
    path('users/<int:id>/statistics/',
         views.users_statistics, name='user_statistics'),
    path('user_reports/', views.user_reports, name='user_reports'),
    path('user_reports/<int:id>/', views.user_report_details,
         name='user_report_details'),
    path('resend_otp/', views.resend_otp, name='resend_otp'),
    path('register_fcm_token/', views.register_fcm_token, name='register_fcm_token'),
]
