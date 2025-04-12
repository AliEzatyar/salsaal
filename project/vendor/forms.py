from django import forms
from accounts.forms import only_image_validator
from marketplace.models import Category, Food
from vendor.models import Vendor
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


class FoodForm(forms.ModelForm):
    """form for food edit/create"""
    image = forms.FileField(
        widget=forms.FileInput(attrs={"class": "btn-primary"}),
        validators=[only_image_validator],
    )
    name = forms.CharField(widget=forms.TextInput(attrs={"class": "common-input"}))
    price = forms.IntegerField(
        widget=forms.NumberInput(attrs={"class": "common-input"})
    )
    description = forms.CharField(
        widget=forms.TextInput(attrs={"class": "common-input text "})
    )
    
    def clean_name(self):
        """this clean method enables unique name validation"""
        data = self.cleaned_data["name"]
        if Food.objects.filter(name=data).exclude(pk=self.instance.pk).exists():
            raise ValidationError("این نام محصول قبلا استفاده شده")
        return data

    class Meta:
        model = Food
        exclude = ["vendor", "modified", "created_at","sold_amount"]
