from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage


def send_email(request, user): 
    """
        sends an email to verify the new registered user
    """
    current_site = get_current_site(request)
    mail_title = "Verify You Email"
    mail_body = render_to_string(
        "accounts/emails/account_verification.html",
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


def send_forgot_email(request, user,template=None):
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


def send_notification(receiver,mail_title, mail_template: str, context: dict):
    mail_body = render_to_string(mail_template, context)
    mail_to = receiver
    mail = EmailMessage(subject=mail_title, to=[mail_to], body=mail_body)
    mail.send()


