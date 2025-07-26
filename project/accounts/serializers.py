from rest_framework.serializers import ModelSerializer, ValidationError, DateTimeField
from vendor.models import Vendor
from .models import User, UserProfile, CUSTOMER
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
import jwt
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


class UserDetailSerializer(ModelSerializer):
    profile = UserProfileSerializer()
    
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "profile"
            
        ]
        read_only_fields = [
            "id",
            "email",
        ]  # Prevent updating the email, seperate view is made
    
    def update(self, instance, validated_data):
        # saving user object
        profile_data = validated_data.pop("profile",None)
        user_data = validated_data
        for attr,val in user_data.items():
            setattr(instance,attr,val)
        instance.save()
        
        # getting profile object
        if profile_data:
            profile = instance.profile
            profile_serializer = self.fields['profile']
            profile_serializer.update(profile,profile_data)            

        return instance
        

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

    def validate(self, attrs):
        # validates whether the refresh tokem is correct
        data = super().validate(attrs)
        # create refresh object using the entered refresh token
        refresh = RefreshToken(data["refresh"])
        # create new access object, add user_id and role to it assign it instead of older one in data
        access = AccessToken()
        access["user_id"] = refresh["user_id"]
        role = User.objects.get(id=access["user_id"]).role
        access["role"] = role  # fallback
        # re-assiging the access token which contains role
        data["access"] = str(access)
        data["refresh"] =str(refresh)
        return data






