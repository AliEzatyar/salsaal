from django.conf import settings
from django.http import HttpResponse
from accounts.models import (
    ADMIN,
    CUSTOMER,
    OTP_RETRY_DELAY,
    REST,
    VENDOR_OTP_RETRY_DELAY,
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
from .utils import generate_otp, get_user_otp_tries_key
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import send_otp
from .serializers import (
    RewardSerializer,
    RoleTokenRefreshSeriaizer,
    UserProfileCreationSerializer,
)
from rest_framework import permissions
from rest_framework import views, viewsets
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView
from marketplace.utils import r
from django.db.transaction import atomic
from logging import getLogger
"""Account API Views"""

AUTO_LOGIN_NUMBERS = [
    "+93733333333",  # customer
    "+93722222222",  # delivery
    "+93711111111" # vendor
]


logger = getLogger(__name__)


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
               checks role consistency for existing users.
               
      - POST: verify OTP. typ="existing_user" issues JWTs after updating token_valid_after.
              typ="new_user" validates user_data, creates User/profile (role=CUSTOMER),
              
    Notes:
      - Uses send_otp Celery task and RefreshToken.for_user to issue tokens.
      - Returns standard 200/400/403/404/409/501 responses for the described cases.
    """

    permission_classes = [permissions.AllowAny]

    def patch(self, *args, **kwargs):
        """
        1. if existing user, sends otp for login
        2. if new user, just says new user
        3. prevents multiple otp requests by redis key
        4. throttles vendor otp requests to 3 per 15 minutes
        5. throttles normal user otp requests to 5 per 5 minutes
        """
        data = self.request.data
        phone_number = data.get("phone_number", None)
        role = data.get("role", None)
        if not phone_number or not role:
            return Response(
                {"detail": "provide_phone_number"}, status=status.HTTP_400_BAD_REQUEST
            )
        if len(str(phone_number)) > 12:
            return Response(
                {"detail": "invalid_phone_number"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            # -------- if existing user, send otp for login
            role = int(role)
            user = User.objects.get(phone_number=phone_number)
            if role != user.role:
                return Response(status=status.HTTP_409_CONFLICT)
            otp = generate_otp()
            send_otp.delay(otp=otp, user_id=user.id, phone_number=phone_number)
            return Response(
                {"type": "existing_user", "message": "otp_sent"},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            # -------- if its a new user, just say new user
            return Response(
                {"type": "new_user", "message": "otp_sent"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Exception in login: {e}")    
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    def post(self, *args, **kwargs):
        """
            this method issues token for existing users after verifying otp
            or creates new user account but does not verify otp and issue tokens for new users 
            for new users, otp verification is done in a separate view called VerifyOtpSignUpApiView
            for new users, otp is created and sent
            *** marking user as active is for existing users, for new users is_active False until otp verified by VerifyOtpSignUpApiView
        """
        data = self.request.data
        typ = data.get("type", None)
        phone_number = data.get("phone_number", None)
        role = data.get("role", None)

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
                otp = data.get("otp", None)
                if not otp:
                    return Response(
                        {"detail": "provide_otp"}, status=status.HTTP_400_BAD_REQUEST
                    )
                # --------- TEMP autologin APPLE/GOOGLE devs ----------------
                if phone_number in AUTO_LOGIN_NUMBERS:
                    user = User.objects.get(phone_number=phone_number)
                    user.token_valid_after = get_token_valid_after()
                    user.is_active = True
                    user.save()
                    refresh = RefreshToken.for_user(user)
                    return Response(
                        {
                            "access": str(refresh.access_token),
                            "refresh": str(refresh),
                            "id": user.id,
                        },
                        status=status.HTTP_200_OK,
                    )
                # verifying otp
                otp_tries_key = get_user_otp_tries_key(phone_number)
                tries = r.get(otp_tries_key)
                r.incrby(otp_tries_key, 1)
                # --------------------- vendor login throttling
                if role == REST:
                    if tries and int(tries) > 3:
                        logger.warning(f"vendor login attempt failed {phone_number}")
                        r.expire(
                            otp_tries_key, VENDOR_OTP_RETRY_DELAY
                        )  # 15 minutes delay
                        # vendor should request new otp after 15 minutes and retry
                        return Response(
                            {"detail": "max_attempts_reached"},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                if tries and int(tries) > 5:
                    logger.warning(f"max otp attempts reached for existing user login: {phone_number}")

                    r.expire(otp_tries_key, OTP_RETRY_DELAY)  # 5 minutes delay
                    return Response(
                        {"detail": "max_attempts_reached"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                # verifying otp
                saved_otp = UserOtp.objects.filter(otp=otp).first()
                if (
                    saved_otp.is_expired()
                    or saved_otp.user.phone_number != phone_number
                ):
                    return Response(
                        {"detail": "invalid_otp"}, status=status.HTTP_403_FORBIDDEN
                    )
                # finding user
                user = User.objects.get(phone_number=phone_number)
                user.token_valid_after = get_token_valid_after()
                user.is_active = True
                user.save()
                refresh = RefreshToken.for_user(user)
                saved_otp.delete()
                r.delete(otp_tries_key)

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
                logger.error(f"Exception in login: {e}")    
                return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

        elif typ == "new_user":
            # ----------------- creating user account
            try:
                with atomic():
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
                    try:
                        user_ser.is_valid(raise_exception=True)
                    except Exception as e:
                        return Response(
                            {"detail": "invalid_user_data"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    user = User(phone_number=phone_number, is_active=True, name=name)
                    if role == REST:
                        user.role = REST
                    else:
                        user.role = CUSTOMER
                    user.is_active = False
                    user.token_valid_after = get_token_valid_after()
                    user.save()
                    # ------ creating user profile
                    profile_ser = UserProfileCreationSerializer(data=new_user_data)
                    profile_ser.is_valid(raise_exception=True)
                    profile_ser.save(user=user)
                    # ------ sending otp
                    otp = generate_otp()
                    NoUserOtp.objects.create(phone_number=phone_number, otp=otp)
                    send_otp.delay(otp=otp, user_id=user.id, phone_number=phone_number)
                    return Response(
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


class VerifyOtpSignUpApiView(views.APIView):
    """
    This view verifies OTPs for new user sign-ups.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, *args, **kwargs):
        data = self.request.data
        otp = data.get("otp", None)
        phone_number = data.get("phone_number", None)
        if not otp:
            return Response(
                {"detail": "provide_otp"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not phone_number:
            return Response(
                {"detail": "provide_phone_number"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # ----- preventing auto retries
            otp_tries_key = get_user_otp_tries_key(phone_number)
            tries = r.get(otp_tries_key)
            r.incrby(otp_tries_key, 1)
            if tries and int(tries) > 5:
                r.expire(otp_tries_key, OTP_RETRY_DELAY)  # 5 minutes delay
                logger.warning(f"max otp attempts reached for new user login: {phone_number}")
                return Response(
                    {"detail": "max_attempts_reached"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # ----- verifying otp
            saved_otp = NoUserOtp.objects.filter(otp=otp).first()
            if not saved_otp:
                return Response(
                    {"detail": "invalid_otp"}, status=status.HTTP_400_BAD_REQUEST
                )
            if saved_otp.is_expired() or saved_otp.phone_number != phone_number:
                return Response(
                    {"detail": "invalid_otp"}, status=status.HTTP_400_BAD_REQUEST
                )
            
            user = User.objects.filter(phone_number=phone_number).first()
            if user:
                user.is_active = True
                user.token_valid_after = get_token_valid_after()
                user.save()
                saved_otp.delete()
                r.delete(otp_tries_key)
                refresh = RefreshToken.for_user(user)
                return Response(
                    {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh),
                        "id": user.id,
                    }
                )
            return Response(
                status=status.HTTP_404_NOT_FOUND
            )
        except NoUserOtp.DoesNotExist:
            return Response(
                {"detail": "invalid_otp"}, status=status.HTTP_400_BAD_REQUEST
            )


class DeleteAccountView(views.APIView):
    """only normal users can delete account"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role not in [REST, ADMIN]:
            tokens = OutstandingToken.objects.filter(user=user)
            for token in tokens:
                BlacklistedToken.objects.get_or_create(token=token)
            logger.warning(f"user {user.phone_number} account deletion prompted")
            return Response(status=status.HTTP_200_OK)
        # just logout vendor or admin
        user.token_valid_after = get_token_valid_after() # 5 seconds before 
        user.save()
        return Response(status=status.HTTP_200_OK)


class SignoutApiView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self,request,*args, **kwargs):
        user = request.user
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)
        user.token_valid_after = get_token_valid_after()
        # deleting device tokens to prevent fcm tokens
        user.devices.all().delete() 
        user.save()
        return Response()


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

        # Import Device model here to avoid circular import issues
        from .models import Device
        
        if request.user.role != REST:
            Device.objects.filter(user=request.user).delete()  # delete old devices for non-REST users


        try:
            # preventing duplicate device tokens
            # if a device with this token already exists, reassign it to this user
            # this is to handle cases where user logs in from multiple devices
            devices_with_this_token = Device.objects.filter(token=new_token) 
            if devices_with_this_token.exists():
                devices_with_this_token.update(user=request.user)  # reassign existing device to this user
                return Response(status=status.HTTP_200_OK)
            with atomic():
                # justing keeping last 3 devices for vendor users
                devices_count = Device.objects.filter(user=request.user).count()
                if devices_count > 2:
                    Device.objects.filter(user=request.user).first().delete()
                    
                Device.objects.create(user=request.user, token=new_token)
        except Exception as e:
            logger.error(f"Error in upsert device token: {e}")
            # token creation raced with another request; try to fetch and reassign
            try:
                device = Device.objects.get(token=new_token)
                device.user = request.user
                device.save()
                return Response(status=status.HTTP_200_OK)
            except Device.DoesNotExist:
                logger.error("Device does not exist after exception")
                return Response(status=status.HTTP_400_BAD_REQUEST)
        
        return Response(status=status.HTTP_201_CREATED)


class ResendOtpApiView(views.APIView):
    """
        users can resend otp 3 times per 10 minutes
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self,*args, **kwargs):
        data = self.request.data
        phone_number = data.get("phone_number", None)
        typ = data.get("type", None)
        new_otp = generate_otp()
        if not phone_number or not typ:
            return Response(
                {"detail": "provide_phone_number_and_type"}, status=status.HTTP_400_BAD_REQUEST
            )
        # preventing multiple resend by redis
        resend_key = f"resend_otp_{phone_number}"
        send_times = r.get(resend_key)
        if send_times and int(send_times) >= 3:
            return Response(
                {"detail": "max_resend_attempts_reached"}, status=status.HTTP_403_FORBIDDEN
            )
        r.incrby(resend_key,1)
        r.expire(resend_key,600) # key expires in 10 minutes
            
        if typ == "new_user":
            # delete old otp entries
            send_otp.delay(
                otp=new_otp,
                phone_number=phone_number,
                user_id=None,
            )
            
        else:
            try:
                user = User.objects.get(phone_number=phone_number)
                send_otp.delay(
                    otp=new_otp,
                    phone_number=phone_number,
                    user_id=user.id,
                )
            except User.DoesNotExist:
                return Response(
                    {"detail": "no_user_found"}, status=status.HTTP_404_NOT_FOUND
                )
        return Response(status=status.HTTP_200_OK)


def jwtks_view(request):
    """this endpoint returns public key for verifying jwt;
    used in uwsocket server"""
    return HttpResponse(settings.SIMPLE_JWT["VERIFYING_KEY"], content_type="text/plain")
