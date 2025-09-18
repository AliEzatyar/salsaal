from marketplace.utils import r as r
from decouple import config
from accounts.models import Device
from pyfcm import FCMNotification

def is_user_online(user_id):
    return r.exists(f"user:{user_id}")  # returns 1 if online, 0 if offline


def send_notification(user_id, title, body, data=None):
    # Check if user is online via Redis
    print("user",user_id, "title",title,"body",body,"data",data)
    if is_user_online(id):
        print("user is online")
        return "Sent via WebSocket"
    print("user was offline")
    # User offline → send push
    devices = Device.objects.filter(user__id=user_id)
    for device in devices:
        print("user device android")
        send_fcm(device.token, title, body, data)
        print("notification sent via fcm")


fcm_api_key = config("FIREBASE_SERVICE_ACCOUNT_KEY")
fcm = FCMNotification(service_account_file=fcm_api_key)


def send_fcm(token, title, body, data=None):
    result = fcm.notify(
        token,
        title,
        body,
        data or {},
    )
    return result

