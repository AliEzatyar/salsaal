import json
from decimal import Decimal
import stripe
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from marketplace.utils import r
from order.models import Order
from logging import getLogger

logger = getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_payment_intent(request):
    order_id = request.data.get("order_id")
    order = Order.objects.filter(id=order_id).first()
    if not order:
        return Response(status=status.HTTP_404_NOT_FOUND)

    rate = r.get("exchange:AFN_USD")
    rate = json.loads(rate)
    if not rate:
        logger.error("rate not in redis")
        rate = 1 / 65
    total_in_usd = int(Decimal(rate) * order.total_price * 100)
    total_in_usd = 0.1 * total_in_usd + total_in_usd
    intent = stripe.PaymentIntent.create(
        amount=int(total_in_usd), currency="usd", metadata={"order_id": order_id}
    )
    extra = dict(order.extra_data)
    extra["total_in_usd"] = total_in_usd / 100
    order.extra_data = extra
    order.save()
    return Response({"client_secret": intent.client_secret})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_order_payment_status(request):
    order_id = request.GET.get("order_id", None)
    if order_id:
        try:
            order = Order.objects.get(id=order_id)
            if order.paid == True and order.transaction_id:
                return Response({"message": "order_is_paid"}, status=status.HTTP_200_OK)
            else:
                logger.error(f"order not paid in check order payment :{e}")
                return Response(
                    {"detail": "order_not_paid"},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )
        except Exception as e:
            logger.error(f"execption in check order payment :{e}")
            return Response(status=status.HTTP_400_BAD_REQUEST)
    logger.error(f"no order id")
    return Response(status=status.HTTP_400_BAD_REQUEST)
