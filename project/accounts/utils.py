from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.core.exceptions import PermissionDenied
from .models import CUSTOMER, UserOtp
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


def generate_otp():
    return random.randint(100000, 999999)


def send_otp(request, user, typ=1):
    """
    sends an email to verify the new registered user
    """
    otp = generate_otp()
    mail_title = "Verify You Email"
    do = "activate your account"

    if typ == 2:
        # forgot password
        mail_title = "Forgot Password"
        do = "reset your password"
    mail_body = render_to_string(
        "accounts/emails/account_verification.html",
        {"user": user, "otp": otp, "do": do},
    )
    # removing previous otp if existing
    pre_otp = UserOtp.objects.filter(user=user).first()
    if pre_otp:
        pre_otp.delete()
    
    # creating new otp
    UserOtp.objects.create(user=user, otp=otp)
    mail_to = user.email
    mail = EmailMessage(subject=mail_title, to=[mail_to], body=mail_body)
    mail.send()


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
