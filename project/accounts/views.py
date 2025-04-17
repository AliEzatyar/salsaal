from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from accounts.models import User, UserOtp
from accounts.forms import UserProfileForm, UserEditForm
from accounts.serializers import UserCreationSerializer, UserDetailSerializer
from .utils import send_otp

from rest_framework import permissions
from rest_framework import generics
from rest_framework import views
from rest_framework import status
from rest_framework.response import Response


"""Account API Views"""


class RegisterUser(generics.CreateAPIView):
    serializer_class = UserCreationSerializer
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        # sending the otp by email
        send_otp(self.request, user, typ=1)


class UpdateDeleteRetriveUser(generics.RetrieveUpdateDestroyAPIView):
    """
    it works with 4 methods:
    GET --> retrieve user data
    PUT --> update user
    DELETE> delete the user account itself
    NOTE: this view uses default authentication class which need JWT-token
    for every request
    """

    serializer_class = UserDetailSerializer
    queryset = User.objects.all()

    def get_object(self):
        """this ensures that only the user itself works on its account"""
        return self.request.user


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
                {"error": "no email address"}, status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        send_otp(self.request, user)
        return Response({"message": "OTP sent"}, status=status.HTTP_200_OK)


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
                return Response({"error": "OTP has expired"}, status=400)
            if user_otp.otp == str(otp_input):
                return Response({"message": "Correct Forgot password OTP "}, status=200)
            else:
                return Response({"error": "Invalid OTP"}, status=400)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)
        except UserOtp.DoesNotExist:
            return Response({"error": "OTP not found"}, status=404)


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
                return Response({"error": "OTP has expired"}, status=400)

            if user_otp.otp == str(otp_input):
                new_password = self.request.data.get("password", None)
                if not new_password:
                    return Response({"error": "no password entered"}, status=400)
                user_otp.delete()
                user.set_password(new_password)
                user.save()
                return Response(
                    {"message": "password changed successfully"}, status=200
                )
            else:
                return Response({"error": "Invalid OTP"}, status=400)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)
        except UserOtp.DoesNotExist:
            return Response({"error": "OTP not found"}, status=404)


# utility funciton
def customer_tester(user):
    if user.role != 2:
        raise PermissionDenied
    return True


@login_required
def dashboard(request):
    if request.user.is_admin:
        return redirect("/admin")
    elif request.user.get_role() == "Customer":
        return redirect("accounts:profile")
    elif request.user.get_role() == "Shop":
        return redirect("vendor:vendor_dashboard")


@login_required
def account_settings(request):
    """this view enables a user to update its account"""
    form = UserEditForm(instance=request.user)
    if request.method == "POST":
        form = UserEditForm(instance=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "تغییرات ثبت شد.")
        else:
            messages.error(request,"مشکلی رخ داد!")
    return render(request, "accounts/account_settings.html", context=locals())


@login_required
@user_passes_test(customer_tester)
def profile(request):
    profile = request.user.profile
    profile_form = UserProfileForm(instance=profile)
    if request.method == "POST":
        profile_form = UserProfileForm(
            instance=profile, data=request.POST, files=request.FILES
        )
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "پروفایل شما آپدیت شد.")
        else:
            messages.error(request, "مشکلاتی در ثبت تغییرات وجود داشت.")
    return render(request, "customer/customer_profile.html", context=locals())
