from rest_framework import serializers
from .models import Vendor
from accounts.serializers import UserProfileSerializer


class VendorSerializer(serializers.ModelSerializer):
    rating = serializers.SerializerMethodField("get_rating")
    user_profile = UserProfileSerializer()

    class Meta:
        model = Vendor
        fields = [
            "user",
            "user_profile",
            "vendor_name",
            "vendor_license",
            "categories",
            "city",
            "is_approved",
            "created_at",
            "rating",
        ]
        read_only_fields = ['user','is_approved','created_at','rating']

    def get_rating(self, obj):
        """returns total rating of the vendor"""
        return obj.overall_rating()

    def update(self, instance, validated_data):
        """overriding to apply user profile update together with vendor"""
        # updating user profile if provided
        user_profile_data = validated_data.pop("user_profile", None)
        if user_profile_data:
            existing_user_profile = instance.user_profile
            for attr, value in user_profile_data.items():
                setattr(existing_user_profile, attr, value)
            existing_user_profile.save()

        # updating vendor itself
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance
