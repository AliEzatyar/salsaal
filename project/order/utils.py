from django.urls import reverse
import requests
import json
from django.conf import settings
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad
import base64
from logging import getLogger
from marketplace.utils import r
import json
from order.models import FailedMultiVendorPayment
from celery import shared_task
from django.utils.translation import gettext as _ 

from multiVend.settings.dev import TELEGRAM_API_URL, TELEGRAM_BOT_URL

logger = getLogger(__name__)


def get_order_delivery_tries_key(order_id):
    """
    Generates a key for tracking the number of delivery attempts for a specific order.
    Args:
        order_id (str or int): The unique identifier for the order.
    Returns:
        str: A formatted string representing the key for the order's delivery attempts.
    """

    return f"order:{order_id}:d_tries"


def create_payment_session(api_key, items, order_id, email=None, redirect_urls=None):
    """
    Create a payment session with HesabPay

    Args:
        api_key (str): Your API key
        items (list): List of items with id, name, and price
        email (str, optional): Customer email
        redirect_urls (dict, optional): Success and failure URLs

    Returns:
        dict: API response with session details
    """
    endpoint = settings.HESAB_PAY_ENDPOINT

    headers = {
        "Authorization": f"API-KEY {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {"items": items, "reference_id": order_id}

    # Add optional parameters
    if email:
        payload["email"] = email

    if redirect_urls:
        payload.update(
            {
                "redirect_success_url": redirect_urls.get("success_url"),
                "redirect_failure_url": redirect_urls.get("failure_url"),
            }
        )

    try:
        response = requests.post(endpoint, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        logger.exception(f"Request to create payment session failed: {e}")
        return {"error": "Request failed", "message": str(e)}


def start_payment_session(items, order_id):
    """this function starts payment session and returns session url"""
    CURRENT_DOMAIN_NAME = settings.CURRENT_DOMAIN_NAME
    success_url = CURRENT_DOMAIN_NAME + reverse("api:order:redirect_payment_success")
    failure_url = CURRENT_DOMAIN_NAME + reverse("api:order:redirect_payment_failure")
    response = create_payment_session(
        settings.HESAB_PAY_API_KEY,
        items,
        order_id,
        redirect_urls={"success_url": success_url, "failure_url": failure_url},
    )
    return response


import requests
import json
import base64
from cryptography.fernet import Fernet


def encrypt_pin(data, key):
    key = key.encode("utf-8")[:32]
    key = key.ljust(32, b"\0")

    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(data.encode("utf-8"), AES.block_size)

    ciphertext = cipher.encrypt(padded_data)
    encrypted_data = base64.b64encode(iv + ciphertext).decode("utf-8")
    return encrypted_data


def create_multi_vendor_payment(vendors,order):
    """
    Distribute payment to multiple vendors

    Args:
        api_key (str): Your API key
        pin (str): Your account PIN
        vendors (list): List of vendor accounts and amounts

    Returns:
        dict: API response
    """
    api_key = settings.HESAB_PAY_API_KEY
    pin = settings.HESAB_PAY_ACCOUNT_PIN
    endpoint = settings.HESAB_PAY_MULTI_VENDOR_ENDPOINT
    headers = {
        "Authorization": f"API-KEY {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    encrypted_pin = encrypt_pin(pin, api_key)
    payload = {"pin": encrypted_pin, "vendors": vendors}
    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        response = response.json()
        logger.info(f"Multi-vendor payment api call response: {response}")
        if response.get("success") == False:
            # multivendor payment faild, release lock so other tries get succeded
            release_payment_lock(order.id)
            logger.error(f"multi vendor payment failed for order :  {order.id}")

        else:
            # multivendor payment successful, keep it for 24 hours
            mark_payment_success(order.id)
            logger.info(f"multi vendor payment successful for order : {order.id}")
        return response

    except requests.exceptions.RequestException as e:
        logger.error(f"Request to create multi-vendor payment failed: {e}")
        FailedMultiVendorPayment.objects.create(
                                order=order,
                                error_message=str(e),
                                request_data=vendors
                            )
        return None


PAYMENT_TTL = 300  # 5 minutes

def get_order_payment_key(order_id):
    key = f"ordr_mltv_pmnt:{order_id}"
    return key
    

def acquire_payment_lock(order_id: int) -> bool:
    """
    Returns True if we can proceed with payment.
    Returns False if payment is already processing or completed.
    """
    key = get_order_payment_key(order_id)
    # SET key value NX EX is atomic
    return r.set(
        name=key,
        value="processing",
        nx=True,
        ex=PAYMENT_TTL
    )


def mark_payment_success(order_id: int):
    key = get_order_payment_key(order_id)
    # keep success longer to prevent replays
    r.set(
        name=key,
        value="success",
        ex=86400  # 24 hours
    )


def release_payment_lock(order_id: int):
    """
    Use ONLY if payment failed and you want retries.
    """
    key = f"order_payment:{order_id}"
    r.delete(key)


def verify_hesab_pay_transaction(api_key, transaction_id):
    """
    Verify transaction details with HesabPay

    Args:
        api_key (str): Your API key
        transaction_id (str): Transaction ID to verify

    Returns:
        dict: API response with transaction details
    """
    endpoint = settings.HESAB_PAY_TRANSACTION_DETAILS_ENDPOINT + str(transaction_id)

    headers = {
        "Authorization": f"API-KEY {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        success = response.json().get("success", False)
        if not success or success in ["false", "False"]:
            logger.error(f"Transaction verification failed for transaction ID: {transaction_id}")
            return False
        logger.info(f"Transaction verified successfully for transaction ID: {transaction_id}")
        return True
    except requests.exceptions.RequestException as e:
        logger.exception(f"Request to verify transaction details failed: {e}")
        return False
    

def get_hesab_pay_transaction_detail(api_key, transaction_id):
    """
    Get transaction details from HesabPay

    Args:
        api_key (str): Your API key
        transaction_id (str): Transaction ID to get details for

    Returns:
        dict: API response with transaction details
    """
    endpoint = settings.HESAB_PAY_TRANSACTION_DETAILS_ENDPOINT + str(transaction_id)

    headers = {
        "Authorization": f"API-KEY {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.exception(f"Request to get transaction details failed: {e}")
        return {}



def get_order_manager_chat_ids():
    """
    Get order managers' chat IDs from Redis or DB.
    Returns:
        list[str]
    """
    cached = r.get('order_manager_chat_ids')
    if cached:
        return json.loads(cached)

    from accounts.models import User

    try:
        chat_ids = list(
            User.objects
            .filter(groups__name="Order Manager")
            .values_list("name", flat=True)
        )
        logger.info(f"Fetched order manager chat ids from DB: {chat_ids}")
        if chat_ids:
            r.set(
                'order_manager_chat_ids',
                json.dumps(chat_ids),
                ex= 24 * 3600  # cache for 24 hours
            )

        return chat_ids

    except Exception as e:
        logger.error(f"Error fetching order manager chat ids: {e}")
        return []


from django.utils.translation import activate, deactivate, gettext as _


def get_new_order_message(order):
    """
    Generate a new order message (translated via gettext).
    """
    activate("fa")

    message = _(
        "New order received!\n\n"
        "Order ID: %(order_id)s\n"
        "Customer: %(customer)s\n"
        "Total price: %(total_price)s\n"
        "Vendor: %(vendor)s\n"
        "Vendor Phone: %(vendor_phone)s\n"
        "Date:  %(date)s\n"
        "link: %(link)s\n"
    ) % {
        "order_id": order.id,
        "customer": order.user.phone_number if order.user else _("Unknown user"),
        "total_price": order.total_price,
        "vendor": order.vendor,
        "vendor_phone": order.vendor.user.phone_number,
        "date": order.created_at,
        "link": "https://api.zayton.llc/hello-world-3000/order/order/"
    }

    deactivate()
    return message


def send_message(chat_id: str, text: str):
    """
    Send a Telegram message to a chat ID.
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    response = requests.post(TELEGRAM_BOT_URL, json=payload, timeout=10)
    logger.info(f"Telegram API response for chat_id {chat_id}: {response.status_code} {response.text}")
    if response.status_code != 200:
        logger.error(
            f"Telegram API error for chat_id {chat_id}: "
            f"{response.status_code} {response.text}"
        )
        response.raise_for_status()

    return response.json()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, retry_kwargs={"max_retries": 3})
def send_message_to_order_managers(self, message: str):
    """
    Send a message to all order managers.
    """
    logger.info("Sending message to order managers, message: %s", message)
    chat_ids = get_order_manager_chat_ids()

    if not chat_ids:
        logger.warning("No order manager chat IDs found in redis")
        return

    for chat_id in chat_ids:
        try:
            send_message(chat_id, message)
            
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            # keep going, one bad manager shouldn't silence the rest


