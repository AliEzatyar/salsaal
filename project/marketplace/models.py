from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from django.template.loader import render_to_string

# Create your models here.


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    show_on_home = models.BooleanField(default=True)
    class Meta:
        verbose_name = "category"
        verbose_name_plural = "categories"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name



class Food(models.Model):
    vendor = models.ForeignKey(
        "vendor.Vendor",
        on_delete=models.CASCADE,
        related_name="foods",
        db_index=True,
    )
    name = models.CharField(max_length=60, db_index=True)
    price = models.DecimalField(max_digits=6, decimal_places=0, db_index=True)
    category = models.ForeignKey(
        "marketplace.Category",
        on_delete=models.CASCADE,
        related_name="foods",
        db_index=True,
    )
    description = models.TextField(max_length=250, blank=True, null=True)
    image = models.ImageField(upload_to="foods/", blank=True, null=True)
    is_available = models.BooleanField(default=True, db_index=True)
    modified = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    rating = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "food"
        verbose_name_plural = "foods"
        ordering = ["-modified"]

    def rating_form(self):
        html = render_to_string(
            "marketplace/rating_form.html",
            context={"object_id": self.pk, "type": "food"},
        )
        return html

    def overall_rating(self):
        """this utility method returns the rating average"""
        ratings = Rating.objects.filter(object_id=self.pk).values_list('rating')
        ratings = [r[0] for r in ratings]
        if len(ratings) == 0:
            return 0
        self.rating = sum(ratings) / len(ratings)
        self.save()
        return sum(ratings)/len(ratings)

    def __str__(self):
        return self.name


class Rating(models.Model):
    """rating models is used for both food and vendor models for now"""

    RATING_CHOICES = ((1, 1), (2, 2), (3, 3), (4, 4), (5, 5))
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="+"
    )
    comment = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rating = models.PositiveSmallIntegerField(default=0, choices=RATING_CHOICES)
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE,null=True
    )
    object_id = models.IntegerField(null=True)
    related_obj = GenericForeignKey("content_type", "object_id")
    enabled= models.BooleanField(default=True)
    
    @property
    def get_rating(self):
        return [i for i in range(self.rating)]
