import json
from decimal import Decimal
import stripe
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from marketplace.utils import r
from order.models import Order
from logging import getLogger

logger = getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


@api_view(["POST"])
@permission_classes([AllowAny])
def create_payment_intent(request):
    order_id = request.data.get("order_id")
    order = Order.objects.filter(id=order_id).first()
    if not order:
        return Response(status=status.HTTP_404_NOT_FOUND)

    rate = r.get("exchange:AFN_USD")
    rate = json.loads(rate)
    if not rate:
        logger.info("rate not in redis")
        rate = 1 / 65
    total_in_usd = int(Decimal(rate) * order.total_price * 100)
    intent = stripe.PaymentIntent.create(
        amount=int(total_in_usd), currency="usd", metadata={"order_id": order_id}
    )
    return Response({"client_secret": intent.client_secret})


@api_view(["GET"])
@permission_classes([AllowAny])
def get_order_payment_status(request):
    order_id = request.data.get("order_id", None)
    if order_id:
        try:
            order = Order.objects.get(id=order_id)
            if order.paid == True & order.transaction_id:
                return Response({"message": "order_is_paid"}, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"detail": "order_not_paid"},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )
        except:
            return Response(status=status.HTTP_400_BAD_REQUEST)
    return Response(status.HTTP_400_BAD_REQUEST)
