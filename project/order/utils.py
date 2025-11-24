from django.urls import reverse
import requests
import json
from django.conf import settings


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
        print("this is payload", payload)
        response = requests.post(endpoint, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(e.args,e)
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
    print(success_url,"start payment session urls---")
    print("this was response in starting payment session:", response, items, order_id)
    return response


import requests
import json
import base64
from cryptography.fernet import Fernet


def encrypt_pin(pin, encryption_key):
    """
    Encrypt PIN for secure transmission
    """
    f = Fernet(encryption_key)
    encrypted_pin = f.encrypt(pin.encode())
    return base64.b64encode(encrypted_pin).decode()


def create_multi_vendor_payment(api_key, encrypted_pin, vendors):
    """
    Distribute payment to multiple vendors

    Args:
        api_key (str): Your API key
        encrypted_pin (str): Your encrypted account PIN
        vendors (list): List of vendor accounts and amounts

    Returns:
        dict: API response
    """
    endpoint = settings.HESAB_PAY_MULTI_VENDOR_ENDPOINT
    headers = {
        "Authorization": f"API-KEY {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {"pin": encrypted_pin, "vendors": vendors}

    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        return {"error": "Request failed", "message": str(e)}


# Example usage
api_key = settings.HESAB_PAY_API_KEY
pin = "4245"

encryption_key = b"kX3hH7QkPz0V8F0fX8yS6k6dO3g8GfN3WcBAzT5i5Yc="

encrypted_pin = encrypt_pin(pin, encryption_key)

vendors = [
    {"account_number": "0794825911", "amount": 20},
    {"account_number": "0794825001", "amount": 40},
    {"account_number": "0742825911", "amount": 20},
]

result = create_multi_vendor_payment(api_key, encrypted_pin, vendors)
print(json.dumps(result, indent=2))
