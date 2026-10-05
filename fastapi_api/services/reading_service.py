from datetime import date
from calendar import day_name
from asgiref.sync import sync_to_async
import httpx
from django.db.models import Q, Prefetch

from missal.models import LiturgicalDay, Reading
from missal.api.v1.serializers import LiturgicalDaySerializer
from fastapi_api.core.pagination import paginate_queryset
from fastapi_api.core.standard_response import StandardResponse
from fastapi_api.core.exceptions import AppException


# ───────────────────────────────────────────────
# 🔹 Helper functions
# ───────────────────────────────────────────────
def get_current_liturgical_year(target_date: date) -> str:
    """Return 3-year Sunday cycle (A, B, C)."""
    cycle = ["A", "B", "C"]
    return cycle[target_date.year % 3]


def get_weekday_cycle(target_date: date) -> str:
    """Return 2-year weekday cycle (I or II)."""
    return "I" if target_date.year % 2 == 1 else "II"


async def fetch_calendar_for_date(target_date: date) -> dict:
    """Fetch liturgical season/week/day metadata from inadiutorium.cz."""
    url = f"http://calapi.inadiutorium.cz/api/v0/en/calendars/default/{target_date.year}/{target_date.month}/{target_date.day}"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise AppException(f"Failed to fetch calendar data: {e}", 502)


# ───────────────────────────────────────────────
# 🔹 ORM + Serializer Helpers (sync context)
# ───────────────────────────────────────────────
@sync_to_async
def fetch_liturgical_day_by_context(season: str, season_week: int, weekday: str):
    """Find LiturgicalDay matching season, week, and weekday — fully prefetched."""
    qs = (
        LiturgicalDay.objects
        .select_related("season", "liturgical_day_type", "title_ref")
        .prefetch_related(
            Prefetch(
                "readings",
                queryset=Reading.objects.prefetch_related(
                    "kind",
                    "sunday_cycles",
                    "weekday_cycles",
                    "alternatives",
                    "alternatives__sunday_cycles",
                    "alternatives__weekday_cycles",
                ),
            ),
            "responsorial_psalm",
            "responsorial_psalm__alternatives_items",
            "gospel_acclamation",
            "gospel_acclamation__alternatives_items",
            "special_sections",
            "special_sections__offerings_alts",
            "special_sections__comm_alts",
            "special_sections__after_comm_alts",
            "special_sections__over_people_alts",
            "introductory_rites",
            "introductory_rites__entrance_alts",
            "introductory_rites__collect_alts",
        )
        .filter(
            Q(season__name__icontains=season)
            & (
                Q(liturgical_week__name__icontains=str(season_week))
                | Q(liturgical_week__name__icontains=f"{season_week}th")
            )
            & (
                Q(title_ref__name__icontains=weekday)
                | Q(theme__icontains=weekday)
                | Q(liturgical_day_type__name__icontains=weekday)
            )
        )
        .order_by("date")
    )

    day = qs.first()
    if not day:
        return None

    # Force eager load
    _ = list(day.readings.all())
    getattr(day, "responsorial_psalm", None)
    getattr(day, "gospel_acclamation", None)
    getattr(day, "special_sections", None)
    getattr(day, "introductory_rites", None)
    return day


@sync_to_async
def fetch_all_days_list():
    qs = (
        LiturgicalDay.objects
        .select_related("season", "liturgical_day_type", "title_ref")
        .prefetch_related("readings__kind", "readings__sunday_cycles", "readings__weekday_cycles")
        .order_by("date")
    )
    return list(qs)


@sync_to_async
def search_liturgical_days_list(query: str):
    qs = (
        LiturgicalDay.objects
        .filter(
            Q(theme__icontains=query)
            | Q(title_ref__name__icontains=query)
            | Q(readings__reference__icontains=query)
            | Q(readings__content__icontains=query)
        )
        .select_related("season", "liturgical_day_type", "title_ref")
        .prefetch_related("readings__kind")
        .distinct()
        .order_by("date")
    )
    return list(qs)


@sync_to_async
def fetch_days_by_season_list(season_name: str):
    qs = (
        LiturgicalDay.objects
        .filter(season__name__iexact=season_name)
        .select_related("season", "liturgical_day_type", "title_ref")
        .prefetch_related("readings__kind")
        .order_by("date")
    )
    return list(qs)


@sync_to_async
def serialize_liturgical_day(day):
    """Serialize a single LiturgicalDay safely and ensure a valid date."""
    data = LiturgicalDaySerializer(day).data
    if not data.get("date"):
        data["date"] = date.today().isoformat()
    return data


