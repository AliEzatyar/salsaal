from marketplace.utils import r
from accounts.models import Device
from pyfcm import FCMNotification
from django.conf import settings
from celery import shared_task

from logging import getLogger

logger = getLogger(__name__)

@shared_task(bind=True, max_retries=5, default_retry_delay=10)
def push_notification(self, user_id: int, title: str, body: str, data=None):
    """
    Send a notification to a user: via WebSocket if online, otherwise via FCM to their registered devices.
    Args:
        user_id: ID of the target user.
        title: Notification title.
        body: Notification body text.
        data: Optional extra payload for the push message.
    Returns:
        A status string such as "Sent via WebSocket" or "NoDevice{user_id}" when applicable; otherwise None.
    Raises:
        May invoke Celery retry on delivery errors.
    """
    try:
        # Check if user is online via Redis
        devices = Device.objects.filter(user__id=user_id)
        if not devices.exists():
            return f"NoDevice{user_id}"
        for device in devices:
            try:
                send_fcm(device.token, title, body, data)
            except Exception as e:
                logger.exception(f"Error sending FCM to device {device.id} for user {user_id}: {e}")
                raise self.retry(exc=e)
        return "Notification sent via FCM"
    except Exception as e:
        logger.exception(f"Error in celery task push_notification: {e}")
        raise self.retry(exc=e)


fcm_api_key = settings.FCM_API_KEY
fcm = FCMNotification(service_account_file=fcm_api_key)


def send_fcm(token, title, body, data=None):
    android_cfg = {
        "priority": "high",
        "notification": {
            "channel_id": "zayton_channel",
            "sound": "default",
        },
    }

    apns_config = {
        "headers": {"apns-priority": "10"},
        "payload": {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
                "badge": 1,
            }
        },
    }

    try:
        return fcm.notify(
            fcm_token=token,
            notification_title=title,
            notification_body=body,
            data_payload={k: str(v) for k, v in (data or {}).items()},
            android_config=android_cfg,
            apns_config=apns_config,
        )
    except Exception as e:
        logger.exception(f"Error in fcm sending notification, token {token}: {e}")
        return None

