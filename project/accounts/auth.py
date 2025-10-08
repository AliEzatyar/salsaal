# users/authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from datetime import timezone


class CustomJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        token_iat = validated_token.get("iat")
        if token_iat is None:
            raise AuthenticationFailed("Token missing 'iat' claim")

        # Compare token issue time with user.token_valid_after
        from datetime import datetime
        # converting user's token issued at to utc
        token_iat_dt = datetime.fromtimestamp(token_iat, tz=timezone.utc)
        if token_iat_dt < user.token_valid_after:
            raise AuthenticationFailed("Token has been invalidated")

        return user
