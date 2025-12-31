from django.db import models
from django.urls import reverse
from django.utils import timezone

# Create your models here.


class Category(models.Model):
    category_name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    description = models.TextField(max_length=255, blank=True)

    # Parent = None → Male/Female | Parent = Category → Chain/Leather/Smartwatch
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    is_listed = models.BooleanField(
        default=True
    )  # soft delete (True=active, False=deleted)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "category"
        verbose_name_plural = "categories"
        ordering = ["-created_at"]

    def get_url(self):
        return reverse("products_by_category", args=[self.slug])

    def __str__(self):
        return self.category_name
