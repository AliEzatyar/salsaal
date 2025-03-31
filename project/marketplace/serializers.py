from rest_framework import serializers


from marketplace.models import Product, Rating

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        exclude = ['object_id','content_type']