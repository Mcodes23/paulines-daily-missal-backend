from django.db import models
from django.core.exceptions import ValidationError
from .base import BaseUUIDModel
from .lookups import LiturgicalColor, YearCycle, WeekdayCycle
from .structure import WeekTitle, DayTitle, LiturgicalDayType, LiturgicalSeason


class LiturgicalDay(BaseUUIDModel):
    """
    Central daily entity tying together readings, psalms, acclamations, and prayers.
    """
    title_ref = models.ForeignKey(DayTitle, on_delete=models.PROTECT, related_name="days")
    theme = models.TextField(blank=True, null=True)
    liturgical_week = models.ForeignKey(WeekTitle, on_delete=models.PROTECT, related_name="days")
    liturgical_day_type = models.ForeignKey(LiturgicalDayType, on_delete=models.PROTECT, related_name="days")
    season = models.ForeignKey(LiturgicalSeason, on_delete=models.PROTECT, related_name="days")
    sunday_cycles = models.ManyToManyField(YearCycle, blank=True)
    weekday_cycles = models.ManyToManyField(WeekdayCycle, blank=True)
    date = models.DateField(blank=True, null=True)
    override_color = models.CharField(max_length=12, choices=LiturgicalColor.choices, blank=True, null=True)

    class Meta:
        ordering = ["date", "title_ref__name"]
        verbose_name = "Liturgical day"
        verbose_name_plural = "Liturgical days"
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["season"]),
            models.Index(fields=["liturgical_day_type"]),
        ]

    def __str__(self):
        return self.title_ref.name

    @property
    def effective_color(self):
        """Returns effective color, considering overrides and season."""
        return self.override_color or self.liturgical_day_type.color or self.season.color

                
    def clean(self):
        super().clean()

        # ───────────────────────────────
        # 🩹 Skip strict validation in unsaved or admin form context
        # ───────────────────────────────
        import inspect

        # When running from the admin, inline formsets aren't yet committed
        if not self.pk or any("admin" in frame.filename for frame in inspect.stack()):
            return

        # ───────────────────────────────
        # ✅ Require Second Reading only for certain day types
        # ───────────────────────────────
        if getattr(self.liturgical_day_type, "requires_second_reading", False):
            has_second = self.readings.filter(kind__slug="second-reading").exists()
            if not has_second:
                raise ValidationError("This day type requires a Second Reading.")

        # ───────────────────────────────
        # ✅ Ensure every reading has at least one cycle
        # ───────────────────────────────
        for r in self.readings.all():
            if r.sunday_cycles.count() == 0 and r.weekday_cycles.count() == 0:
                raise ValidationError(
                    f"Reading '{r}' must have at least one cycle (A/B/C or I/II)."
                )
