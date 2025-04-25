from rest_framework import serializers

from accounts.models import CARRIER, SHOP, User, UserProfile
from .models import Carrier
from order.models import Order
from vendor.models import Vendor

class CarrierSerializer(serializers.ModelSerializer):
    
    
    vendor = serializers.PrimaryKeyRelatedField(read_only=True)
    email = serializers.EmailField(max_length=60, write_only=True, required=False)
    name = serializers.SerializerMethodField("get_carrier_name")
    
    
    class Meta:
        model = Carrier
        fields = [
            "id",
            "email",
            "is_active",
            "id_document",
            "vendor",
            "user",
            "user_profile",
            "name"
        ]
        read_only_fields= ["user","user_profile","email"]
        

    def get_carrier_name(self,obj):
        return obj.user.get_full_name()
    
