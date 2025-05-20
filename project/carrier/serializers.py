from rest_framework import serializers
from .models import Carrier

class CarrierSerializer(serializers.ModelSerializer):
    
    
    vendor = serializers.PrimaryKeyRelatedField(read_only=True)
    email = serializers.EmailField(max_length=60, write_only=True, required=False)
    name = serializers.SerializerMethodField("get_carrier_name")
    
    
    class Meta:
        model = Carrier
        fields = [
            "id",
            "is_active",
            "id_document",
            "email",
            "vendor",
            "user",
            "user_profile",
            "name"
        ]
        read_only_fields= ["id","user","user_profile","email","vendor","name"]
        

    def get_carrier_name(self,obj):
        return obj.user.get_full_name()
    
