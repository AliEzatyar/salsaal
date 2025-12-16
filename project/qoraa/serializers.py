from django.utils import timezone
from rest_framework.serializers import (
    ModelSerializer,
    SerializerMethodField,
    ReadOnlyField,
)
from accounts.models import User, UserProfile
from marketplace.models import Food
from qoraa.tasks import end_vendor_qoraa, start_vendor_qoraa
from vendor.models import Vendor
from qoraa.models import MIN_QORAA_PRICE_VALUE, Qoraa
from rest_framework.serializers import ValidationError
from logging import getLogger

logger = getLogger(__name__)


class QoraaSerializer(ModelSerializer):
    joiners_count = SerializerMethodField()

    class Meta:
        model = Qoraa
        fields = [
            "id",
            "title",
            "start",
            "end",
            "joiners_count",
            "status",
            "vendor",
            "food",
            "price_value",
            "is_joined",
        ]
        read_only_fields = fields

    def get_joiners_count(self, obj):
        return obj.joiners.count()

    def get_is_joined(self, obj):
        user = self.context.get("request").user
        if user.is_authenticated:
            return obj.joiners.filter(pk=user.pk).exists()
        return False


class QoraaWinnerSerializer(ModelSerializer):
    image = SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "image"]

    def get_image(self, obj):
        try:
            profile = UserProfile.objects.get(user=obj)
            if profile.picture:
                return profile.picture.url
            return None
        except UserProfile.DoesNotExist:
            return None


class QoraaReadOnlySerializer(ModelSerializer):
    """for listing qoraas with details for customers"""
    is_joined = SerializerMethodField()
    is_winner = SerializerMethodField()
    vendor_name = SerializerMethodField()
    winner = QoraaWinnerSerializer(read_only=True)
    food = ReadOnlyField(source="food.image.url")
    joiners_count = SerializerMethodField()

    class Meta:
        model = Qoraa
        fields = [
            "id",
            "start",
            "end",
            "status",
            "winner",
            "food",
            "title",
            "created_at",
            "vendor",
            "vendor_name",
            "is_platform",
            "joiners_count",
            "is_joined",
            "is_winner"
        ]

    def get_vendor_name(self, obj):
        if obj.vendor:
            return obj.vendor.vendor_name
        return "Zayton"

    def get_joiners_count(self, obj):
        if obj.joiners:
            return obj.joiners.count()
        return 0

    def get_is_joined(self, obj):
        user = self.context["request"].user
        joiners = {j.id for j in obj.joiners.all()}
        if user.is_authenticated:
            return user.id in joiners
        return False

    def get_is_winner(self, obj):
        user = self.context["request"].user
        if user.is_authenticated and obj.winner:
            return user.id == obj.winner.id
        return False

class VendorQoraaFoodSerializer(ModelSerializer):
    prices = SerializerMethodField("get_prices")
    class Meta:
        model = Food
        fields = ["id", "name", "prices", "image"]

    def get_prices(self, instance):
        return [i for i in instance.prices if i >= MIN_QORAA_PRICE_VALUE]


class VendorQoraaSerializer(ModelSerializer):
    """THis is used by vendor to create/update their qoraas"""
    winner = QoraaWinnerSerializer(read_only=True)
    food_data = SerializerMethodField(method_name="get_food_data")
    joiners_count = SerializerMethodField(method_name="get_joiners_count")
    class Meta:
        model = Qoraa
        fields = [
            "id",
            "food",
            "food_data",
            "title",
            "created_at",
            "start",
            "end",
            "status",
            "winner",
            "joiners_limit",
            "price_value",
            "joiners_count"
        ]
        read_only_fields = [
            "created_at",
            "winner",
            "status",
            "food_data",
            "joiners_count",
        ]

    def create(self, validated_data):
        price_value = validated_data.get("price_value", None)
        joiners_limit = validated_data.get("joiners_limit", 0)
        try:
            food = validated_data.get("food", None)
            if not price_value:
                raise ValidationError("provide_price_value")
            if not price_value in food.prices:
                raise ValidationError("price_value_not_in_prices")
            if price_value < MIN_QORAA_PRICE_VALUE:
                raise ValidationError("price_value_is_low")
            if joiners_limit < 100:
                raise ValidationError("min_joinsers_limit_100")
            if validated_data["start"] >= validated_data["end"]:
                raise ValidationError("start_must_be_before_end")
            if validated_data["start"] < timezone.now() - timezone.timedelta(minutes=1):
                validated_data["start"] = timezone.now() - timezone.timedelta(minutes=1)
                # raise ValidationError("start_must_be_in_future")
            if validated_data["end"] <= timezone.now():
                raise ValidationError("end_must_be_in_future")

            validated_data["vendor"] = Vendor.objects.get(
                id=self.context.get("vendor", None)
            )
            validated_data["price_value"] = price_value
            qoraa = Qoraa.objects.create(**validated_data)
            # ---- settting celery task to update status ----
            start_vendor_qoraa.apply_async((qoraa.id,), eta=qoraa.start)
            end_vendor_qoraa.apply_async((qoraa.id,), eta=qoraa.end)
            return qoraa
        except Exception as e:
            logger.exception(f"Error in creating qoraa for vendor: {e}")
            return


    def get_food_data(self, instance):
        ser = VendorQoraaFoodSerializer(instance.food)  # to avoid n+1 query
        return ser.data

    def get_joiners_count(self, instance):
        count = instance.joiners.count()
        return count