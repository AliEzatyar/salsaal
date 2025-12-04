from rest_framework.serializers import ModelSerializer, SerializerMethodField, ReadOnlyField
from accounts.models import User, UserProfile
from qoraa.models import Qoraa, QoraaVendor


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
            "is_joined"
        ]
        read_only_fields = fields

    def get_joiners_count(self, obj):
        return obj.joiners.count()

    def get_is_joined(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.joiners.filter(pk=user.pk).exists()
        return False


class QoraaWinnerSerializer(ModelSerializer):
    picture = SerializerMethodField()

    class Meta:
        model = User
        fields = ["id","name", "picture"]

    def get_picture(self, obj):
        try:
            profile = UserProfile.objects.get(user=obj)
            if profile.picture:
                return profile.picture.url
            return None
        except UserProfile.DoesNotExist:
            return None


class QoraaReadOnlySerializer(ModelSerializer):
    is_joined = SerializerMethodField()
    vendor_name = SerializerMethodField()
    winner = QoraaWinnerSerializer(read_only=True)
    food  = ReadOnlyField(source='food.image.url')
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
        if user.is_authenticated:
            return obj.joiners.filter(pk=user.pk).exists()
        return False


class QoraaVendorSerializer(ModelSerializer):

    class Meta:
        model = QoraaVendor
        fields = [
            "id",
            "title",
            "food_items",
            "is_active",
            "price_value",
            "vendor",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "vendor"]
