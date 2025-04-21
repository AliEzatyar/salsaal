from rest_framework.serializers import ModelSerializer, ValidationError
from vendor.models import Vendor
from .models import User, UserProfile
from .models import CUSTOMER

class UserCreationSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "username",
            "password",
            "email",
        ]

    def create(self, validated_data):
        # overriden for password hashing
        cd = validated_data
        user = User(**cd)
        user.set_password(cd["password"])
        user.role = CUSTOMER
        user.save()

        return user


class UserProfileSerializer(ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["picture", "city", "address", "lattitude", "longitude"]

    def update(self, instance, validated_data):
        pic = validated_data.get("picture",None)
        if pic:
            ext = pic.name.split(".")[-1]
            valid_extensions = ["jpg", "png", "jpeg"]
            if ext.lower() not in valid_extensions:
                raise ValidationError({"error": "file extension must be jpg, png, jpeg"})
        # re-assigning the valid data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class UserDetailSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
        ]
        read_only_fields = [
            "id",
            "email",
        ]  # Prevent updating the email, seperate view is made


class VendorCreateSerializer(ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["vendor_name"]


class VendorManageSerializer(ModelSerializer):
    user = UserDetailSerializer()
    user_profile = UserProfileSerializer()

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_name",
            "vendor_license",
            "user",
            "user_profile",
            "created_at",
        ]
        read_only_fields = ["id"]
