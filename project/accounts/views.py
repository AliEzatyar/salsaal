from accounts.models import User, UserOtp
from accounts.serializers import (
    UserCreationSerializer,
    UserDetailSerializer,
)
from .utils import OTP_LOGIN
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import send_otp
from .serializers import RoleTokenRefreshSeriaizer
from rest_framework import permissions
from rest_framework import generics
from rest_framework import views, viewsets
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView

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


class VerifyActivateAccountOTP(views.APIView):
    """sign up-after otp verification"""
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        phone_number = request.data.get("phone_number")
        otp_input = request.data.get("otp")
        try:
            user = User.objects.get(phone_number=phone_number)
            # last otp
            user_otp = UserOtp.objects.filter(user=user).order_by("-created_at").first()

            if user_otp.is_expired():
                user_otp.delete()  # Optional: cleanup expired OTP
                return Response({"detail": "otp_expired"}, status=400)
            if user_otp.otp == str(otp_input):
                user.is_active = True
                user.save()
                user_otp.delete()
                # sending access and refresh tokens
                refresh = RefreshToken.for_user(user)
                return Response(
                    {
                        "message": "account_activated",
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                    status=200,
                )
            else:
                return Response({"detail": "invalid_otp"}, status=400)

        except User.DoesNotExist:
            return Response({"detail": "user_not_found"}, status=404)
        except UserOtp.DoesNotExist:
            return Response({"detail": "otp_not_found"}, status=404)
        except:
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class ResendActivationOTP(views.APIView):

    permission_classes = [permissions.AllowAny]

    def post(self, *args, **kwargs):
        phone_number = self.request.data.get("phone_number", None)
        if not phone_number:
            return Response(
                {"error": "provide_phone_number"}, status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(phone_number=phone_number).first()
        if not user:
            return Response(
                {"error": "user_not_found"}, status=status.HTTP_404_NOT_FOUND
            )

        send_otp(self.request, user)
        return Response({"message": "otp_sent"}, status=status.HTTP_200_OK)


class RoleTokenObtainView(views.APIView):
    """login"""
    permission_classes = [permissions.AllowAny]

    def patch(self,*args, **kwargs):
        """sends otp"""
        data = self.request.data
        phone_number = data.get("phone_number")
        if not phone_number:
            return Response({"detail":"provide_phone_number"},status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(phone_number=phone_number)
            send_otp(self.request,user,OTP_LOGIN)
            return Response({"message":"otp_sent"})
        except User.DoesNotExist():
            return Response(
                {"detail": "user_not_found"}, status=status.HTTP_404_NOT_FOUND
            )

    def post(self, *args, **kwargs):
        """verifies otp and signs user in"""
        try:
            data = self.request.data
            phone_number = data.get("phone_number")
            code = data.get("otp")
            user = User.objects.get(phone_number=phone_number)
            otp_obj = UserOtp.objects.filter(user=user).order_by("-created_at").first()
            okay = True
            if not otp_obj:
                print("no otp")
                okay = False
            elif otp_obj.is_expired():
                print("expired")

                otp_obj.delete()
                okay = False
            elif otp_obj.otp != str(code):
                print("incorrect")
                okay = False
            if not okay:
                return Response(
                    {"detail": "authentication_failed"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Generate JWT token manually
            refresh = RefreshToken.for_user(user)
            otp_obj.delete()
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "rule": user.role
                }
            )
        except Exception as e:
            print("problems in ace",e,e.args)
            return Response(
                {"detail": "authentication_failed"}, status=status.HTTP_403_FORBIDDEN
            )


class RoleTokenRefreshView(TokenRefreshView):
    serializer_class = RoleTokenRefreshSeriaizer
