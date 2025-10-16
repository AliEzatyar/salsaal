from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.core.exceptions import PermissionDenied
from .models import CUSTOMER, NoUserOtp, User, UserOtp
from celery import shared_task
import random


def send_log_email(amount, type_=None):
    if type_ == "db":
        mail = EmailMessage(
            subject="Time token for db..", to=["aliahmadyar10@gmail.com"], body=amount
        )
    else:
        mail = EmailMessage(
            subject="total server Time token..",
            to=["aliahmadyar10@gmail.com"],
            body=amount,
        )
    mail.send()


def generate_otp(length=6):
    if length == 8:
        return random.randint(10000000, 99999999)
    return random.randint(100000, 999999)


OTP_VERIFY_PHONE = 1
OTP_FORGOT_PASSWORD = 2
OTP_VERIFY_CARRIER = 3
OTP_LOGIN = 4


@shared_task(bind=True, max_retries=5, default_retry_delay=10)
def send_otp(self, otp=None, user_id=None, phone_number=None, typ=OTP_VERIFY_PHONE, **kwargs):
    """
    sends otp using email
    """
    try:
        if not user_id:
            # no-user otp for sign up
            if not phone_number:
                return "no phone number provided for sending otp"

            # deleting previous
            NoUserOtp.objects.filter(phone_number=phone_number).delete()
            # creating new one
            NoUserOtp.objects.create(otp=otp, phone_number=phone_number)
            mail_body = render_to_string(
                "accounts/emails/account_verification.html",
                {"otp": otp},
            )

        else:
            do = "activate your account"
            question = ""

            if typ == OTP_FORGOT_PASSWORD:
                # forgot password
                do = "reset your password"
            elif typ == OTP_VERIFY_CARRIER:
                # verify carrier
                do = "add your account to carriers list"
                question = f"Are you working in {kwargs['vendor_name']}, if yes,"
            elif typ == OTP_LOGIN:
                do = "login to your account"
            mail_body = render_to_string(
                "accounts/emails/account_verification.html",
                {"user": user_id, "question": question, "otp": otp, "do": do},
            )
            # removing previous otp if existing
            user = User.objects.get(id=user_id)
            UserOtp.objects.filter(user__id=user_id).delete()
            # creating new otp
            UserOtp.objects.create(user=user, otp=otp)
        mail = EmailMessage(
            subject="HI",
            to=["tareeqshah5@gmail.com", "wahidiali859@gmail.com"],
            body=mail_body,
        )
        mail.send()
        return "OTP sending successful!"
    except Exception as e:
        # retry after 10 seconds
        delay = min(60 * 2 ** self.request.retries, 3600)
        raise self.retry(exc=e, countdown=delay)

def send_forgot_email(request, user, template=None):
    current_site = get_current_site(request)
    mail_title = "Reset Your Password"
    mail_body = render_to_string(
        "accounts/emails/reset_password.html",
        {
            "user": user,
            "domain": current_site,
            "uid": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": default_token_generator.make_token(user),
        },
    )
    mail_to = user.email
    mail = EmailMessage(subject=mail_title, to=[mail_to], body=mail_body)
    mail.send()


def send_notification(receiver, mail_title, mail_template: str, context: dict):
    mail_body = render_to_string(mail_template, context)
    mail_to = receiver
    mail = EmailMessage(subject=mail_title, to=[mail_to], body=mail_body)
    mail.send()


def user_test(user):
    if user.role != CUSTOMER:
        raise PermissionDenied
    return True


def get_user_otp_tries_key(phone_number):
    return f"user:{phone_number}:tries"
