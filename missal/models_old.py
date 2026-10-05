import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


# ── Lookups ──────────────────────────────────────────────────────────────────
class LiturgicalColor(models.TextChoices):
    GREEN = "green", "Green"
    PURPLE = "purple", "Purple"
    WHITE = "white", "White"
    RED = "red", "Red"
    ROSE = "rose", "Rose"
    BLACK = "black", "Black"
    GOLD = "gold", "Gold"


class YearCycle(models.Model):  # A/B/C
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=1, unique=True)
    class Meta:
        ordering = ["code"]
        verbose_name = "Sunday cycle"
        verbose_name_plural = "Sunday cycles"
        indexes = [models.Index(fields=["code"])]
    def __str__(self): return self.code


class WeekdayCycle(models.Model):  # I/II
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=2, unique=True)
    class Meta:
        ordering = ["code"]
        verbose_name = "Weekday cycle"
        verbose_name_plural = "Weekday cycles"
        indexes = [models.Index(fields=["code"])]
    def __str__(self): return self.code


class ReadingKind(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)  # First Reading, Second Reading, Gospel, …
    slug = models.SlugField(max_length=60, unique=True)
    order_hint = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["order_hint", "name"]
        indexes = [models.Index(fields=["order_hint"]), models.Index(fields=["slug"])]
    def __str__(self): return self.name


class LiturgicalSeason(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    color = models.CharField(max_length=12, choices=LiturgicalColor.choices, default=LiturgicalColor.GREEN)
    key_figures = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["color"]), models.Index(fields=["created_at"])]
    def __str__(self): return self.name


class LiturgicalDayType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    rank_num = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    color = models.CharField(max_length=12, choices=LiturgicalColor.choices, blank=True, null=True)
    requires_second_reading = models.BooleanField(default=False)
    class Meta:
        ordering = ["rank_num", "name"]
        indexes = [models.Index(fields=["requires_second_reading"]), models.Index(fields=["color"])]
    def __str__(self): return f"{self.name}{f' · {self.rank_num}' if self.rank_num is not None else ''}"


class WeekTitle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)  # e.g., "First Week in Ordinary Time"
    season = models.ForeignKey(LiturgicalSeason, on_delete=models.PROTECT, related_name="week_titles")
    week_number = models.PositiveIntegerField(blank=True, null=True)
    class Meta:
        ordering = ["season__name", "week_number", "name"]
        indexes = [models.Index(fields=["season", "week_number"])]
    def __str__(self): return self.name


class DayTitle(models.Model):
    WEEKDAYS = [("Mon","Monday"),("Tue","Tuesday"),("Wed","Wednesday"),("Thu","Thursday"),
                ("Fri","Friday"),("Sat","Saturday"),("Sun","Sunday")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180, unique=True)
    week = models.ForeignKey(WeekTitle, on_delete=models.PROTECT, related_name="day_titles")
    weekday = models.CharField(max_length=3, choices=WEEKDAYS)
    default_day_type = models.ForeignKey(LiturgicalDayType, on_delete=models.PROTECT, related_name="default_for_titles")
    class Meta:
        unique_together = [("week","weekday")]
        ordering = ["week__season__name", "week__week_number", "weekday"]
        indexes = [models.Index(fields=["week", "weekday"])]
    def __str__(self): return self.name


# ── Day & content ────────────────────────────────────────────────────────────
class LiturgicalDay(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title_ref = models.ForeignKey(DayTitle, on_delete=models.PROTECT, related_name="days")
    theme = models.TextField(blank=True, null=True)  # e.g., "The Baptism of the Lord"
    liturgical_week = models.ForeignKey(WeekTitle, on_delete=models.PROTECT, related_name="days")
    liturgical_day_type = models.ForeignKey(LiturgicalDayType, on_delete=models.PROTECT, related_name="days")
    season = models.ForeignKey(LiturgicalSeason, on_delete=models.PROTECT, related_name="days")
    sunday_cycles = models.ManyToManyField(YearCycle, blank=True)     # A/B/C
    weekday_cycles = models.ManyToManyField(WeekdayCycle, blank=True) # I/II
    date = models.DateField(blank=True, null=True)
    override_color = models.CharField(max_length=12, choices=LiturgicalColor.choices, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date","title_ref__name"]
        verbose_name = "Reading"
        verbose_name_plural = "Readings"
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["season"]),
            models.Index(fields=["liturgical_day_type"]),
        ]

    def __str__(self): return self.title_ref.name

    @property
    def effective_color(self):
        return self.override_color or self.liturgical_day_type.color or self.season.color

    def clean(self):
        super().clean()

        # ───────────────────────────────
        # 🩹 Skip strict validation when creating or partial saving
        # ───────────────────────────────
        if not self.pk:
            # Object isn't saved yet — skip until it exists (avoids admin inline timing issues)
            return

        # ───────────────────────────────
        # ✅ Require 2nd reading only for Sundays/Solemnities/Feasts
        # ───────────────────────────────
        if getattr(self.liturgical_day_type, "requires_second_reading", False):
            has_second = self.readings.filter(kind__slug="second-reading").exists()
            if not has_second:
                raise ValidationError("This day type requires a Second Reading.")

        # ───────────────────────────────
        # ✅ Ensure readings have at least one cycle
        # ───────────────────────────────
        for r in self.readings.all():
            if r.sunday_cycles.count() == 0 and r.weekday_cycles.count() == 0:
                raise ValidationError(f"Reading '{r}' must have at least one cycle (A/B/C or I/II).")



