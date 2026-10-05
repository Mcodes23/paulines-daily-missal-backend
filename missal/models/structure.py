from django.db import models
from .base import BaseUUIDModel
from .lookups import LiturgicalColor


class LiturgicalSeason(BaseUUIDModel):
    """
    Seasons of the Church year (Advent, Lent, Easter, Ordinary Time, etc.).
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    color = models.CharField(max_length=12, choices=LiturgicalColor.choices, default=LiturgicalColor.GREEN)
    key_figures = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["color"]), models.Index(fields=["created_at"])]

    def __str__(self):
        return self.name


class LiturgicalDayType(BaseUUIDModel):
    """
    Hierarchical rank of the liturgical day (e.g., Solemnity, Feast, Memorial).
    """
    name = models.CharField(max_length=50, unique=True)
    rank_num = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    color = models.CharField(max_length=12, choices=LiturgicalColor.choices, blank=True, null=True)
    requires_second_reading = models.BooleanField(default=False)

    class Meta:
        ordering = ["rank_num", "name"]
        indexes = [models.Index(fields=["requires_second_reading"]), models.Index(fields=["color"])]

    def __str__(self):
        suffix = f" · {self.rank_num}" if self.rank_num is not None else ""
        return f"{self.name}{suffix}"


class WeekTitle(BaseUUIDModel):
    """Weeks inside a liturgical season (e.g., 'First Week in Ordinary Time')."""
    name = models.CharField(max_length=120, unique=True)
    season = models.ForeignKey(LiturgicalSeason, on_delete=models.PROTECT, related_name="week_titles")
    week_number = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ["season__name", "week_number", "name"]
        indexes = [models.Index(fields=["season", "week_number"])]

    def __str__(self):
        return self.name


class DayTitle(BaseUUIDModel):
    """Each day in the week within the liturgical year."""
    WEEKDAYS = [
        ("Mon", "Monday"), ("Tue", "Tuesday"), ("Wed", "Wednesday"),
        ("Thu", "Thursday"), ("Fri", "Friday"), ("Sat", "Saturday"), ("Sun", "Sunday"),
    ]
    name = models.CharField(max_length=180, unique=True)
    week = models.ForeignKey(WeekTitle, on_delete=models.PROTECT, related_name="day_titles")
    weekday = models.CharField(max_length=3, choices=WEEKDAYS)
    default_day_type = models.ForeignKey(LiturgicalDayType, on_delete=models.PROTECT, related_name="default_for_titles")

    class Meta:
        unique_together = [("week", "weekday")]
        ordering = ["week__season__name", "week__week_number", "weekday"]
        indexes = [models.Index(fields=["week", "weekday"])]

    def __str__(self):
        return self.name
