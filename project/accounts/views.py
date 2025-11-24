from django.conf import settings
from django.http import HttpResponse
from accounts.models import (
    CUSTOMER,
    OTP_RETRY_DELAY,
    NoUserOtp,
    User,
    UserOtp,
    get_token_valid_after,
)
from accounts.serializers import (
    UserCreationSerializer,
    UserDetailSerializer,
)
from django.db.utils import IntegrityError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from order.models import Reward
from .utils import OTP_LOGIN, OTP_VERIFY_PHONE, generate_otp, get_user_otp_tries_key
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import send_otp
from .serializers import (
    RewardSerializer,
    RoleTokenRefreshSeriaizer,
    UserProfileCreationSerializer,
)
from rest_framework import permissions
from rest_framework import generics
from rest_framework import views, viewsets
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView
from marketplace.utils import r
from django.utils import timezone
from datetime import timedelta
from django.db.transaction import atomic

"""Account API Views"""


class UserViewset(viewsets.ModelViewSet):
    """
    it works with 4 methods:
    GET --> retrieve user data including user profile
    PUT --> update user and profile
    DELETE> delete the user account and profile
    """

    http_method_names = ["get", "delete", "patch", "put"]
    serializer_class = UserDetailSerializer

    def get_object(self):
        """this ensures that only the user itself works on its account"""
        return self.request.user

    def get_queryset(self):
        """limiting queryset to only  one instance"""
        new_qs = User.objects.filter(id=self.request.user.id)
        return new_qs


class UserRewardsViewset(viewsets.ReadOnlyModelViewSet):
    """this view lists user's rewards"""

    serializer_class = RewardSerializer

    def get_queryset(self):
        qs = Reward.objects.filter(user=self.request.user)
        return qs


