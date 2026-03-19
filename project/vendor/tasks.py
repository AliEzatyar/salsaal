from celery import shared_task
from marketplace.models import Discount, Food
from marketplace.utils import r
from django.utils import timezone as tz
from carrier.models import CARRIER_STATUS_CHOICES
from order.models import ORDER_STATUS_CHOICES, Order
from vendor.models import Vendor
from vendor.utils import get_vendor_carriers_key, revert_discount
from django.db.transaction import atomic
from logging import getLogger

logger = getLogger(__name__)

@shared_task
def deactivate_discounts():
    discounts = Discount.objects.filter(deadline__lte=tz.now(),is_active=True).prefetch_related(
        "foods"
    )
    # resetting foods prices to original
    with atomic():
        for dis in discounts:
            discount_foods = dis.foods.only("id", "min_price", "prices")
            for food in discount_foods:
                food = revert_discount(food, dis.amount)
            Food.objects.bulk_update(discount_foods, ["prices", "min_price"])
        discounts.update(is_active=False)
    return "Discounts Deactivated!"


@shared_task
def reset_vendors_carriers_in_redis():
    """
    this task resets f_c_c, b_c_c and total_c_c in redis for all vendors
    """
    logger.info("reverting carriers status for all vendors")

    vendors = Vendor.objects.all().prefetch_related("carriers")
    for vendor in vendors:
        vendor_carriers_key = get_vendor_carriers_key(vendor.id)
        # setting all carriers of this vendor free
        vendor.carriers.update(status=CARRIER_STATUS_CHOICES[0][0])
        # setting total carriers count from db
        total_carriers_count = vendor.carriers.filter(is_active=True).count()
        r.hset(vendor_carriers_key, "total_c_c", total_carriers_count)  # total carriers
        r.hset(vendor_carriers_key, "f_c_c", total_carriers_count)  # all free
        r.hset(vendor_carriers_key, "b_c_c", 0)  # no busy carriers

    return "Carriers reset!"


@shared_task
def disable_vendors():
    """
    this task marks all vendors disabled every 3 hours
    any vendor heading orders page is marked as avaialble
    """
    Vendor.objects.all().update(is_available=False)
    return "Vendors disabled"    


@shared_task
def mark_order_delivered(order_id):
    try:
        order = Order.objects.get(id=order_id)
        if not order.carrier.is_online:
            order.status = ORDER_STATUS_CHOICES[4][1]  # delivered
            order.paid = True
            order.save()
        return "Order carrier online, no auto deliver"
    except Exception as e:
        return "Error in mark order delivered task for legacy carriers" + str(e.args)


@shared_task
def enable_vendors():
    logger.info("enabling vendors")
    Vendor.objects.all().update(is_available=True)


@shared_task
def disable_vendors():
    logger.info("disbaling vendors")
    Vendor.objects.all().update(is_available=False)
