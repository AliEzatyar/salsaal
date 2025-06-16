from django.contrib.auth.models import AnonymousUser
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from rest_framework_simplejwt.authentication import JWTAuthentication
from jwt import InvalidTokenError
from urllib.parse import parse_qs


@database_sync_to_async
def get_user(validated_token):
    """verifies the validated token if it is related to a user"""
    try:
        return JWTAuthentication().get_user(validated_token)
    except:
        return AnonymousUser


class JWTAuthMiddleware(BaseMiddleware):

    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope['query_string'].decode())
        token = query_string.get("token")
        if token:
            try:
                validated_token = JWTAuthentication().get_validated_token(token[0])
                scope['user'] = await get_user(validated_token)
            except InvalidTokenError:
                scope['user'] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()
        return await super().__call__(scope,receive,send)