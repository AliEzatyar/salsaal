from django import forms
from .models import User


class UserRegForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())
    confirm = forms.CharField(widget=forms.PasswordInput())

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
        if cd['password'] != cd['confirm']:
            raise forms.ValidationError(
                "Passwords does not match!"
            )