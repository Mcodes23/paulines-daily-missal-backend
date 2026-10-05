from rest_framework import viewsets
from missal.services.liturgical_day_service import LiturgicalDayService
from missal.api.v1.serializers import LiturgicalDaySerializer

class LiturgicalDayViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LiturgicalDaySerializer

    def get_queryset(self):
        return LiturgicalDayService.get_full_queryset()
