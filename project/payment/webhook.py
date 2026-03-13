# payments/views.py
import stripe
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.conf import settings
from order.models import VALID_PAYMENT_TYPES, Order
from logging import getLogger

logger = getLogger(__name__)


@csrf_exempt
def stripe_webhook(request):

    payload = request.body
    sig_header = request.META["HTTP_STRIPE_SIGNATURE"]

    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )
    logger.info(f"event object on stripe webhook {event}")
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        transaction_id = payment_intent["id"]
        order_id = payment_intent["metadata"]["order_id"]
        logger.info(f"meta of intent {payment_intent['metadata']}")
        # save to database
        Order.objects.filter(id=order_id).update(
            paid=True,
            payment_type = VALID_PAYMENT_TYPES[4][0],
            is_epay = True,
            transaction_id = transaction_id,
        )
        logger.info(f"order {order_id} marked as paid")
    return HttpResponse(status=200)
