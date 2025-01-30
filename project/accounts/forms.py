from os import path
from django import forms
from django.core.exceptions import ValidationError
from vendor.models import Vendor
from .models import User, UserProfile
from django.core.files.uploadedfile import InMemoryUploadedFile


def only_image_validator(filename: InMemoryUploadedFile):
    ext = path.splitext(filename.name)[1]

    valid_extensions = [".jpg", ".png", ".jpeg"]
    if ext.lower() not in valid_extensions:
        raise ValidationError("باید فایل عکس انتخاب کنید")


class UserRegForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "common-input"})
    )
    confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "common-input"})
    )
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "common-input"})
    )
    last_name = forms.CharField(widget=forms.TextInput(attrs={"class": "common-input"}))
    username = forms.CharField(widget=forms.TextInput(attrs={"class": "common-input"}))
    email = forms.CharField(widget=forms.TextInput(attrs={"class": "common-input"}))

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "username",
            "password",
            "email",
        ]

    def clean(self):
        cd = super(UserRegForm, self).clean()
        if cd["password"] != cd["confirm"]:
            raise forms.ValidationError("Passwords does not match!")


class VendorRegForm(forms.ModelForm):
    vendor_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "common-input"})
    )

    class Meta:
        model = Vendor
        fields = ("vendor_name", "vendor_license")


class UserProfileForm(forms.ModelForm):
    picture = forms.FileField(
        widget=forms.FileInput(attrs={"class": "btn-primary"}),
        validators=[only_image_validator],
    )
    cover = forms.FileField(
        widget=forms.FileInput(attrs={"class": "btn-primary"}),
        validators=[only_image_validator],
    )
    lattitude = forms.CharField(widget=forms.TextInput(attrs={"readonly": "readonly"}))
    longtitiude = forms.CharField(
        widget=forms.TextInput(attrs={"readonly": "readonly"})
    )
    address = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "placeholder": "start typing...",
                "required": "requried",
                "class": "common-input",
            }
        )
    )
    city = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "placeholder": "start typing...",
                "required": "requried",
                "class": "common-input",
            }
        )
    )

    class Meta:
        model = UserProfile
        fields = ["picture", "cover", "address", "city", "lattitude", "longtitiude"]
