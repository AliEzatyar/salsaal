from marketplace.utils import r 
from accounts.models import Device
from pyfcm import FCMNotification
from django.conf import settings
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

def is_user_online(user_id):
    return r.exists(f"user:{user_id}")  # returns 1 if online, 0 if offline

@shared_task(bind=True, max_retries=5,default_retry_delay=10)
def send_notification(self,user_id, title, body, data=None):
    """sends notification in background-task mode"""
    try:
        # Check if user is online via Redis
        print("user", user_id, "title", title, "body", body, "data", data)
        if is_user_online(id):
            print("user is online")
            return "Sent via WebSocket"
        print("user was offline")
        # User offline → send push
        devices = Device.objects.filter(user__id=user_id)
        if not devices.exists():
            print("use has no registered device")
            return "NoDevice"
        for device in devices:
            try:
                print("user device android")
                send_fcm(device.token, title, body, data)
                print("notification sent via fcm in celery")
            except Exception as e:
                raise self.retry(exc=e)
    except ObjectDoesNotExist:
        print("objec does not exist", e)

        return "does not exist"
    except Exception as e:
        print("error in celery ",e)
        raise self.retry(exc=e)

fcm_api_key = settings.FCM_API_KEY
fcm = FCMNotification(service_account_file=fcm_api_key)


def send_fcm(token, title, body, data=None):
    android_cfg = {
        "priority": "high",  # wrapper will translate to android priority
        "notification": {
            "channel_id": "eatee_channel",  # MUST match Android channel id
            "sound": "default",
        },
    }

    result = fcm.notify(
        fcm_token=token,
        notification_title=title,
        notification_body=body,
        data_payload={k: str(v) for k, v in (data or {}).items()},
        android_config=android_cfg,
    )
    return result