# Readings (multiple per day: First, Second, Gospel…)
class Reading(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day = models.ForeignKey(LiturgicalDay, on_delete=models.CASCADE, related_name="readings")
    kind = models.ForeignKey(ReadingKind, on_delete=models.PROTECT, related_name="readings")
    reference = models.CharField(max_length=120)
    quote = models.TextField(blank=True, null=True)
    introduction = models.CharField(max_length=2000, blank=True, null=True)
    content = models.TextField()
    conclusion = models.CharField(max_length=40, default="The word of the Lord.")
    sunday_cycles = models.ManyToManyField(YearCycle, blank=True)
    weekday_cycles = models.ManyToManyField(WeekdayCycle, blank=True)
    order = models.PositiveIntegerField(default=0)
    # historical link-of-links (keep for flexibility; hidden in admin)
    alternatives = models.ManyToManyField("self", symmetrical=False, blank=True)

    class Meta:
        ordering = ["order","kind__order_hint"]
        indexes = [
            models.Index(fields=["day", "order"]),
            models.Index(fields=["kind"]),
        ]

    def __str__(self): return f"{self.kind.name} – {self.reference}"

    def save(self, *args, **kwargs):
        # Auto conclusion for Gospel
        if self.kind and self.kind.name.lower().startswith("gospel"):
            self.conclusion = "The Gospel of the Lord."
        super().save(*args, **kwargs)


# Alternatives inline FOR a single Reading (so editors add them right under the parent)
class ReadingAltItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reading = models.ForeignKey(Reading, on_delete=models.CASCADE, related_name="alternatives_items")

    variant_label = models.CharField(max_length=60, blank=True, null=True)  # "short form" / "long form" (optional)
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


# Psalm — ONE per day (O2O). Alternatives are separate rows under it, cycle-aware.
class ResponsorialPsalm(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day = models.OneToOneField(LiturgicalDay, on_delete=models.CASCADE, related_name="responsorial_psalm")
    reference = models.CharField(max_length=120)
    response = models.CharField(max_length=200)
    verses = models.JSONField(default=list, blank=True)
    order = models.PositiveIntegerField(default=0)
    sunday_cycles = models.ManyToManyField(YearCycle, blank=True)      # optional: scope the primary
    weekday_cycles = models.ManyToManyField(WeekdayCycle, blank=True)  # optional
    class Meta:
        indexes = [models.Index(fields=["day"])]
    def __str__(self): return f"Psalm — {self.reference}"


class ResponsorialPsalmAltItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    psalm = models.ForeignKey(ResponsorialPsalm, on_delete=models.CASCADE, related_name="alternatives_items")
    reference = models.CharField(max_length=120)
    response = models.CharField(max_length=200)
    verses = models.JSONField(default=list, blank=True)
    order = models.PositiveIntegerField(default=0)
    sunday_cycles = models.ManyToManyField(YearCycle, blank=True)      # A/B/C for which this alt applies
    weekday_cycles = models.ManyToManyField(WeekdayCycle, blank=True)  # I/II for which this alt applies
    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["psalm", "order"])]


# Gospel Acclamation — ONE per day (O2O). Alternatives are separate rows, cycle-aware.
class GospelAcclamation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day = models.OneToOneField(LiturgicalDay, on_delete=models.CASCADE, related_name="gospel_acclamation")
    reference = models.CharField(max_length=120, blank=True, null=True)  # e.g., "Mk 1:15"
    primary_acclamation = models.CharField(max_length=50, default="Alleluia")
    verse = models.TextField()
    class Meta:
        indexes = [models.Index(fields=["day"])]
    def __str__(self): return f"Gospel Acclamation — {self.primary_acclamation}"


class GospelAcclamationAltItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    acclamation = models.ForeignKey(GospelAcclamation, on_delete=models.CASCADE, related_name="alternatives_items")
    reference = models.CharField(max_length=120, blank=True, null=True)
    primary_acclamation = models.CharField(max_length=50, default="Alleluia")
    verse = models.TextField()
    order = models.PositiveIntegerField(default=0)
    sunday_cycles = models.ManyToManyField(YearCycle, blank=True)
    weekday_cycles = models.ManyToManyField(WeekdayCycle, blank=True)
    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["acclamation", "order"])]


