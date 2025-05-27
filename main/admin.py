from django.contrib import admin
from .models import User, DriverProfile, Vehicle, Trip, Booking, ChatThread, ChatMessage

admin.site.register([User, DriverProfile, Vehicle, Trip, Booking, ChatThread, ChatMessage])