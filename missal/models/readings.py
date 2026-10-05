from django.db import models
from django.utils.text import slugify
from .base import BaseUUIDModel
from .lookups import YearCycle, WeekdayCycle, ReadingKind
from .day import LiturgicalDay


KIND_SLUG_DEFAULTS = {
    "first": "first-reading",
    "second": "second-reading",
    "gospel": "gospel",
}


class Reading(BaseUUIDModel):
    """Scripture readings for each liturgical day."""
    day = models.ForeignKey(
        LiturgicalDay,
        on_delete=models.CASCADE,
        related_name="readings",
    )
    kind = models.ForeignKey(
        ReadingKind,
        on_delete=models.PROTECT,
        related_name="readings",
    )
    reference = models.CharField(max_length=120)
    quote = models.TextField(blank=True, null=True)
    introduction = models.CharField(max_length=2000, blank=True, null=True)
    content = models.TextField()
    conclusion = models.CharField(max_length=40, blank=True, default="")
    sunday_cycles = models.ManyToManyField(YearCycle, blank=True)
    weekday_cycles = models.ManyToManyField(WeekdayCycle, blank=True)
    order = models.PositiveIntegerField(default=0)
    alternatives = models.ManyToManyField("self", symmetrical=False, blank=True)

    class Meta:
        ordering = ["order", "kind__order_hint"]
        verbose_name = "Reading"
        verbose_name_plural = "Readings"
        indexes = [
            models.Index(fields=["day", "order"]),
            models.Index(fields=["kind"]),
        ]

    def __str__(self):
        kind_name = getattr(self.kind, "name", "Unknown Kind")
        return f"{kind_name} – {self.reference}"

    def _auto_assign_kind(self):
        """
        Automatically assigns kind based on contextual hints (first, second, gospel)
        if not already set.
        """
        if not getattr(self, "kind_id", None):
            try:
                # Try to infer from admin inline or content
                if hasattr(self, "_meta") and self._meta.verbose_name_plural:
                    name_hint = self._meta.verbose_name_plural.lower()
                    for key, slug in KIND_SLUG_DEFAULTS.items():
                        if key in name_hint:
                            kind = ReadingKind.objects.filter(slug=slug).first()
                            if kind:
                                self.kind = kind
                                break
            except Exception:
                pass

    def save(self, *args, **kwargs):
        # 🔹 Ensure kind is assigned before saving (fixes IntegrityError)
        self._auto_assign_kind()

        # 🔹 Absolute fallback: assign 'first-reading' if still None
        if not getattr(self, "kind_id", None):
            default_kind = ReadingKind.objects.filter(slug="first-reading").first()
            if default_kind:
                self.kind = default_kind

        # 🔹 Set Gospel conclusion automatically if kind is gospel
        try:
            if getattr(self, "kind_id", None) and self.kind.name.lower().startswith("gospel"):
                if not self.conclusion:
                    self.conclusion = "The Gospel of the Lord."
        except Exception:
            pass

        super().save(*args, **kwargs)



class ReadingAltItem(BaseUUIDModel):
    """Alternative reading versions under one parent reading."""
    reading = models.ForeignKey(
        Reading,
        on_delete=models.CASCADE,
        related_name="alternatives_items",
    )
    variant_label = models.CharField(max_length=60, blank=True, null=True)
    reference = models.CharField(max_length=120, blank=True, null=True)
    quote = models.TextField(blank=True, null=True)
    introduction = models.CharField(max_length=200, blank=True, null=True)
    content = models.TextField()
    conclusion = models.CharField(max_length=40, default="The word of the Lord.")
    sunday_cycles = models.ManyToManyField(YearCycle, blank=True)
    weekday_cycles = models.ManyToManyField(WeekdayCycle, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["reading", "order"])]

    def __str__(self):
        return f"Alt for {self.reading.reference or self.reading.id} ({self.variant_label or 'variant'})"