# Special Sections — ONE per day (O2O) with alternatives everywhere
class SpecialSections(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day = models.OneToOneField(LiturgicalDay, on_delete=models.CASCADE, related_name="special_sections")
    entrance_antiphon_reference = models.CharField(max_length=120, blank=True, null=True)
    entrance_antiphon_text = models.TextField(blank=True, null=True)
    collect_text = models.TextField(blank=True, null=True)
    prayer_over_offerings_text = models.TextField(blank=True, null=True)
    communion_antiphon_reference = models.CharField(max_length=120, blank=True, null=True)
    communion_antiphon_text = models.TextField(blank=True, null=True)
    prayer_after_communion_text = models.TextField(blank=True, null=True)
    prayer_over_the_people_reference = models.CharField(max_length=120, blank=True, null=True)
    prayer_over_the_people_text = models.TextField(blank=True, null=True)
    def __str__(self): return f"Special Sections for {self.day}"


class EntranceAntiphonAltItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sections = models.ForeignKey(SpecialSections, on_delete=models.CASCADE, related_name="entrance_alts")
    reference = models.CharField(max_length=120, blank=True, null=True)
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["sections", "order"])]


class CollectAltItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sections = models.ForeignKey(SpecialSections, on_delete=models.CASCADE, related_name="collect_alts")
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["sections", "order"])]


class PrayerOverOfferingsAltItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sections = models.ForeignKey(SpecialSections, on_delete=models.CASCADE, related_name="offerings_alts")
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["sections", "order"])]


class CommunionAntiphonAltItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sections = models.ForeignKey(SpecialSections, on_delete=models.CASCADE, related_name="comm_alts")
    reference = models.CharField(max_length=120, blank=True, null=True)
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["sections", "order"])]


class PrayerAfterCommunionAltItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sections = models.ForeignKey(SpecialSections, on_delete=models.CASCADE, related_name="after_comm_alts")
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["sections", "order"])]


class PrayerOverThePeopleAltItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sections = models.ForeignKey(SpecialSections, on_delete=models.CASCADE, related_name="over_people_alts")
    reference = models.CharField(max_length=120, blank=True, null=True)
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["sections", "order"])]


# Universal Prayer (multiple sets per day; each can reference alternatives)
class UniversalPrayer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day = models.ForeignKey(LiturgicalDay, on_delete=models.CASCADE, related_name="universal_prayers")
    introduction = models.TextField(blank=True, null=True)
    petitions = models.JSONField(default=list, blank=True)
    conclusion = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    alternatives = models.ManyToManyField("self", symmetrical=False, blank=True)
    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["day", "order"])]
    def __str__(self): return f"Universal Prayer set {self.order} — {self.day}"


# Prefaces
class Preface(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=180, unique=True)
    note = models.CharField(max_length=180, blank=True, null=True)
    body = models.TextField()
    class Meta:
        ordering = ["title"]
    def __str__(self): return self.title


