from django.db import models
from .base import BaseUUIDModel
from .day import LiturgicalDay


class UniversalPrayer(BaseUUIDModel):
    """
    The Prayer of the Faithful / Intercessions for the Mass.
    Can have multiple ordered sets and alternative versions.
    """
    day = models.ForeignKey(
        LiturgicalDay,
        on_delete=models.CASCADE,
        related_name="universal_prayers"
    )
    introduction = models.TextField(blank=True, null=True)
    petitions = models.JSONField(default=list, blank=True)
    conclusion = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    alternatives = models.ManyToManyField("self", symmetrical=False, blank=True)

    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["day", "order"])]

    def __str__(self):
        return f"Universal Prayer {self.order} — {self.day}"


class Preface(BaseUUIDModel):
    """
    Preface texts used in the Eucharistic Prayer.
    Linked to multiple days and organized alphabetically.
    """
    title = models.CharField(max_length=180, unique=True)
    note = models.CharField(max_length=180, blank=True, null=True)
    body = models.TextField()

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class DayPreface(BaseUUIDModel):
    """
    Bridge model connecting Prefaces to specific Liturgical Days.
    Allows multiple ordered prefaces for one day (e.g., seasonal variations).
    """
    day = models.ForeignKey(
        LiturgicalDay,
        on_delete=models.CASCADE,
        related_name="day_prefaces"
    )
    preface = models.ForeignKey(
        Preface,
        on_delete=models.PROTECT,
        related_name="use_days"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        unique_together = [("day", "preface")]
        indexes = [models.Index(fields=["day", "order"])]

    def __str__(self):
        return f"{self.preface.title} (Day {self.day})"
