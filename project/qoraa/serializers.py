from rest_framework.serializers import ModelSerializer
from project.qoraa.models import QoraaVendor


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
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        validated_data['vendor'] = self.context.get('vendor')
        return super().create(validated_data)
