import stripe
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from marketplace.utils import r
from order.models import Order
from logging import getLogger

logger = getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


@api_view(["POST"])
def create_payment_intent(request):
    order_id = request.data.get("order_id")
    order = Order.objects.filter(id=order_id).first()
    if not order:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    rate = r.get("exchange:AFN_USD")
    if not rate:
        logger.info("rate not in redis")
        rate = 1/65
    total_in_usd = int(rate) * order.total_price
    logger(f"total order price in usd:{total_in_usd}")
    intent = stripe.PaymentIntent.create(
        amount=int(total_in_usd),
        currency="usd",
        metadata={
            "order_id":order_id
        }
    )
    logger.info(f"payment intent created, client_secret: {intent.client_secret}")
    return Response({"client_secret": intent.client_secret})
