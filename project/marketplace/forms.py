from django import forms
from marketplace.models import Rating


class RatingForm(forms.ModelForm):

    class Meta:
        model = Rating
        fields = ["comment", "rating"]