class DayPreface(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day = models.ForeignKey(LiturgicalDay, on_delete=models.CASCADE, related_name="day_prefaces")
    preface = models.ForeignKey(Preface, on_delete=models.PROTECT, related_name="use_days")
    order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["order"]
        unique_together = [("day","preface")]
        indexes = [models.Index(fields=["day", "order"])]

# Metadata + exporter
class Metadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day = models.OneToOneField(LiturgicalDay, on_delete=models.CASCADE, related_name="metadata", blank=True, null=True)
    source_file = models.CharField(max_length=200, blank=True, null=True)
    api_version = models.CharField(max_length=20, default="2025")
    generated_at = models.DateTimeField(default=timezone.now)
    def __str__(self): return f"Metadata for {self.day or self.id}"

    def export_json(self):
        d = self.day
        season, dtype, week = d.season, d.liturgical_day_type, d.liturgical_week
        def codes(qs): return [c.code for c in qs.all()]

        readings = []
        for r in d.readings.select_related("kind").all():
            readings.append({
                "id": str(r.id),
                "reading_type": r.kind.name,
                "reference": r.reference,
                "quote": r.quote,
                "introduction": r.introduction,
                "content": r.content,
                "conclusion": ("The Gospel of the Lord." if "gospel" in r.kind.name.lower() else r.conclusion),
                "year_cycles": codes(r.sunday_cycles),
                "weekday_cycles": codes(r.weekday_cycles),
                "alternatives": [
                    {
                        "variant_label": a.variant_label,
                        "reference": a.reference,
                        "quote": a.quote,
                        "introduction": a.introduction,
                        "content": a.content,
                        "conclusion": a.conclusion,
                        "year_cycles": codes(a.sunday_cycles),
                        "weekday_cycles": codes(a.weekday_cycles),
                    } for a in r.alternatives_items.all().order_by("order")
                ],
            })

        psalm = getattr(d, "responsorial_psalm", None)
        psalm_json = None
        if psalm:
            psalm_json = {
                "id": str(psalm.id),
                "reference": psalm.reference,
                "response": psalm.response,
                "verses": psalm.verses,
                "year_cycles": codes(psalm.sunday_cycles),
                "weekday_cycles": codes(psalm.weekday_cycles),
                "alternatives": [
                    {
                        "reference": a.reference,
                        "response": a.response,
                        "verses": a.verses,
                        "year_cycles": codes(a.sunday_cycles),
                        "weekday_cycles": codes(a.weekday_cycles),
                    } for a in psalm.alternatives_items.all().order_by("order")
                ],
            }

        acclam = getattr(d, "gospel_acclamation", None)
        acclam_json = None
        if acclam:
            acclam_json = {
                "id": str(acclam.id),
                "reference": acclam.reference,
                "primary_acclamation": acclam.primary_acclamation,
                "verse": acclam.verse,
                "alternatives": [
                    {
                        "reference": a.reference,
                        "primary_acclamation": a.primary_acclamation,
                        "verse": a.verse,
                        "year_cycles": codes(a.sunday_cycles),
                        "weekday_cycles": codes(a.weekday_cycles),
                    } for a in acclam.alternatives_items.all().order_by("order")
                ],
            }

        specials = getattr(d, "special_sections", None)
        specials_json = None
        if specials:
            specials_json = {
                "entrance_antiphon": {
                    "reference": specials.entrance_antiphon_reference,
                    "text": specials.entrance_antiphon_text,
                    "alternatives": [{"reference": a.reference, "text": a.text} for a in specials.entrance_alts.all().order_by("order")],
                },
                "collect": {
                    "text": specials.collect_text,
                    "alternatives": [{"text": a.text} for a in specials.collect_alts.all().order_by("order")],
                },
                "prayer_over_offerings": {
                    "text": specials.prayer_over_offerings_text,
                    "alternatives": [{"text": a.text} for a in specials.offerings_alts.all().order_by("order")],
                },
                "communion_antiphon": {
                    "reference": specials.communion_antiphon_reference,
                    "text": specials.communion_antiphon_text,
                    "alternatives": [{"reference": a.reference, "text": a.text} for a in specials.comm_alts.all().order_by("order")],
                },
                "prayer_after_communion": {
                    "text": specials.prayer_after_communion_text,
                    "alternatives": [{"text": a.text} for a in specials.after_comm_alts.all().order_by("order")],
                },
                "prayer_over_the_people": (
                    {
                        "reference": specials.prayer_over_the_people_reference,
                        "text": specials.prayer_over_the_people_text,
                        "alternatives": [{"reference": a.reference, "text": a.text} for a in specials.over_people_alts.all().order_by("order")],
                    } if (specials.prayer_over_the_people_text or specials.over_people_alts.exists()) else None
                ),
            }

        prefaces = [{"id": str(dp.preface.id), "title": dp.preface.title, "note": dp.preface.note, "body": dp.preface.body, "order": dp.order}
                    for dp in d.day_prefaces.all()]

        universal_sets = [{
            "id": str(up.id),
            "introduction": up.introduction,
            "petitions": up.petitions,
            "conclusion": up.conclusion,
            "alternatives": [str(a.id) for a in up.alternatives.all()],
        } for up in d.universal_prayers.all().order_by("order")]

        return {
            "liturgical_season": {
                "id": str(season.id), "name": season.name, "description": season.description,
                "start_date": season.start_date.isoformat() if season.start_date else None,
                "end_date": season.end_date.isoformat() if season.end_date else None,
                "color": season.color, "key_figures": season.key_figures,
                "created_at": season.created_at.isoformat(),
            },
            "liturgical_day": {
                "id": str(d.id),
                "title": d.title_ref.name,
                "liturgical_week": week.name,
                "liturgical_day_type": {
                    "id": str(dtype.id), "name": dtype.name,
                    "rank_num": str(dtype.rank_num) if dtype.rank_num is not None else None,
                    "color": dtype.color,
                },
                "theme": d.theme,
                "year_cycles": list({*codes(d.sunday_cycles)}),
                "weekday_cycles": list({*codes(d.weekday_cycles)}),
                "color_effective": d.effective_color,
                "created_at": d.created_at.isoformat(),
            },
            "readings": readings,
            "responsorial_psalm": psalm_json,
            "gospel_acclamation": acclam_json,
            "special_sections": specials_json,
            "universal_prayer": universal_sets or None,
            "prefaces": prefaces,
            "metadata": {
                "source_file": self.source_file,
                "api_version": self.api_version,
                "generated_at": self.generated_at.isoformat(),
            },
        }
