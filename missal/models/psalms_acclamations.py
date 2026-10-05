from django.db import models
from .base import BaseUUIDModel
from .lookups import YearCycle, WeekdayCycle
from .day import LiturgicalDay


class ResponsorialPsalm(BaseUUIDModel):
    """Psalm for the day, with optional alternate versions."""
    day = models.OneToOneField(
        LiturgicalDay,
        on_delete=models.CASCADE,
        related_name="responsorial_psalm"
    )
    reference = models.CharField(max_length=120)
    response = models.CharField(max_length=200)
    verses = models.TextField(
        blank=True,
        help_text="Enter one verse per line."
    )
    order = models.PositiveIntegerField(default=0)
    sunday_cycles = models.ManyToManyField(YearCycle, blank=True)
    weekday_cycles = models.ManyToManyField(WeekdayCycle, blank=True)

    class Meta:
        indexes = [models.Index(fields=["day"])]

    def __str__(self):
        return f"Psalm — {self.reference}"


class ResponsorialPsalmAltItem(BaseUUIDModel):
    """Alternative psalms for cycle-specific use."""
    psalm = models.ForeignKey(
        ResponsorialPsalm,
        on_delete=models.CASCADE,
        related_name="alternatives_items"
    )
    reference = models.CharField(max_length=120)
    response = models.CharField(max_length=200)
    verses = models.TextField(
        blank=True,
        help_text="Enter one verse per line."
    )
    order = models.PositiveIntegerField(default=0)
    sunday_cycles = models.ManyToManyField(YearCycle, blank=True)
    weekday_cycles = models.ManyToManyField(WeekdayCycle, blank=True)

    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["psalm", "order"])]

    def __str__(self):
        return f"Alt {self.order} for {self.psalm.reference}"


class GospelAcclamation(BaseUUIDModel):
    """Alleluia verse or alternative acclamation."""
    day = models.OneToOneField(
        LiturgicalDay,
        on_delete=models.CASCADE,
        related_name="gospel_acclamation"
    )
    reference = models.CharField(max_length=120, blank=True, null=True)
    primary_acclamation = models.CharField(max_length=50, default="Alleluia")
    verse = models.TextField()

    class Meta:
        indexes = [models.Index(fields=["day"])]

    def __str__(self):
        return f"Gospel Acclamation — {self.primary_acclamation}"


class GospelAcclamationAltItem(BaseUUIDModel):
    """Alternative acclamations (for different cycles)."""
    acclamation = models.ForeignKey(
        GospelAcclamation,
        on_delete=models.CASCADE,
        related_name="alternatives_items"
    )
    reference = models.CharField(max_length=120, blank=True, null=True)
    primary_acclamation = models.CharField(max_length=50, default="Alleluia")
    verse = models.TextField()
    order = models.PositiveIntegerField(default=0)
    sunday_cycles = models.ManyToManyField(YearCycle, blank=True)
    weekday_cycles = models.ManyToManyField(WeekdayCycle, blank=True)

    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["acclamation", "order"])]

    def __str__(self):
        return f"Alt {self.order} for {self.acclamation}"
