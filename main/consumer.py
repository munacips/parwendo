import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import UserLocation
from django.contrib.gis.geos import Point

class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join a group (e.g., "tracking_group")
        await self.channel_layer.group_add("tracking", self.channel_name)
        await self.accept()

    async def receive(self, text_data):
        data = json.loads(text_data)
        lat = data['latitude']
        lng = data['longitude']

        # Update the database asynchronously
        await self.update_user_location(lat, lng)

        # Broadcast the new location to anyone watching (like the Admin)
        await self.channel_layer.group_send(
            "tracking",
            {
                "type": "location_update",
                "latitude": lat,
                "longitude": lng,
                "user": self.scope["user"].username
            }
        )

    @database_sync_to_async
    def update_user_location(self, lat, lng):
        point = Point(float(lng), float(lat))
        UserLocation.objects.update_or_create(
            user=self.scope["user"],
            defaults={'location': point}
        )