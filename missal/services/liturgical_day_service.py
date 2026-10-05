from missal.models import LiturgicalDay

class LiturgicalDayService:
    @staticmethod
    def get_full_queryset():
        return (
            LiturgicalDay.objects
            .select_related("liturgical_day_type", "season")
            .prefetch_related(
                "readings__kind",
                "responsorial_psalm__sunday_cycles",
                "responsorial_psalm__weekday_cycles",
                "gospel_acclamation",
            )
        )
        
    @staticmethod
    def get_day_cached(day_id):
        cache_key = f"liturgical_day:{day_id}"
        data = cache.get(cache_key)
        if not data:
            day = (
                LiturgicalDay.objects
                .select_related("season", "liturgical_day_type")
                .prefetch_related("readings", "responsorial_psalm", "gospel_acclamation")
                .get(id=day_id)
            )
            data = LiturgicalDaySerializer(day).data
            cache.set(cache_key, data, timeout=3600)
        return data
