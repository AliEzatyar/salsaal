from accounts.models import User, UserOtp, UserProfile
from accounts.serializers import (
    UserCreationSerializer,
    UserDetailSerializer,
    UserProfileSerializer,
)
from api.permissions import IsProfileOwner
from .utils import send_otp
from .serializers import RoleTokenObtainPairSerializer, RoleTokenRefreshSeriaizer
from rest_framework import permissions
from rest_framework import generics
from rest_framework import views, viewsets
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
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


# class UserProfileViewset(viewsets.ModelViewSet):
#     serializer_class = UserProfileSerializer
#     permission_classes = [permissions.IsAuthenticated, IsProfileOwner]
#     # http_method_names = ["patch","get"]

#     def destroy(self, request, *args, **kwargs):
#         return Response({"error": "user profile deletion not allowed"})

#     def create(self, request, *args, **kwargs):
#         return Response({"error": "user profile creation not allowed"})

#     def get_object(self):
#         """only user's profile"""
#         if hasattr(self.request.user, "profile"):
#             return self.request.user.profile
#         return super().get_object()

#     def get_queryset(self):
#         """overriding to prevent others from accessing another profile"""
#         return UserProfile.objects.filter(user=self.request.user)


class VerifyActivateAccountOTP(views.APIView):

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        otp_input = request.data.get("otp")
        try:
            user = User.objects.get(email=email)
            user_otp = UserOtp.objects.get(user=user)

            if user_otp.is_expired():
                user_otp.delete()  # Optional: cleanup expired OTP
                return Response({"error": "OTP has expired"}, status=400)
            if user_otp.otp == str(otp_input):
                user.is_active = True
                user.save()
                user_otp.delete()
                return Response(
                    {"message": "Account activated successfully"}, status=200
                )
            else:
                return Response({"error": "Invalid OTP"}, status=400)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)
        except UserOtp.DoesNotExist:
            return Response({"error": "OTP not found"}, status=404)


class ResendActivationOTP(views.APIView):

    permission_classes = [permissions.AllowAny]

    def post(self, *args, **kwargs):
        email = self.request.data.get("email", None)
        if not email:
            return Response(
                {"error": "provide_an_email"}, status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"error": "user_not_found"}, status=status.HTTP_404_NOT_FOUND
            ) 

        send_otp(self.request, user)
        return Response({"message": "otp_sent"}, status=status.HTTP_200_OK)


class ForgotPassword(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, *args, **kwargs):
        email = self.request.data.get("email")
        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"error": "no_account_registered_with_this_email"},
                status=status.HTTP_404_NOT_FOUND,
            )

        send_otp(self.request, user, typ=2)
        return Response({"message": "otp_sent"}, status=status.HTTP_200_OK)


class VerifyForgotPasswordOTP(views.APIView):

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        otp_input = request.data.get("otp")
        try:
            user = User.objects.get(email=email)
            user_otp = UserOtp.objects.get(user=user)

            if user_otp.is_expired():
                user_otp.delete()  # Optional: cleanup expired OTP
                return Response({"error": "otp_expired"}, status=400)
            if user_otp.otp == str(otp_input):
                return Response({"message": "otp_valid"}, status=200)
            else:
                return Response({"error": "otp_invalid"}, status=400)

        except User.DoesNotExist:
            return Response({"error": "user_not_found"}, status=404)
        except UserOtp.DoesNotExist:
            return Response({"error": "otp_not_found"}, status=404)


class ResetPassword(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, *args, **kwargs):
        email = self.request.data.get("email")
        otp_input = self.request.data.get("otp")

        try:
            user = User.objects.get(email=email)
            user_otp = UserOtp.objects.get(user=user)

            if user_otp.is_expired():
                user_otp.delete()  # Optional: cleanup expired OTP
                return Response({"detail": "OTP_has_expired"}, status=400)

            if user_otp.otp == str(otp_input):
                new_password = self.request.data.get("password", None)
                if not new_password:
                    return Response({"detail": "no_password_entered"}, status=400)
                user_otp.delete()
                user.set_password(new_password)
                user.save()
                return Response(
                    {"message": "password_changed_successfully"}, status=200
                )
            else:
                return Response({"detail": "otp_invalid"}, status=400)

        except User.DoesNotExist:
            return Response({"detail": "user_not_found"}, status=404)
        except UserOtp.DoesNotExist:
            return Response({"detail": "otp_not_found"}, status=404)


class RoleTokenObtainView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer


class RoleTokenRefreshView(TokenRefreshView):
    serializer_class = RoleTokenRefreshSeriaizer
