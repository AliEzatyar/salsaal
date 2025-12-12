from celery import shared_task
from marketplace.models import Discount, Food
from marketplace.utils import r
from django.utils import timezone as tz
from carrier.models import CARRIER_STATUS_CHOICES
from order.models import ORDER_STATUS_CHOICES, Order
from vendor.models import Vendor
from vendor.utils import get_vendor_carriers_key, revert_discount
from django.db.transaction import atomic


@shared_task
def deactivate_discounts():
    discounts = Discount.objects.filter(deadline__lte=tz.now()).prefetch_related(
        "foods"
    )
    # resetting foods prices to original
    with atomic():
        for dis in discounts:
            discount_foods = dis.foods.only("id", "min_price", "prices")
            for food in discount_foods:
                print("discount cleared by celery...", food.id)
                food = revert_discount(food, dis.amount)
            Food.objects.bulk_update(discount_foods, ["prices", "min_price"])
        discounts.update(is_active=False)
    return "Discounts Deactivated!"


@shared_task
def reset_vendors_carriers_in_redis():
    """
    this task resets f_c_c, b_c_c and total_c_c in redis for all vendors
    """
    print("revert carriers status for all vendors")

    vendors = Vendor.objects.all().prefetch_related("carriers")
    for vendor in vendors:
        if Order.objects.filter(
            vendor=vendor, status=ORDER_STATUS_CHOICES[3][0]
        ).exists():
            print("order in carrying, no reset for this vendor ", vendor.id)
            continue
        vendor_carriers_key = get_vendor_carriers_key(vendor.id)
        # setting all carriers of this vendor free
        vendor.carriers.update(status=CARRIER_STATUS_CHOICES[0][0])
        # setting total carriers count from db
        total_carriers_count = vendor.carriers.filter(is_active=True).count()
        r.hset(vendor_carriers_key, "total_c_c", total_carriers_count)  # total carriers
        r.hset(vendor_carriers_key, "f_c_c", total_carriers_count)  # all free
        r.hset(vendor_carriers_key, "b_c_c", 0)  # no busy carriers

    return "Carrier's reset!"


@shared_task
def disable_vendors():
    """
    this task marks all vendors disabled every 3 hours
    any vendor heading orders page is marked as avaialble
    """
    Vendor.objects.all().update(is_available=False)
    return "Vendors disabled"    
