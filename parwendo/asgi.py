import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Import your routing from the 'main' app
import main.routing 

# Ensure this matches the exact path found in your original file
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parwendo.settings.settings')

application = ProtocolTypeRouter({
    # Handles standard HTTP requests (REST API, Admin, etc.)
    "http": get_asgi_application(),
    
    # Handles WebSocket connections (Live Tracking)
    "websocket": AuthMiddlewareStack(
        URLRouter(
            main.routing.websocket_urlpatterns
        )
    ),
})