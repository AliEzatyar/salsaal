from rest_framework.serializers import ModelSerializer, ValidationError
from order.models import Reward
from vendor.models import Vendor
from .models import Device, User, UserProfile, CUSTOMER, get_token_valid_after
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework import serializers
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.settings import api_settings

class UserCreationSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["full_name", "phone_number"]

    def create(self, validated_data):
        # overriden for password hashing
        cd = validated_data
        user = User(**cd)
        user.role = CUSTOMER
        user.save()
        return user

    def validate(self, attrs):
        super().validate(attrs)
        phone_number = attrs.get("phone_number", None)
        if phone_number:
            okay = True
            if not phone_number.startswith("+"):
                okay = False
            if not phone_number[1:].isnumeric():
                okay = False
            if not okay:
                raise ValidationError({"detail": "phone_invalid"})
        return attrs


class UserProfileSerializer(ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["picture", "city", "address", "latitude", "longitude"]

    def update(self, instance, validated_data):
        pic = validated_data.get("picture", None)
        if pic:
            ext = pic.name.split(".")[-1]
            valid_extensions = ["jpg", "png", "jpeg"]
            if ext.lower() not in valid_extensions:
                raise ValidationError(
                    {"error": "file extension must be jpg, png, jpeg"}
                )
        # re-assigning the valid data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class UserProfileCreationSerializer(ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["pf_lang", "country", "city", "latitude", "longitude", "address"]

    def create(self, validated_data):
        latitude, longitude = validated_data["latitude"], validated_data["longitude"]
        try:
            float(latitude)
            float(longitude)
        except:
            print("lat and lon invalid",latitude,longitude,"--")
            raise ValidationError("provide_correct_lat_lon")
        return super().create(validated_data)

    def save(self, **kwargs):
        return super().save(**kwargs)


class UserDetailSerializer(ModelSerializer):
    profile = UserProfileSerializer()

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "phone_number", "profile", "created_date"]
        read_only_fields = [
            "id",
            "email",
            "created_date",
        ]  # Prevent updating the email, seperate view is made

    def update(self, instance, validated_data):
        # saving user object
        profile_data = validated_data.pop("profile", None)
        user_data = validated_data
        for attr, val in user_data.items():
            setattr(instance, attr, val)
        instance.save()

        # getting profile object
        if profile_data:
            profile = instance.profile
            profile_serializer = self.fields["profile"]
            profile_serializer.update(profile, profile_data)

        return instance


class DeviceSerializer(ModelSerializer):
    """this is used to save device token for out-of-app notifications"""

    class Meta:
        model = Device
        fields = ["user", "token"]


class VendorCreateSerializer(ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["vendor_name"]


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # adding role
        token["role"] = user.role
        return token


class RoleTokenRefreshSeriaizer(TokenRefreshSerializer):
    """
    overriden to invalidate pre-access tokens 
    when getting new access token with refresh token
    """
    def validate(self, attrs):
        # validates whether the refresh token is correct and generates new access token
        tokens = super().validate(attrs)
        decoded_access = token_backend.decode(tokens["access"])
        user = User.objects.get(id=int(decoded_access["user_id"]))
        user.token_valid_after = get_token_valid_after()
        user.save()
        return tokens


class RewardSerializer(ModelSerializer):
    vendor_name = serializers.ReadOnlyField(source="vendor.vendor_name")

    class Meta:
        model = Reward
        fields = ["amount", "vendor_name", "vendor"]
        read_only_fields = ["__all__"]
