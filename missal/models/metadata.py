from django.db import models
from django.utils import timezone
from .base import BaseUUIDModel
from .day import LiturgicalDay


class Metadata(BaseUUIDModel):
    """Metadata and JSON exporter for each Liturgical Day."""
    day = models.OneToOneField(
        LiturgicalDay, on_delete=models.CASCADE, related_name="metadata", blank=True, null=True
    )
    source_file = models.CharField(max_length=200, blank=True, null=True)
    api_version = models.CharField(max_length=20, default="2025")
    generated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Metadata for {self.day or self.id}"

    # ----------------------------------------------------------------------
    # JSON Exporter (used for API / sync / frontend generation)
    # ----------------------------------------------------------------------
    def export_json(self):
        """Serializes the entire day's liturgical data into nested JSON."""
        d = self.day
        season, dtype, week = d.season, d.liturgical_day_type, d.liturgical_week

        def codes(qs):
            return [c.code for c in qs.all()]

        # -----------------------------
        # Readings
        # -----------------------------
        readings = []
        for r in d.readings.select_related("kind").all():
            readings.append({
                "id": str(r.id),
                "reading_type": r.kind.name,
                "reference": r.reference,
                "quote": r.quote,
                "introduction": r.introduction,
                "content": r.content,
                "conclusion": (
                    "The Gospel of the Lord." if "gospel" in r.kind.name.lower() else r.conclusion
                ),
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
                    }
                    for a in r.alternatives_items.all().order_by("order")
                ],
            })

        # -----------------------------
        # Psalm
        # -----------------------------
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
                    }
                    for a in psalm.alternatives_items.all().order_by("order")
                ],
            }

        # -----------------------------
        # Gospel Acclamation
        # -----------------------------
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
                    }
                    for a in acclam.alternatives_items.all().order_by("order")
                ],
            }

        # -----------------------------
        # Special Sections
        # -----------------------------
        specials = getattr(d, "special_sections", None)
        specials_json = None
        if specials:
            specials_json = {
                "entrance_antiphon": {
                    "reference": specials.entrance_antiphon_reference,
                    "text": specials.entrance_antiphon_text,
                    "alternatives": [
                        {"reference": a.reference, "text": a.text}
                        for a in specials.entrance_alts.all().order_by("order")
                    ],
                },
                "collect": {
                    "text": specials.collect_text,
                    "alternatives": [
                        {"text": a.text}
                        for a in specials.collect_alts.all().order_by("order")
                    ],
                },
                "prayer_over_offerings": {
                    "text": specials.prayer_over_offerings_text,
                    "alternatives": [
                        {"text": a.text}
                        for a in specials.offerings_alts.all().order_by("order")
                    ],
                },
                "communion_antiphon": {
                    "reference": specials.communion_antiphon_reference,
                    "text": specials.communion_antiphon_text,
                    "alternatives": [
                        {"reference": a.reference, "text": a.text}
                        for a in specials.comm_alts.all().order_by("order")
                    ],
                },
                "prayer_after_communion": {
                    "text": specials.prayer_after_communion_text,
                    "alternatives": [
                        {"text": a.text}
                        for a in specials.after_comm_alts.all().order_by("order")
                    ],
                },
                "prayer_over_the_people": (
                    {
                        "reference": specials.prayer_over_the_people_reference,
                        "text": specials.prayer_over_the_people_text,
                        "alternatives": [
                            {"reference": a.reference, "text": a.text}
                            for a in specials.over_people_alts.all().order_by("order")
                        ],
                    }
                    if (specials.prayer_over_the_people_text or specials.over_people_alts.exists())
                    else None
                ),
            }

        # -----------------------------
        # Prefaces
        # -----------------------------
        prefaces = [
            {
                "id": str(dp.preface.id),
                "title": dp.preface.title,
                "note": dp.preface.note,
                "body": dp.preface.body,
                "order": dp.order,
            }
            for dp in d.day_prefaces.all()
        ]

        # -----------------------------
        # Universal Prayer
        # -----------------------------
        universal_sets = [
            {
                "id": str(up.id),
                "introduction": up.introduction,
                "petitions": up.petitions,
                "conclusion": up.conclusion,
                "alternatives": [str(a.id) for a in up.alternatives.all()],
            }
            for up in d.universal_prayers.all().order_by("order")
        ]

        # -----------------------------
        # Final Output
        # -----------------------------
        return {
            "liturgical_season": {
                "id": str(season.id),
                "name": season.name,
                "description": season.description,
                "start_date": season.start_date.isoformat() if season.start_date else None,
                "end_date": season.end_date.isoformat() if season.end_date else None,
                "color": season.color,
                "key_figures": season.key_figures,
                "created_at": season.created_at.isoformat(),
            },
            "liturgical_day": {
                "id": str(d.id),
                "title": d.title_ref.name,
                "liturgical_week": week.name,
                "liturgical_day_type": {
                    "id": str(dtype.id),
                    "name": dtype.name,
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
