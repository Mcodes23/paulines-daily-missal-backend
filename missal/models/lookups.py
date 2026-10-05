from django.db import models
from .base import BaseUUIDModel


class LiturgicalColor(models.TextChoices):
    """Canonical liturgical colors."""
    GREEN = "green", "Green"
    PURPLE = "purple", "Purple"
    WHITE = "white", "White"
    RED = "red", "Red"
    ROSE = "rose", "Rose"
    BLACK = "black", "Black"
    GOLD = "gold", "Gold"


class YearCycle(BaseUUIDModel):
    """Sunday reading cycle (A/B/C)."""
    code = models.CharField(max_length=1, unique=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Sunday cycle"
        verbose_name_plural = "Sunday cycles"
        indexes = [models.Index(fields=["code"])]

    def __str__(self):
        return self.code


class WeekdayCycle(BaseUUIDModel):
    """Weekday reading cycle (I/II)."""
    code = models.CharField(max_length=2, unique=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Weekday cycle"
        verbose_name_plural = "Weekday cycles"
        indexes = [models.Index(fields=["code"])]

    def __str__(self):
        return self.code


class ReadingKind(BaseUUIDModel):
    """
    Types of readings for Mass (e.g., First Reading, Second Reading, Gospel).
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    order_hint = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order_hint", "name"]
        indexes = [models.Index(fields=["order_hint"]), models.Index(fields=["slug"])]

    def __str__(self):
        return self.name
