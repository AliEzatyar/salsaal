from django import forms
from accounts.forms import only_image_validator
from marketplace.models import Category, Product
from vendor.models import Rating, Vendor
from vendor.utils import slugify_persian
from django.core.exceptions import ValidationError


class VendorForm(forms.ModelForm):
    """For for creating and updating vendor"""

    vendor_license = forms.FileField(
        widget=forms.FileInput(attrs={"class": "btn-primary"}),
        validators=[only_image_validator],
    )
    vendor_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "common-input"})
    )

    class Meta:
        model = Vendor
        fields = ["vendor_license", "vendor_name"]


class ProductForm(forms.ModelForm):
    """form for product edit/create"""

    image = forms.FileField(
        widget=forms.FileInput(attrs={"class": "btn-primary"}),
        validators=[only_image_validator],
    )
    name = forms.CharField(widget=forms.TextInput(attrs={"class": "common-input"}))
    price = forms.IntegerField(
        widget=forms.NumberInput(attrs={"class": "common-input"})
    )
    description = forms.CharField(
        widget=forms.TextInput(attrs={"class": "common-input"})
    )

    def clean_name(self):
        """this clean method enables unique name validation"""
        data = self.cleaned_data["name"]
        if Product.objects.filter(name=data).exclude(pk=self.instance.pk).exists():
            raise ValidationError("این نام محصول قبلا استفاده شده")
        return data

    class Meta:
        model = Product
        exclude = ["vendor", "slug", "modified", "created_at"]


class RatingForm(forms.ModelForm):

    class Meta:
        model = Rating
        exclude = ["vendor", "customer", "created_at"]
