# main/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Using re_path for flexible websocket naming
    re_path(r'ws/location/$', consumers.LocationConsumer.as_async()),
]