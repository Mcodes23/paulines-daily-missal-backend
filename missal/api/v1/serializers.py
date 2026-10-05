from datetime import date as dt
from rest_framework import serializers
from missal.models import (
    LiturgicalDay,
    Reading,
    ResponsorialPsalm,
    GospelAcclamation,
    SpecialSections,
    IntroductoryRites,
)

# ───────────────────────────────────────────────
# 🔹 Alternative Reading Item
# ───────────────────────────────────────────────
class ReadingAlternativeSerializer(serializers.ModelSerializer):
    variant_label = serializers.CharField(source="kind.name", read_only=True, default=None)
    sunday_cycles = serializers.SlugRelatedField(many=True, read_only=True, slug_field="code")
    weekday_cycles = serializers.SlugRelatedField(many=True, read_only=True, slug_field="code")

    class Meta:
        model = Reading
        fields = [
            "id",
            "variant_label",
            "reference",
            "quote",
            "introduction",
            "content",
            "conclusion",
            "sunday_cycles",
            "weekday_cycles",
            "order",
        ]


# ───────────────────────────────────────────────
# 🔹 Reading (handles nested cycles, alternatives)
# ───────────────────────────────────────────────
class ReadingSerializer(serializers.ModelSerializer):
    kind = serializers.StringRelatedField(read_only=True)
    sunday_cycles = serializers.SlugRelatedField(many=True, read_only=True, slug_field="code")
    weekday_cycles = serializers.SlugRelatedField(many=True, read_only=True, slug_field="code")
    alternatives = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    alternative_items = ReadingAlternativeSerializer(source="alternatives", many=True, read_only=True)

    class Meta:
        model = Reading
        fields = [
            "id",
            "kind",
            "reference",
            "quote",
            "introduction",
            "content",
            "conclusion",
            "order",
            "sunday_cycles",
            "weekday_cycles",
            "alternatives",
            "alternative_items",
        ]


# ───────────────────────────────────────────────
# 🔹 Responsorial Psalm (with alt items)
# ───────────────────────────────────────────────
class ResponsorialPsalmAltSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponsorialPsalm
        fields = ["id", "reference", "response", "verses"]


class ResponsorialPsalmSerializer(serializers.ModelSerializer):
    alternatives_items = ResponsorialPsalmAltSerializer(many=True, read_only=True)

    class Meta:
        model = ResponsorialPsalm
        fields = ["id", "reference", "response", "verses", "alternatives_items"]


# ───────────────────────────────────────────────
# 🔹 Gospel Acclamation (with alt items)
# ───────────────────────────────────────────────
class GospelAcclamationAltSerializer(serializers.ModelSerializer):
    class Meta:
        model = GospelAcclamation
        fields = ["id", "reference", "primary_acclamation", "verse"]


class GospelAcclamationSerializer(serializers.ModelSerializer):
    alternatives_items = GospelAcclamationAltSerializer(many=True, read_only=True)

    class Meta:
        model = GospelAcclamation
        fields = ["id", "reference", "primary_acclamation", "verse", "alternatives_items"]


# ───────────────────────────────────────────────
# 🔹 Introductory Rites (with alt text)
# ───────────────────────────────────────────────
class IntroductoryRitesAltSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntroductoryRites
        fields = ["entrance_antiphon_reference", "entrance_antiphon_text", "collect_text"]


class IntroductoryRitesSerializer(serializers.ModelSerializer):
    entrance_alts = IntroductoryRitesAltSerializer(many=True, read_only=True)
    collect_alts = IntroductoryRitesAltSerializer(many=True, read_only=True)

    class Meta:
        model = IntroductoryRites
        fields = [
            "entrance_antiphon_reference",
            "entrance_antiphon_text",
            "collect_text",
            "entrance_alts",
            "collect_alts",
        ]


# ───────────────────────────────────────────────
# 🔹 Special Sections (Communion, Offerings, etc.)
# ───────────────────────────────────────────────
class SpecialSectionsAltSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialSections
        fields = [
            "prayer_over_offerings_text",
            "communion_antiphon_reference",
            "communion_antiphon_text",
            "prayer_after_communion_text",
            "prayer_over_the_people_reference",
            "prayer_over_the_people_text",
        ]


class SpecialSectionsSerializer(serializers.ModelSerializer):
    offerings_alts = SpecialSectionsAltSerializer(many=True, read_only=True)
    comm_alts = SpecialSectionsAltSerializer(many=True, read_only=True)
    after_comm_alts = SpecialSectionsAltSerializer(many=True, read_only=True)
    over_people_alts = SpecialSectionsAltSerializer(many=True, read_only=True)

    class Meta:
        model = SpecialSections
        fields = [
            "prayer_over_offerings_text",
            "communion_antiphon_reference",
            "communion_antiphon_text",
            "prayer_after_communion_text",
            "prayer_over_the_people_reference",
            "prayer_over_the_people_text",
            "offerings_alts",
            "comm_alts",
            "after_comm_alts",
            "over_people_alts",
        ]


# ───────────────────────────────────────────────
# 🔹 Main Liturgical Day Serializer
# ───────────────────────────────────────────────
class LiturgicalDaySerializer(serializers.ModelSerializer):
    """
    Comprehensive human-readable serializer for full Missal content.
    Returns names for foreign keys, and includes nested readings, psalms,
    acclamations, and rites — including all alt items.
    """

    season = serializers.CharField(source="season.name", read_only=True)
    liturgical_day_type = serializers.CharField(source="liturgical_day_type.name", read_only=True)
    title = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()

    readings = ReadingSerializer(many=True, read_only=True)
    responsorial_psalm = ResponsorialPsalmSerializer(read_only=True)
    gospel_acclamation = GospelAcclamationSerializer(read_only=True)
    introductory_rites = IntroductoryRitesSerializer(read_only=True)
    special_sections = SpecialSectionsSerializer(read_only=True)

    class Meta:
        model = LiturgicalDay
        fields = [
            "id",
            "date",
            "title",
            "theme",
            "season",
            "liturgical_day_type",
            "readings",
            "responsorial_psalm",
            "gospel_acclamation",
            "introductory_rites",
            "special_sections",
        ]

    # Derive title intelligently (prefer FK or fallback)
    def get_title(self, obj):
        if hasattr(obj, "title_ref") and obj.title_ref:
            return getattr(obj.title_ref, "name", None)
        return getattr(obj, "title", None) or getattr(obj, "theme", None)

    # Always return a valid ISO date (today if missing)
    def get_date(self, obj):
        return obj.date.isoformat() if obj.date else dt.today().isoformat()
