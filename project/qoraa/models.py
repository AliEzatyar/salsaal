from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.


class Qoraa(models.Model):
    hour = models.TimeField
    winner = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="+",
        blank=True,
        null=True,
    )
    joiners = models.ManyToManyField(to=get_user_model(), related_name="qoraas_joined")
    title = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
