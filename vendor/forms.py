from django import forms
from accounts.forms import only_image_validator
from vendor.models import Vendor

class VendorForm(forms.ModelForm):
    vendor_license = forms.FileField(widget=forms.FileInput(attrs={"class": "btn-primary"}),validators = [only_image_validator])

    class Meta:
        model = Vendor
        fields = ["vendor_license","vendor_name"]
        