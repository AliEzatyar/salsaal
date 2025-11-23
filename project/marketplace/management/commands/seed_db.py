# app_name/management/commands/seed_db.py
import random
import math
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from faker import Faker
import requests
from accounts.models import UserProfile
from vendor.models import Vendor
from marketplace.models import Category, Food
from .constants import *
from django.core.files.base import ContentFile


User = get_user_model()
faker = Faker("fa_IR")


def generate_unique_phone(existing_numbers=set()):
    """Generate unique Afghan phone numbers starting with +93 (12 chars)."""
    while True:
        number = "+93" + "".join([str(random.randint(0, 9)) for _ in range(9)])
        if number not in existing_numbers:
            existing_numbers.add(number)
            return number


def random_location_within_radius(lat, lon, radius_km=5):
    """
    Generate random lat/lon within radius_km around given lat/lon.
    """
    # 1 degree ≈ 111 km
    radius_in_degrees = radius_km / 111

    # Random angle
    u = random.random()
    v = random.random()
    w = radius_in_degrees * math.sqrt(u)
    t = 2 * math.pi * v
    delta_lat = w * math.cos(t)
    delta_lon = w * math.sin(t) / math.cos(math.radians(lat))

    return str(lat + delta_lat), str(lon + delta_lon)


class Command(BaseCommand):
    help = "Seed the database with random data"

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding Users and UserProfiles...")
        users = []
        profiles = []

        # exisitng
        existing_phone_numbers = set(
            User.objects.all().values_list("phone_number", flat=True)
        )

        for _ in range(NUM_VENDORS):
            user = User(
                name=faker.name(),
                phone_number=generate_unique_phone(existing_phone_numbers),
            )
            users.append(user)

        User.objects.bulk_create(users)
        users = list(User.objects.all().order_by("-id")[:NUM_VENDORS])

        for user in users:
            random_location = random_location_within_radius(
                CENTER_LOCATION[0], CENTER_LOCATION[1], 20
            )
            profile = UserProfile(
                user=user,
                pf_lang=random.choice(["fa", "en"]),
                country="AF",
                picture=PLACEHOLDER_IMAGE,
                city=DEFAULT_CITY,
                latitude=random_location[0],
                longitude=random_location[1],
            )
            profiles.append(profile)

        UserProfile.objects.bulk_create(profiles)
        profiles = list(UserProfile.objects.all().order_by("-id")[:NUM_VENDORS])
        # ------------------- seeding categoris --------------
        self.stdout.write("Seeding Categories...")
        for _ in range(NUM_CATEGORIES):
            name = CATEGORY_NAMES[_]
            icon_bytes = self._get_random_image(50, 50)
            category = Category(
                name=name,
                show_on_home=True,
                description=faker.sentence(),
            )
            if icon_bytes:
                print("setting category icon...")
                category.icon.save(
                    f"category_{name}_{random.randint(1,100)}",
                    ContentFile(icon_bytes),
                )
            else:
                print("could not set category image")
                category.icon = f"NotFilled{random.randint(1,100)}"

            category.save()
            print("cateogry created", _)

        categories = list(Category.objects.all().order_by("-id")[:NUM_CATEGORIES])

        self.stdout.write("Seeding Vendors...")
        for index, profile in enumerate(profiles):
            vendor_name = VENDOR_NAMES[index]
            vendor_image_bytes = self._get_random_image()
            vendor_logo_bytes = self._get_random_image(50, 50)
            vendor = Vendor(
                user_profile=profile,
                user=profile.user,
                vendor_name=vendor_name,
                is_approved=True,
                avg_rating=round(random.uniform(1, 5), 1),
                rating_count=random.randint(0, 100),
                mfdd=random.randint(0, 10),
                mfcfd=random.randint(2, 5),
                min_order_price=random.randint(50, 500),
                delivery_fee_km=random.randint(3, 10),
                is_available=True,
                reward_percentage=round(random.uniform(0, 20), 1),
            )
            if vendor_image_bytes:
                print("setting vendor image and license...")

                vendor.vendor_license.save(
                    f"vendor_l{random.randint(1,100)}", ContentFile(vendor_image_bytes)
                )
                vendor.image.save(
                    f"vendor_i{random.randint(1,100)}", ContentFile(vendor_image_bytes)
                )
            if vendor_logo_bytes:
                print("setting venodr logo")
                vendor.logo.save(f"vendor_logo_{random.randint(1,100)}", ContentFile(vendor_logo_bytes))
            print("saving venodr....")
            vendor.save()
        # seeding food table
        vendors = list(Vendor.objects.all().order_by("-id")[:NUM_VENDORS])
        categories = list(Category.objects.all().order_by("-id"))
        self.stdout.write("Seeding Foods...")
        for vendor in vendors:
            for _ in range(NUM_FOODS_PER_VENDOR):
                category = random.choice(categories)
                food_name = FOOD_NAMES[_]
                min_price = Decimal(random.randint(100, 500))
                prices = [float(min_price), float(min_price + random.randint(50, 1000))]
                image_bytes = self._get_random_image()
                food = Food(
                    vendor=vendor,
                    name=food_name,
                    min_price=min_price,
                    prices=prices,
                    category=category,
                    description=faker.sentence(),
                    is_available=True,
                    avg_rating=round(random.uniform(0, 5), 1),
                    rating_count=random.randint(0, 100),
                    discount=None,
                    is_featured=random.choice([True, False]),
                    likes=random.randint(0, 1000),
                    is_drink=False,  # all normal food
                    is_ready_type=False,  # all fast food
                    ready_time=None,
                    duration=random.randint(5, 30),
                )
                if image_bytes:
                    print("setting food image...")
                    food.image.save(
                        f"food_{food_name}_{random.randint(1,100)}",
                        ContentFile(image_bytes),
                    )
                else:
                    print("could not set food image")
                    food.image = f"NotFilled{random.randint(1,100)}"
                food.save()
                print("food created", _)

        self.stdout.write(self.style.SUCCESS("Database seeding complete!"))

    def _get_random_image(self, width=400, height=400):
        """Fetch random image from Picsum"""
        try:
            url = f"https://picsum.photos/{width}/{height}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print("feteched image from site...")
                return response.content
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️ Could not fetch image: {e}"))
        return None
