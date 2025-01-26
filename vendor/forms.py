from django import forms
from accounts.forms import only_image_validator
from catalog.models import Category, Product
from vendor.models import Rating, Vendor
from vendor.utils import slugify_persian


class VendorForm(forms.ModelForm):
    vendor_license = forms.FileField(
        widget=forms.FileInput(attrs={"class": "btn-primary"}),
        validators=[only_image_validator],
    )

    class Meta:
        model = Vendor
        fields = ["vendor_license", "vendor_name"]


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]


class ProductForm(forms.ModelForm):
    image = forms.FileField(
        widget=forms.FileInput(attrs={"class": "btn-primary"}),
        validators=[only_image_validator],
    )

    class Meta:
        model = Product
        exclude = ["vendor", "slug", "modified", "created_at"]


class RatingForm(forms.ModelForm):
    
    class Meta:
        model = Rating
        exclude = ["vendor","customer","created_at"]
        