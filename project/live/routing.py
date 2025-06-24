from django.urls import re_path
from .consumers import Consumer


websocket_urlpatterns = [
    re_path(r"ws/notf/(?P<for>[\w-]+)/(?P<id>\d+)/$", Consumer.as_asgi()),
]
