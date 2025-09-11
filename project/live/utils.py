from marketplace.utils import r as r
from decouple import config
from accounts.models import Device
from json import dumps
from pyfcm import FCMNotification
from apns2.client import APNsClient
from apns2.payload import Payload

def is_user_online(user_id):
    print("is online mthod called", r.exists(f"user:{user_id}"))
    return r.exists(f"user:{user_id}")  # returns 1 if online, 0 if offline


def send_notification(room,id, title, body, data=None):
    # Check if user is online via Redis
    if is_user_online(id):
        # publish to WebSocket (Redis pub/sub)
        r.publish(
            f"pub:vendor:{id}",
            dumps(
                {"id":id, "title": title, "body": body, "data": data}
            ),
        )
        return "Sent via WebSocket"
    print("user was offline")
    # User offline → send push
    devices = Device.objects.filter(user__id=id)
    for device in devices:
        if device.platform == "android":
            print("user device android")
            send_fcm(device.token, title, body, data)
        elif device.platform == "ios":
            print("user device ios")
            send_apns(device.token, {"title": title, "body": body}, data)


fcm_api_key = config("FIREBASE_SERVICE_ACCOUNT_KEY")
fcm = FCMNotification(api_key=fcm_api_key)


def send_fcm(token, title, body, data=None):
    result = fcm.notify_single_device(
        registration_id=token,
        message_title=title,
        message_body=body,
        data_message=data or {},
    )
    return result


apns_client = APNsClient(
    "path/to/AuthKey_XXXXXXXXXX.p8",
    use_sandbox=True,
    team_id="YOUR_TEAM_ID",
    key_id="YOUR_KEY_ID",
)


def send_apns(token, alert, custom_data=None):
    payload = Payload(alert=alert, sound="default", badge=1, custom=custom_data or {})
    apns_client.send_notification(token, payload)
