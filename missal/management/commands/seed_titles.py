# missal/management/commands/seed_titles.py
from django.core.management.base import BaseCommand
from django.db import transaction

from missal.models import (
    LiturgicalSeason, LiturgicalDayType, WeekTitle, DayTitle,
    YearCycle, WeekdayCycle, ReadingKind, LiturgicalColor
)

def get_or_create(model, **kwargs):
    # passthrough helper that supports Django's defaults=... convention
    return model.objects.get_or_create(**kwargs)[0]

class Command(BaseCommand):
    help = "Seeds cycles, seasons, day types, week titles and day titles (idempotent)."

    @transaction.atomic
    def handle(self, *args, **opts):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding Missal lookups & titles…"))

        # --- Cycles ----------------------------------------------------------
        for c in ["A", "B", "C"]:
            get_or_create(YearCycle, code=c)
        for c in ["I", "II"]:
            get_or_create(WeekdayCycle, code=c)

        # --- Reading kinds ---------------------------------------------------
        for name, slug, order in [
            ("First Reading", "first-reading", 10),
            ("Second Reading", "second-reading", 20),
            ("Gospel", "gospel", 90),
        ]:
            # Upsert by slug to avoid dupes
            rk, created = ReadingKind.objects.get_or_create(
                slug=slug, defaults={"name": name, "order_hint": order}
            )
            if not created:
                changed = False
                if rk.name != name:
                    rk.name = name
                    changed = True
                if rk.order_hint != order:
                    rk.order_hint = order
                    changed = True
                if changed:
                    rk.save(update_fields=["name", "order_hint"])

        # --- Day types (rank & color defaults are indicative) ---------------
        spec = [
            ("Solemnity", 1.10, LiturgicalColor.WHITE, True),
            ("Sunday",   2.60, None,                 True),
            ("Feast",    2.50, None,                 False),
            ("Memorial", 3.12, None,                 False),
            ("Optional Memorial", 3.13, None,        False),
            ("Weekday",  4.00, None,                 False),
        ]
        for name, rank, color, req2 in spec:
            dt, created = LiturgicalDayType.objects.get_or_create(
                name=name,
                defaults={"rank_num": rank, "color": color, "requires_second_reading": req2},
            )
            if not created:
                changed = False
                if dt.rank_num != rank:
                    dt.rank_num = rank; changed = True
                if dt.color != color:
                    dt.color = color; changed = True
                if dt.requires_second_reading != req2:
                    dt.requires_second_reading = req2; changed = True
                if changed:
                    dt.save(update_fields=["rank_num", "color", "requires_second_reading"])

        DTY = {d.name: d for d in LiturgicalDayType.objects.all()}

        # --- Seasons ---------------------------------------------------------
        for name, color in [
            ("Advent", LiturgicalColor.PURPLE),
            ("Christmas Time", LiturgicalColor.WHITE),
            ("Lent", LiturgicalColor.PURPLE),
            ("Holy Week", LiturgicalColor.RED),
            ("The Sacred Paschal Triduum", LiturgicalColor.RED),
            ("Easter Time", LiturgicalColor.WHITE),
            ("Ordinary Time", LiturgicalColor.GREEN),
        ]:
            season, created = LiturgicalSeason.objects.get_or_create(
                name=name, defaults={"color": color}
            )
            if not created and season.color != color:
                season.color = color
                season.save(update_fields=["color"])

        SEASON = {s.name: s for s in LiturgicalSeason.objects.all()}

        # --- Helpers ---------------------------------------------------------
        def week(season_name: str, week_name: str, **defaults) -> WeekTitle:
            return WeekTitle.objects.get_or_create(
                name=week_name, season=SEASON[season_name], defaults=defaults
            )[0]

        def ensure_day_title(*, week: WeekTitle, name: str, weekday: str, default_type: str) -> DayTitle:
            """
            Idempotent upsert keyed by (week, weekday) to honor unique_together.
            If exists, updates name and default_day_type when needed.
            """
            dt, created = DayTitle.objects.get_or_create(
                week=week, weekday=weekday,
                defaults={"name": name, "default_day_type": DTY[default_type]},
            )
            changed = False
            if dt.name != name:
                dt.name = name; changed = True
            if dt.default_day_type_id != DTY[default_type].id:
                dt.default_day_type = DTY[default_type]; changed = True
            if changed:
                dt.save(update_fields=["name", "default_day_type"])
            return dt

        def week_with_title(season_name, week_name, day_title, weekday_code, default_type, **wk_defaults):
            wk = week(season_name, week_name, **wk_defaults)
            return ensure_day_title(week=wk, name=day_title, weekday=weekday_code, default_type=default_type)

        # =====================  ADVENT  =====================================
        for n, title in enumerate([
            "First Sunday of Advent",
            "Second Sunday of Advent",
            "Third Sunday of Advent",
            "Fourth Sunday of Advent",
        ], start=1):
            week_with_title("Advent", f"{n} Week in Advent", title, "Sun", "Sunday")

        # Late Advent (Dec 17–24) — give each date its own week container to avoid weekday collisions
        for day_num, weekday_code in [
            (17, "Mon"), (18, "Tue"), (19, "Wed"), (20, "Thu"),
            (21, "Fri"), (22, "Sat"), (23, "Sun"), (24, "Mon"),
        ]:
            wk = week("Advent", f"Late Advent — December {day_num}")
            ensure_day_title(
                week=wk,
                name=f"December {day_num} of Advent",
                weekday=weekday_code,
                default_type="Weekday",
            )

        # =====================  CHRISTMAS TIME  =============================
        for nm, wd, dtype in [
            ("The Nativity of the Lord", "Sun", "Solemnity"),
            ("The Holy Family of Jesus, Mary, and Joseph", "Sun", "Feast"),
            ("Solemnity of Mary, the Holy Mother of God", "Wed", "Solemnity"),
            ("Second Sunday after the Nativity", "Sun", "Sunday"),
            ("The Epiphany of the Lord", "Sun", "Solemnity"),
            ("The Baptism of the Lord", "Sun", "Feast"),
        ]:
            wk = week("Christmas Time", f"Christmas — {nm}")
            ensure_day_title(week=wk, name=nm, weekday=wd, default_type=dtype)

        # =====================  LENT & HOLY WEEK  ===========================
        week_with_title("Lent", "Ash Wednesday", "Ash Wednesday", "Wed", "Weekday")

        for n, title in enumerate([
            "First Sunday of Lent", "Second Sunday of Lent", "Third Sunday of Lent",
            "Fourth Sunday of Lent", "Fifth Sunday of Lent",
        ], start=1):
            week_with_title("Lent", f"{n} Week of Lent", title, "Sun", "Sunday")

        # Holy Week / Triduum
        week_with_title("Holy Week", "Palm Sunday of the Passion of the Lord",
                        "Palm Sunday of the Passion of the Lord", "Sun", "Sunday")
        week_with_title("The Sacred Paschal Triduum", "Thursday of Holy Week",
                        "Thursday of Holy Week", "Thu", "Feast")
        week_with_title("The Sacred Paschal Triduum", "Friday of the Passion of the Lord",
                        "Friday of the Passion of the Lord", "Fri", "Feast")

        # =====================  EASTER TIME  ===============================
        week_with_title("Easter Time", "Easter Vigil", "Easter Vigil", "Sat", "Solemnity")
        week_with_title("Easter Time", "Easter Sunday of the Resurrection of the Lord (Day)",
                        "At the Mass during the Day", "Sun", "Solemnity")

        wk_octave = week("Easter Time", "Within the Octave of Easter")
        for wd, nm in [
            ("Mon", "Monday within the Octave of Easter"),
            ("Tue", "Tuesday within the Octave of Easter"),
            ("Wed", "Wednesday within the Octave of Easter"),
            ("Thu", "Thursday within the Octave of Easter"),
            ("Fri", "Friday within the Octave of Easter"),
            ("Sat", "Saturday within the Octave of Easter"),
        ]:
            ensure_day_title(week=wk_octave, name=nm, weekday=wd, default_type="Weekday")

        for n, title in enumerate([
            "Second Sunday of Easter (of Divine Mercy)",
            "Third Sunday of Easter",
            "Fourth Sunday of Easter",
            "Fifth Sunday of Easter",
            "Sixth Sunday of Easter",
            "Seventh Sunday of Easter",
        ], start=2):
            week_with_title("Easter Time", f"{n} Sunday of Easter (Week)", title, "Sun", "Sunday")

        week_with_title("Easter Time", "Ascension of the Lord", "The Ascension of the Lord", "Sun", "Solemnity")
        week_with_title("Easter Time", "Pentecost Sunday", "Pentecost Sunday", "Sun", "Solemnity")

        # =====================  ORDINARY TIME  =============================
        week("Ordinary Time", "First Week in Ordinary Time", week_number=1)

        for n in range(2, 34):
            wk = week("Ordinary Time", f"{n} Week in Ordinary Time", week_number=n)
            title = f"{n} Sunday in Ordinary Time"
            ensure_day_title(week=wk, name=title, weekday="Sun", default_type="Sunday")

        wk34 = week("Ordinary Time", "Thirty-Fourth Week in Ordinary Time", week_number=34)
        ensure_day_title(
            week=wk34,
            name="Last Sunday in Ordinary Time: The Solemnity of Our Lord Jesus Christ, King of the Universe",
            weekday="Sun",
            default_type="Solemnity",
        )

        for nm, wd in [
            ("The Solemnity of the Most Holy Trinity", "Sun"),
            ("The Solemnity of the Most Holy Body and Blood of Christ (Corpus Christi)", "Sun"),
            ("The Solemnity of the Most Sacred Heart of Jesus", "Fri"),
        ]:
            wk = week("Ordinary Time", f"Ordinary Time — {nm}")
            ensure_day_title(week=wk, name=nm, weekday=wd, default_type="Solemnity")

        self.stdout.write(self.style.SUCCESS("✓ Titles and lookups seeded (idempotent)."))
