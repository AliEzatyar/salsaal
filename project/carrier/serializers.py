from rest_framework import serializers

from accounts.models import CARRIER, User, UserProfile
from .models import Carrier
from order.models import Order
from vendor.models import Vendor
class CarrierSerializer(serializers.ModelSerializer):
    vendor = serializers.PrimaryKeyRelatedField(read_only=True)
    email = serializers.EmailField(max_length=60, write_only=True, required=False)

    class Meta:
        model = Carrier
        fields = [
            "email",
            "user",
            "user_profile",
            "id_document",
            "vendor",
        ]
        read_only_fields= ["user","user_profile"]
        
    def create(self, validated_data):
        """overriding to handle automatic vendor and name save"""
        vendor = Vendor.objects.get(id=self.context['vendor'])
        validated_data["vendor"] = vendor
        email = validated_data.pop("email",None)
        account = User.objects.filter(email=email).first()
        if not account:
            raise serializers.ValidationError({"error":"no_account_found_by_that_email"})
        profile = UserProfile.objects.get(user=account)
        validated_data["user_profile"] = profile
        validated_data["user"] = account
        if hasattr(account,"carrier") or account.role == CARRIER:
            # update
            instance = Carrier.objects.update(**validated_data)
            return instance
        account.role  = CARRIER
        account.save()
        instance = Carrier.objects.create(**validated_data)
        return instance


class CarrierOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField("get_customer_name")
    class Meta:
        model = Order
        fields = [
            "customer_name",
            "total_items",
            "total_price",
            "status",
            "paid",
            "created",
        ]

    def get_customer_name(self, obj):
        return obj.user.first_name + obj.user.last_name
