from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from .models import NoUserOtp, User, UserOtp
from celery import shared_task
from random import randint
import requests
from marketplace.utils import r
from django.conf import settings
from json import loads as jloads

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
        return randint(10000000, 99999999)
    return randint(100000, 999999)


OTP_VERIFY_PHONE = 1
OTP_FORGOT_PASSWORD = 2
OTP_VERIFY_CARRIER = 3
OTP_LOGIN = 4

def create_otp_text(otp):
    return otp


def get_cpaas_token():
    token = r.get("cpaas_token")
    r.expire("cpaas_token", 3)  # setting expiry to 1 hour

    print("cpaas token from redis:", token)
    if token:
        return jloads(token)
    else:
        # making a request to get new token
        response = requests.post(
            settings.CPAAS_AUTHENTICATION_URL,
            data={"username": settings.CPAAS_USERNAME, "password": settings.CPAAS_PASSWORD},
        )
        print("cpaas token response:", response.status_code, response.text)
        if response.status_code == 200:
            token = response.json().get("idToken")
            if token:
                r.set("cpaas_token", token)
                r.expire("cpaas_token", 3600)  # setting expiry to 1 hour
                return token
            else:
                print("No token found in response of CPAAS")

@shared_task(bind=True, max_retries=5, default_retry_delay=10)
def send_otp(self,otp=None, user_id=None, phone_number=None, **kwargs):
    """
    sends otp using OBD compaign
    """
    try:
        if not user_id:
            # no-user otp for sign up
            print("no user id, creating no user otp")
            if not phone_number:
                return "no phone number provided for sending otp"
            print("phone number provided:", phone_number)
            # deleting previous
            NoUserOtp.objects.filter(phone_number=phone_number).delete()
            # creating new one
            NoUserOtp.objects.create(otp=otp, phone_number=phone_number)
        else:
            print("user id provided, creating user otp")
            # removing previous otp if existing
            user = User.objects.get(id=user_id)
            UserOtp.objects.filter(user__id=user_id).delete()
            # creating new otp
            UserOtp.objects.create(user=user, otp=otp)

        # calling
        print("sending otp via CPAAS...")
        otp_text = create_otp_text(otp)
        token = get_cpaas_token()
        if not token:
            print("Could not get CPAAS token")
            return "Could not get CPAAS token"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        phone_number = str(phone_number).split("+93")[1]  # removing leading 0
        print("phone number converted", phone_number)
        data = {
            "dni": settings.CPAAS_CALLER_ID,
            "Records": [{"msisdn": int(phone_number), "otp": str(otp_text)}],
            "campaign_ID": settings.CPAAS_OBD_CAMPAIGN_ID,
        }
        print(data,"data")
        response = requests.post(
                settings.CPAAS_UPLOAD_BASELOAD_URL, json=data, headers=headers
            )
        
        if response.status_code in (200,201):
            return "OTP sending successful!"
        else:
            print(f"Failed to send OTP, status code: {response.status_code}, response: {response.text}")
            return f"Failed to send OTP, status code: {response.status_code}, response: {response.text}"
    except Exception as e:
        print(f"Error sending OTP: {e}")
        # retry after 10 seconds
        delay = min(60 * 2 ** self.request.retries, 10)
        raise self.retry(exc=e, countdown=delay)


def get_user_otp_tries_key(phone_number):
    return f"user:{phone_number}:tries"


CITY_TRANSLATIONS = {
    "Kabul": "کابل",
    "Herat": "هرات",
    "Kandahar": "قندهار",
    "Mazar-e Sharif": "مزار شریف",
    "Jalalabad": "جلال‌آباد",
    "Kunduz": "کندوز",
    "Ghazni": "غزنی",
    "Bamyan": "بامیان",
    "Faizabad": "فیض‌آباد",
    "Pul-e Khumri": "پل خمری",
    "Charikar": "چاریکار",
    "Taloqan": "تالقان",
    "Sheberghan": "شبرغان",
    "Sar-e Pol": "سرپل",
    "Maimana": "میمنه",
    "Farah": "فراه",
    "Lashkar Gah": "لشکرگاه",
    "Khost": "خوست",
    "Gardez": "گردیز",
    "Zaranj": "زرنج",
    "Qalat": "قلات",
    "Asadabad": "اسعدآباد",
    "Mahmud-e Raqi": "محمودراقی",
    "Mehtar Lam": "مهترلام",
    "Nili": "نیلی",
    "Aybak": "ایبک",
    "Pul-e Alam": "پل علم",
    "Sharana": "شرنه",
    "Fayroz Koh": "فیروزکوه",
    "Chaghcharan": "چغچران",  # old name for Ghor capital
    "Tarin Kot": "ترین‌کوت",
    "Parun": "پرون",
    "Kunar": "کنر",
    "Uruzgan": "ارزگان",
    "Logar": "لوگر",
    "Badghis": "بادغیس",
    "Badakhshan": "بدخشان",
    "Samangan": "سمگان",
    "Paktia": "پکتیا",
    "Paktika": "پکتیکا",
    "Daikundi": "دایکندی",
    "Nangarhar": "ننگرهار",
    "Helmand": "هلمند",
    "Faryab": "فاریاب",
    "Balkh": "بلخ",
    "Kunar Province": "ولایت کنر",
    "Wardak": "وردک",
    "Maidan Shahr": "میدان‌شهر",
}
