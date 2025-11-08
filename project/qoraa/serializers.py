from rest_framework.serializers import ModelSerializer, SerializerMethodField
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
        ]
        read_only_fields = fields

    def get_joiners_count(self, obj):
        return obj.joiners.count()


class QoraaReadOnlySerializer(ModelSerializer):
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
            "is_platform",  
            ] 


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
        read_only_fields = ['id', 'created_at','vendor']
