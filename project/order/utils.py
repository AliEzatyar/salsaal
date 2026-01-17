from django.urls import reverse
import requests
import json
from django.conf import settings
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad
import base64
from logging import getLogger

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


def create_multi_vendor_payment(vendors):
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
        logger.info(f"Multi-vendor payment api call response: {response.text}")
        return response.json()

    except requests.exceptions.RequestException as e:
        logger.error(f"Request to create multi-vendor payment failed: {e}")
        return {"error": "Request failed", "message": str(e)}


# Example usage



vendors = [
    {"account_number": "0794825911", "amount": 20},
]