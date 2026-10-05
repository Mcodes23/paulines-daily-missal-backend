from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Query

# ───────────────────────────────────────────────
# Internal imports (service + response)
# ───────────────────────────────────────────────
from fastapi_api.schemas.reading_schema import LiturgicalReadingResponse
from fastapi_api.services import reading_service as service
from fastapi_api.core.standard_response import StandardResponse


# ───────────────────────────────────────────────
# Initialize router
# ───────────────────────────────────────────────
router = APIRouter()

# 📅 Calendar Proxy (must come first)
@router.get(
    "/calendar/{year}/{month}",
    summary="Proxy: Catholic calendar (month view)",
)
async def get_calendar_month(year: int, month: int):
    """Fetch calendar month (proxied to inadiutorium.cz)."""
    return await service.fetch_calendar_month(year, month)


# ───────────────────────────────────────────────
# 📖 Today's readings
# ───────────────────────────────────────────────
@router.get(
    "/today",
    response_model=StandardResponse[LiturgicalReadingResponse],
    summary="Fetch today's liturgical readings",
)
async def get_readings_for_today(
    target_date: Optional[date] = None,
    offset: Optional[int] = Query(
        None,
        description="Offset in days from today (e.g., +1 for tomorrow, -1 for yesterday)"
    ),
):
    """
    Fetch readings for today or an offset from today.
    """
    if offset is not None:
        target_date = date.today() + timedelta(days=offset)
    if target_date is None:
        target_date = date.today()
    return await service.get_liturgical_readings(target_date)


# ───────────────────────────────────────────────
# 📅 Specific date readings
# ───────────────────────────────────────────────
@router.get(
    "/{year}/{month}/{day}",
    response_model=StandardResponse[LiturgicalReadingResponse],
    summary="Fetch readings for a specific calendar date",
)
async def get_readings_by_date(year: int, month: int, day: int):
    """
    Fetch readings for a specific year/month/day combination.
    """
    target_date = date(year, month, day)
    return await service.get_liturgical_readings(target_date)


# ───────────────────────────────────────────────
# 📚 All liturgical days (paginated)
# ───────────────────────────────────────────────
@router.get(
    "/all",
    response_model=StandardResponse[List[LiturgicalReadingResponse]],
    summary="List all liturgical days with readings (paginated)",
)
async def get_all_readings(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, le=100),
):
    """
    Paginated list of all liturgical days.
    """
    return await service.list_all_liturgical_days(page, page_size)


# ───────────────────────────────────────────────
# 🔍 Search readings
# ───────────────────────────────────────────────
@router.get(
    "/search",
    response_model=StandardResponse[List[LiturgicalReadingResponse]],
    summary="Search readings or themes by keyword",
)
async def search_readings(
    q: str = Query(..., min_length=2, description="Search keyword (in theme, title, or content)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, le=100),
):
    """
    Search readings by keyword across title, theme, and content.
    """
    return await service.search_liturgical_readings(q, page, page_size)


# ───────────────────────────────────────────────
# 🕊️ Readings by liturgical season
# ───────────────────────────────────────────────
@router.get(
    "/season/{season_name}",
    response_model=StandardResponse[List[LiturgicalReadingResponse]],
    summary="Fetch all readings within a specific liturgical season (e.g., Advent, Lent, Easter)",
)
async def get_readings_by_season(
    season_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, le=100),
):
    """
    Fetch readings grouped under a liturgical season.
    """
    return await service.get_readings_by_season(season_name, page, page_size)

