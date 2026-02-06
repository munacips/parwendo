import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import UserLocation

class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join a group (e.g., "tracking_group")
        await self.channel_layer.group_add("tracking", self.channel_name)
        await self.accept()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            
            # Validate required fields
            if 'latitude' not in data or 'longitude' not in data:
                await self.send(text_data=json.dumps({
                    'error': 'Missing required fields: latitude and longitude'
                }))
                return
            
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
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e)
            }))

    @database_sync_to_async
    def update_user_location(self, lat, lng):
        UserLocation.objects.update_or_create(
            user=self.scope["user"],
            defaults={'latitude': float(lat), 'longitude': float(lng)}
        )