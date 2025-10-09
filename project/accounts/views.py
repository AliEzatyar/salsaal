from django.conf import settings
from django.http import HttpResponse
from accounts.models import CUSTOMER, OTP_RETRY_DELAY, NoUserOtp, User, UserOtp
from accounts.serializers import (
    UserCreationSerializer,
    UserDetailSerializer,
)
from django.db.utils import IntegrityError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from order.models import Reward
from .utils import OTP_LOGIN, OTP_VERIFY_PHONE, generate_otp, get_user_otp_tries_key
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import send_otp
from .serializers import (
    DeviceSerializer,
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
    permission_classes = [permissions.AllowAny]

    def patch(self, *args, **kwargs):
        data = self.request.data
        phone_number = data.get("phone_number", None)

        if not phone_number:
            return Response(
                {"detail": "provide_phone_number"}, status=status.HTTP_400_BAD_REQUEST
            )
        if len(str(phone_number)) > 12:
            return Response(
                {"detail": "invalid_phone_number"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            # ------- if user already exists with this phone number
            user = User.objects.get(phone_number=phone_number)
            otp = generate_otp()
            send_otp.delay(otp=otp,user_id=user.id, typ=OTP_LOGIN)
            return Response(
                {"type": "existing_user", "message": "otp_sent"},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            # -------- if its a new user
            otp = generate_otp()
            send_otp.delay(otp,typ=OTP_VERIFY_PHONE, phone_number=phone_number)
            return Response(
                {"type": "new_user", "message": "otp_sent"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            print(e.args, e, "exception in login")
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
                otp_tries_key = get_user_otp_tries_key(phone_number)
                tries = r.get(otp_tries_key)
                r.incrby(otp_tries_key, 1)
                if tries and int(tries) > 5:
                    r.expire(otp_tries_key, OTP_RETRY_DELAY)  # 10 minutes delay
                    return Response(
                        {"detail": "max_attempts_reached"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                saved_otp = UserOtp.objects.get(otp=otp)
                if (
                    saved_otp.is_expired()
                    or saved_otp.user.phone_number != phone_number
                ):
                    return Response(
                        {"detail": "invalid_otp"}, status=status.HTTP_403_FORBIDDEN
                    )
                # finding user
                user = User.objects.get(phone_number=phone_number)
                user.token_valid_after = timezone.now() - timedelta(seconds=10)
                user.save()
                refresh = RefreshToken.for_user(user)
                saved_otp.delete()
                r.delete(otp_tries_key)

                return Response(
                    {"access": str(refresh.access_token), "refresh": str(refresh)},
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
                print("error in login", e, e.args)
                return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

        elif typ == "new_user":
            # ----------------- creating user account
            try:
                # ----- preventing auto retries
                otp_tries_key = get_user_otp_tries_key(phone_number)
                tries = r.get(otp_tries_key)
                r.incrby(otp_tries_key, 1)
                if tries and int(tries) > 5:
                    r.expire(otp_tries_key, OTP_RETRY_DELAY)  #
                    return Response(
                        {"detail": "max_attempts_reached"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                # ----- verifying otp
                saved_otp = NoUserOtp.objects.get(otp=otp)
                if saved_otp.is_expired() or saved_otp.phone_number != phone_number:
                    return Response(
                        {"detail": "invalid_otp"}, status=status.HTTP_403_FORBIDDEN
                    )

                # ----- validating user data and creating new account
                new_user_data = data.get("user_data", None)
                if not new_user_data:
                    return Response(
                        {"detail": "provide_user_data"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                full_name = new_user_data.get("full_name", None)
                if not full_name:
                    return Response(
                        {"detail": "provide_full_name"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # serializing data for validation only not creation
                ser = UserCreationSerializer(
                    data={"phone_number": phone_number, "full_name": full_name}
                )
                ser.is_valid(raise_exception=True)
                user = User(
                    phone_number=phone_number, is_active=True, full_name=full_name
                )
                user.role = CUSTOMER
                user.save()
                # ------ creating user profile
                ser = UserProfileCreationSerializer(data=new_user_data)
                ser.is_valid(raise_exception=True)
                # ------ removing otp and generating access token for new user
                r.delete(otp_tries_key)
                saved_otp.delete()
                refresh = RefreshToken.for_user(user)
                return Response(
                    {"access": str(refresh.access_token), "refresh": str(refresh)},
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


class RoleTokenRefreshView(TokenRefreshView):
    serializer_class = RoleTokenRefreshSeriaizer


class UpsertDeviceToken(views.APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        if request.user.devices:
            ser = DeviceSerializer(request.user.devices.last(), data=data, partial=True)
        else:
            ser = DeviceSerializer(data)
        if ser.is_valid(raise_exception=True):
            ser.validated_data["user"] = request.user
            print("saving user device...")
            ser.save()
        return Response()


def jwtks_view(request):
    return HttpResponse(settings.SIMPLE_JWT["VERIFYING_KEY"], content_type="text/plain")
