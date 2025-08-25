from accounts.models import CUSTOMER, NoUserOtp, User, UserOtp, UserProfile
from accounts.serializers import (
    UserCreationSerializer,
    UserDetailSerializer,
)
from django.db.utils import IntegrityError
from django.core.cache import cache
from .utils import OTP_LOGIN, OTP_VERIFY_PHONE
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import send_otp
from .serializers import RoleTokenRefreshSeriaizer, UserProfileCreationSerializer
from rest_framework import permissions
from rest_framework import generics
from rest_framework import views, viewsets
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView
from marketplace.utils import r

"""Account API Views"""


class RegisterUser(generics.CreateAPIView):
    serializer_class = UserCreationSerializer
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        # sending the otp by email
        send_otp(self.request, user, typ=1)


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
            # if user already exists with this phone number
            user = User.objects.get(phone_number=phone_number)
            send_otp(user=user, typ=OTP_LOGIN)
            return Response(
                {"type": "existing_user", "message": "otp_sent"},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            # new user
            send_otp(typ=OTP_VERIFY_PHONE, phone_number=phone_number)
            return Response(
                {"type": "new_user", "message": "otp_sent"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            print(e.args, e, "exception in patc of logi")
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
                tries = r.get(f"user:{phone_number}:tries")
                r.incrby(f"user:{phone_number}:tries", 1)
                if tries and int(tries) > 3:
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
                refresh = RefreshToken.for_user(user)
                saved_otp.delete()
                r.delete(f"user:{phone_number}:tries")

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
            # ----------------- creating user account + sending tokens
            # verifying otp
            try:
                tries = r.get(f"user:{phone_number}:tries")
                r.incrby(f"user:{phone_number}:tries", 1)

                if tries and int(tries) > 3:
                    return Response(
                        {"detail": "max_attempts_reached"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                saved_otp = NoUserOtp.objects.get(otp=otp)
                if saved_otp.is_expired() or saved_otp.phone_number != phone_number:
                    return Response(
                        {"detail": "invalid_otp"}, status=status.HTTP_403_FORBIDDEN
                    )

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
                # creating user
                # validating data
                ser = UserCreationSerializer(
                    data={"phone_number": phone_number, "full_name": full_name}
                )
                ser.is_valid(raise_exception=True)
                user = User(
                    phone_number=phone_number, is_active=True, full_name=full_name
                )
                # creating profile
                user.role = CUSTOMER
                user.save()
                # removing otp
                ser = UserProfileCreationSerializer(data=new_user_data)
                ser.is_valid(raise_exception=True)
                profile = ser.save(user=user)
                r.delete(f"user:{phone_number}:tries")
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
