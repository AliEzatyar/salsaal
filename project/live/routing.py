from django.urls import re_path
from .consumers import  LocationConsumer, NotificationConsumer


websocket_urlpatterns = [
    re_path(
        r"ws/notf/(?P<track_id>[\w-]+)/(?P<id>\d+)/$", NotificationConsumer.as_asgi()
    ),
    re_path(r"ws/track/(?P<track_id>\d+)/$", LocationConsumer.as_asgi()),
]
