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
