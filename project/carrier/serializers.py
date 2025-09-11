from rest_framework import serializers
from .models import Carrier

class CarrierSerializer(serializers.ModelSerializer):
    vendor = serializers.PrimaryKeyRelatedField(read_only=True)
    name = serializers.SerializerMethodField("get_carrier_name")
    class Meta:
        model = Carrier
        fields = [
            "id",
            "is_active",
            "vendor",
            "user",
            "user_profile",
            "id_document",
            "name"
        ]
        read_only_fields= ["id","user","user_profile","email","vendor","name"]
        

    def get_carrier_name(self,obj):
        return obj.user.get_full_name()
    
