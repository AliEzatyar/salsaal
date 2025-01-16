import rest_framework.serializers as ser
from ..models import User
from ..models import CUSTOMER


class UserCreationSerializer(ser.ModelSerializer):
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


class UserDetailSerializer(ser.ModelSerializer):

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
        read_only_fields = ["id", "email"]  # Prevent updating the email, seperate view is made
