from django.db import models
from .base import BaseUUIDModel
from .day import LiturgicalDay


class IntroductoryRites(BaseUUIDModel):
    """Entrance Antiphon and Collect (now separated from SpecialSections)."""
    day = models.OneToOneField(
        LiturgicalDay,
        on_delete=models.CASCADE,
        related_name="introductory_rites"
    )
    entrance_antiphon_reference = models.CharField(max_length=120, blank=True, null=True)
    entrance_antiphon_text = models.TextField(blank=True, null=True)
    collect_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Introductory Rites for {self.day}"


class SpecialSections(BaseUUIDModel):
    """Concluding prayers: Offerings, Communion, After Communion, Over the People."""
    day = models.OneToOneField(
        LiturgicalDay,
        on_delete=models.CASCADE,
        related_name="special_sections"
    )
    prayer_over_offerings_text = models.TextField(blank=True, null=True)
    communion_antiphon_reference = models.CharField(max_length=120, blank=True, null=True)
    communion_antiphon_text = models.TextField(blank=True, null=True)
    prayer_after_communion_text = models.TextField(blank=True, null=True)
    prayer_over_the_people_reference = models.CharField(max_length=120, blank=True, null=True)
    prayer_over_the_people_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Special Sections (Concluding Rites) for {self.day}"


# ───────────────────────────────────────────────
# 🔹 Shared Alternative Base
# ───────────────────────────────────────────────
class BaseSpecialAlt(BaseUUIDModel):
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ["order"]


# ───────────────────────────────────────────────
# 🔹 Alternatives for Introductory Rites
# ───────────────────────────────────────────────
class EntranceAntiphonAltItem(BaseSpecialAlt):
    rites = models.ForeignKey(
        IntroductoryRites,
        on_delete=models.CASCADE,
        related_name="entrance_alts"
    )
    reference = models.CharField(max_length=120, blank=True, null=True)


class CollectAltItem(BaseSpecialAlt):
    rites = models.ForeignKey(
        IntroductoryRites,
        on_delete=models.CASCADE,
        related_name="collect_alts"
    )


# ───────────────────────────────────────────────
# 🔹 Alternatives for Concluding Rites
# ───────────────────────────────────────────────
class PrayerOverOfferingsAltItem(BaseSpecialAlt):
    sections = models.ForeignKey(SpecialSections, on_delete=models.CASCADE, related_name="offerings_alts")


class CommunionAntiphonAltItem(BaseSpecialAlt):
    sections = models.ForeignKey(SpecialSections, on_delete=models.CASCADE, related_name="comm_alts")
    reference = models.CharField(max_length=120, blank=True, null=True)


class PrayerAfterCommunionAltItem(BaseSpecialAlt):
    sections = models.ForeignKey(SpecialSections, on_delete=models.CASCADE, related_name="after_comm_alts")


class PrayerOverThePeopleAltItem(BaseSpecialAlt):
    sections = models.ForeignKey(SpecialSections, on_delete=models.CASCADE, related_name="over_people_alts")
    reference = models.CharField(max_length=120, blank=True, null=True)