@sync_to_async
def serialize_days_list(days):
    """Serialize list of LiturgicalDay objects safely."""
    serialized = [LiturgicalDaySerializer(d).data for d in days]
    for d in serialized:
        if not d.get("date"):
            d["date"] = date.today().isoformat()
    return serialized


# ───────────────────────────────────────────────
# 🔹 Main Service Logic (async-safe)
# ───────────────────────────────────────────────
async def get_liturgical_readings(target_date: date):
    """Return readings for a given date."""
    calendar = await fetch_calendar_for_date(target_date)
    season = calendar.get("season")
    season_week = calendar.get("season_week")
    weekday = day_name[target_date.weekday()]

    if not season or not season_week:
        raise AppException("Calendar API returned incomplete data.", 500)

    day = await fetch_liturgical_day_by_context(season, season_week, weekday)
    if not day:
        raise AppException(f"No readings found for {weekday}, {season_week}th week of {season}.", 404)

    sunday_cycle = get_current_liturgical_year(target_date)
    weekday_cycle = get_weekday_cycle(target_date)
    is_weekday = weekday.lower() != "sunday"

    # Filter readings synchronously
    @sync_to_async
    def _filter_readings(day, sunday_cycle, weekday_cycle, is_weekday):
        filtered = []
        for r in day.readings.all():
            sunday_codes = [c.code for c in r.sunday_cycles.all()]
            weekday_codes = [c.code for c in r.weekday_cycles.all()]
            if is_weekday:
                if not weekday_codes or weekday_cycle in weekday_codes:
                    filtered.append(r)
            else:
                if not sunday_codes or sunday_cycle in sunday_codes:
                    filtered.append(r)
        day._prefetched_objects_cache = getattr(day, "_prefetched_objects_cache", {})
        day._prefetched_objects_cache["readings"] = filtered
        return day

    day = await _filter_readings(day, sunday_cycle, weekday_cycle, is_weekday)
    data = await serialize_liturgical_day(day)
    data["metadata"] = {
        "season": season,
        "week": season_week,
        "weekday": weekday,
        "sunday_cycle": sunday_cycle,
        "weekday_cycle": weekday_cycle,
        "liturgical_year": target_date.year,
    }

    meta = {
        "total_items": len(data.get("readings", [])),
        "total_pages": 1,
        "page": 1,
        "page_size": len(data.get("readings", [])),
    }

    return StandardResponse.ok(data=data, meta=meta, message="Success")


async def list_all_liturgical_days(page: int = 1, page_size: int = 10):
    """Paginated list of all liturgical days."""
    days = await fetch_all_days_list()
    subset, meta = paginate_queryset(days, page, page_size)
    data = await serialize_days_list(subset)

    # Enrich metadata per day
    for d in data:
        d["metadata"] = {
            "liturgical_year": date.today().year,
        }

    return StandardResponse.ok(data=data, meta=meta, message="Success")


async def search_liturgical_readings(query: str, page: int = 1, page_size: int = 10):
    """Search readings by theme, title, or content."""
    if not query.strip():
        raise AppException("Search query cannot be empty", 400)

    days = await search_liturgical_days_list(query)
    subset, meta = paginate_queryset(days, page, page_size)
    data = await serialize_days_list(subset)

    for d in data:
        d["metadata"] = {
            "liturgical_year": date.today().year,
        }

    return StandardResponse.ok(data=data, meta=meta, message="Success")


async def get_readings_by_season(season_name: str, page: int = 1, page_size: int = 10):
    """Return readings for a specific liturgical season."""
    days = await fetch_days_by_season_list(season_name)
    if not days:
        raise AppException(f"No readings found for season '{season_name}'", 404)

    subset, meta = paginate_queryset(days, page, page_size)
    data = await serialize_days_list(subset)

    for d in data:
        d["metadata"] = {
            "season": season_name.title(),
            "liturgical_year": date.today().year,
        }

    return StandardResponse.ok(data=data, meta=meta, message="Success")


# ───────────────────────────────────────────────
# 🌍 Calendar Proxy (for React Native)
# ───────────────────────────────────────────────
async def fetch_calendar_month(year: int, month: int):
    """
    Securely proxy the external HTTP-only Catholic calendar API (month-level)
    through our own backend — used by the mobile app calendar.
    """
    url = f"http://calapi.inadiutorium.cz/api/v0/en/calendars/default/{year}/{month}"

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return StandardResponse.ok(
                data=data,
                message=f"Calendar for {year}-{month} fetched successfully.",
            )
        except httpx.HTTPStatusError as e:
            raise AppException(f"Calendar API returned {e.response.status_code}", 502)
        except Exception as e:
            raise AppException(f"Failed to fetch calendar data: {e}", 502)
