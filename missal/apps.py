# missal/apps.py
from django.apps import AppConfig
from django.db.models.signals import post_migrate

class MissalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "missal"

    def ready(self):
        from django.dispatch import receiver
        from .models import YearCycle, WeekdayCycle, ReadingKind, LiturgicalDayType

        @receiver(post_migrate)
        def seed_core(sender, **kwargs):
            if sender.name != self.name:
                return

            for c in ["A", "B", "C"]:
                YearCycle.objects.get_or_create(code=c)
            for c in ["I", "II"]:
                WeekdayCycle.objects.get_or_create(code=c)

            kinds = [
                ("First Reading", "first-reading", 10),
                ("Second Reading", "second-reading", 20),
                ("Gospel", "gospel", 90),
                ("Responsorial Psalm", "responsorial-psalm", 30),
                ("Gospel Acclamation", "gospel-acclamation", 40),
            ]
            for name, slug, order_hint in kinds:
                ReadingKind.objects.get_or_create(slug=slug, defaults={"name": name, "order_hint": order_hint})

            # Day types + whether second reading is required
            defaults = [
                ("Sunday", True), ("Solemnity", True), ("Feast", True),
                ("Weekday", False), ("Memorial", False), ("Optional Memorial", False),
            ]
            for name, req in defaults:
                LiturgicalDayType.objects.get_or_create(name=name, defaults={"requires_second_reading": req})