class LoginApiView(views.APIView):
    """
    LoginApiView
    Handles two-step OTP login/registration.

    Methods:
      - PATCH: request OTP for phone_number. Sends OTP for existing users (OTP_LOGIN)
               or for new numbers (OTP_VERIFY_PHONE).
      - POST: verify OTP. typ="existing_user" issues JWTs after updating token_valid_after.
              typ="new_user" validates user_data, creates User/profile (role=CUSTOMER),
              sets token_valid_after and issues JWTs.

    Notes:
      - OTP verification and retry logic exist but are commented out here.
      - Uses send_otp Celery task and RefreshToken.for_user to issue tokens.
      - Returns standard 200/400/403/404/409/501 responses for the described cases.
    """

    permission_classes = [permissions.AllowAny]

    def patch(self, *args, **kwargs):
        data = self.request.data
        phone_number = data.get("phone_number", None)
        role = data.get("role", None)
        print(role, "this was the role")
        if not phone_number or not role:
            return Response(
                {"detail": "provide_phone_number"}, status=status.HTTP_400_BAD_REQUEST
            )
        if len(str(phone_number)) > 12:
            return Response(
                {"detail": "invalid_phone_number"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            role = int(role)

            user = User.objects.get(phone_number=phone_number)
            if role != user.role:
                print("incorrect app", role, user.role)
                return Response(status=status.HTTP_409_CONFLICT)
            otp = generate_otp()
            send_otp.delay(otp=otp, user_id=user.id, typ=OTP_LOGIN)
            return Response(
                {"type": "existing_user", "message": "otp_sent"},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            # -------- if its a new user
            otp = generate_otp()
            send_otp.delay(otp, typ=OTP_VERIFY_PHONE, phone_number=phone_number)
            return Response(
                {"type": "new_user", "message": "otp_sent"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            print("exception in login", e)
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    def post(self, *args, **kwargs):
        data = self.request.data
        typ = data.get("type", None)
        otp = data.get("otp", None)
        phone_number = data.get("phone_number", None)
        if not otp:
            return Response(
                {"detail": "provide_otp"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not typ:
            return Response(
                {"detail": "provide_type"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not phone_number:
            return Response(
                {"detail": "provide_phone_number"}, status=status.HTTP_400_BAD_REQUEST
            )
        # --------------------- start -----------------------------------------------
        if typ == "existing_user":
            # -------------------------------- sending tokens
            try:
                # verifying otp
                # otp_tries_key = get_user_otp_tries_key(phone_number)
                # tries = r.get(otp_tries_key)
                # r.incrby(otp_tries_key, 1)
                # if tries and int(tries) > 5:
                #     r.expire(otp_tries_key, OTP_RETRY_DELAY)  # 10 minutes delay
                #     return Response(
                #         {"detail": "max_attempts_reached"},
                #         status=status.HTTP_403_FORBIDDEN,
                #     )

                # saved_otp = UserOtp.objects.get(otp=otp)
                # if (
                #     saved_otp.is_expired()
                #     or saved_otp.user.phone_number != phone_number
                # ):
                #     return Response(
                #         {"detail": "invalid_otp"}, status=status.HTTP_403_FORBIDDEN
                #     )
                # # finding user
                user = User.objects.get(phone_number=phone_number)
                user.token_valid_after = get_token_valid_after()
                # user.save()
                refresh = RefreshToken.for_user(user)
                # saved_otp.delete()
                # r.delete(otp_tries_key)

                return Response(
                    {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh),
                        "id": user.id,
                    },
                    status=status.HTTP_200_OK,
                )
            except UserOtp.DoesNotExist:
                return Response(
                    {"detail": "invalid_otp"}, status=status.HTTP_403_FORBIDDEN
                )
            except User.DoesNotExist:
                return Response(
                    {"detail": "no_user_found"}, status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                print("exception in login", e, e.args)
                return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

        elif typ == "new_user":
            # ----------------- creating user account
            try:
                with atomic():

                    # ----- preventing auto retries
                    # otp_tries_key = get_user_otp_tries_key(phone_number)
                    # tries = r.get(otp_tries_key)
                    # r.incrby(otp_tries_key, 1)
                    # if tries and int(tries) > 5:
                    #     r.expire(otp_tries_key, OTP_RETRY_DELAY)  #
                    #     return Response(
                    #         {"detail": "max_attempts_reached"},
                    #         status=status.HTTP_403_FORBIDDEN,
                    #     )
                    # # ----- verifying otp
                    # saved_otp = NoUserOtp.objects.get(otp=otp)
                    # if saved_otp.is_expired() or saved_otp.phone_number != phone_number:
                    #     return Response(
                    #         {"detail": "invalid_otp"}, status=status.HTTP_403_FORBIDDEN
                    #     )

                    # ----- validating user data and creating new account
                    new_user_data = data.get("user_data", None)
                    if not new_user_data:
                        return Response(
                            {"detail": "provide_user_data"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    name = new_user_data.get("name", None)
                    if not name:
                        return Response(
                            {"detail": "provide_name"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    # serializing data for validation only, not creation
                    user_ser = UserCreationSerializer(
                        data={"phone_number": phone_number, "name": name}
                    )
                    user_ser.is_valid(raise_exception=True)
                    user = User(phone_number=phone_number, is_active=True, name=name)
                    user.role = CUSTOMER
                    user.token_valid_after = get_token_valid_after()
                    user.save()
                    # ------ creating user profile
                    profile_ser = UserProfileCreationSerializer(data=new_user_data)
                    profile_ser.is_valid(raise_exception=True)
                    profile_ser.save(user=user)
                    # ------ removing otp and generating access token for new user
                    # r.delete(otp_tries_key)
                    # saved_otp.delete()
                    refresh = RefreshToken.for_user(user)
                    return Response(
                        {
                            "access": str(refresh.access_token),
                            "refresh": str(refresh),
                            "id": user.id,
                        },
                        status=status.HTTP_200_OK,
                    )
            except IntegrityError:
                return Response(
                    {"detail": "user_already_exists"},
                    status=status.HTTP_409_CONFLICT,
                )
            except NoUserOtp.DoesNotExist:
                return Response(
                    {"detail": "invalid_otp"}, status=status.HTTP_403_FORBIDDEN
                )
        else:
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class DeleteAccountView(views.APIView):
    
    def get(self, request, *args, **kwargs):
        user = request.user
        # Blacklist all outstanding tokens for the user
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)
        user.delete()
        return Response(status=status.HTTP_200_OK)


class RoleTokenRefreshView(TokenRefreshView):
    serializer_class = RoleTokenRefreshSeriaizer


class UpsertDeviceToken(views.APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        new_token = data.get("token", None)
        # if no token provided, return 400
        if not new_token:
            return Response(
                {"detail": "no_token_provided"}, status=status.HTTP_400_BAD_REQUEST
            )
        # Normalize token
        new_token = str(new_token).strip()

        # Fast-path: if user already has a device with same token, nothing to do
        existing_for_user = request.user.devices.filter(token=new_token).first()
        if existing_for_user:
            return Response(status=status.HTTP_200_OK)

        from .models import Device

        try:
            # If a device with this token exists for another user, reassign it to current user
            device = Device.objects.filter(token=new_token).first()
            if device:
                # reassign owner to current user
                device.user = request.user
                device.save()
                return Response(status=status.HTTP_200_OK)

            # otherwise create a new device for this user
            # wrap in atomic to handle race conditions
            with atomic():
                print("device token saved", new_token)
                Device.objects.create(user=request.user, token=new_token)
        except IntegrityError:
            # token creation raced with another request; try to fetch and reassign
            try:
                device = Device.objects.get(token=new_token)
                device.user = request.user
                device.save()
                return Response(status=status.HTTP_200_OK)
            except Device.DoesNotExist:
                return Response(status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_201_CREATED)


def jwtks_view(request):
    """this endpoint returns public key for verifying jwt;
    used in uwsocket server"""
    return HttpResponse(settings.SIMPLE_JWT["VERIFYING_KEY"], content_type="text/plain")
