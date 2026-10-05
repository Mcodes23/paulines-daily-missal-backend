from datetime import date
from typing import List, Optional, Union
from pydantic import BaseModel, Field


# ───────────────────────────────────────────────
# 🔹 Cycle (Sunday / Weekday) Items
# ───────────────────────────────────────────────
class CycleItem(BaseModel):
    """Represents a liturgical cycle such as A/B/C or I/II."""
    id: Optional[str] = None
    code: Optional[str] = None
    name: Optional[str] = None

    class Config:
        from_attributes = True


# ───────────────────────────────────────────────
# 🔹 Alternative Reading Item
# ───────────────────────────────────────────────
class ReadingAlternativeItem(BaseModel):
    """Alternative or variant form of a reading."""
    id: Optional[str] = None
    variant_label: Optional[str] = None
    reference: Optional[str] = None
    quote: Optional[str] = None
    introduction: Optional[str] = None
    content: Optional[str] = None
    conclusion: Optional[str] = "The word of the Lord."
    order: Optional[int] = None

    # Accept both simple string codes and full objects
    sunday_cycles: Optional[List[Union[str, CycleItem]]] = Field(default_factory=list)
    weekday_cycles: Optional[List[Union[str, CycleItem]]] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ───────────────────────────────────────────────
# 🔹 Primary Reading
# ───────────────────────────────────────────────
class ReadingItem(BaseModel):
    """A single reading for a liturgical day."""
    id: Optional[str] = None
    kind: Optional[str] = None
    reference: Optional[str] = None
    quote: Optional[str] = None
    introduction: Optional[str] = None
    content: Optional[str] = None
    conclusion: Optional[str] = None
    order: Optional[int] = None

    # Accept both string and object cycles
    sunday_cycles: Optional[List[Union[str, CycleItem]]] = Field(default_factory=list)
    weekday_cycles: Optional[List[Union[str, CycleItem]]] = Field(default_factory=list)

    # Alternatives
    alternatives: Optional[List[str]] = Field(default_factory=list)
    alternative_items: Optional[List[ReadingAlternativeItem]] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ───────────────────────────────────────────────
# 🔹 Responsorial Psalm
# ───────────────────────────────────────────────
class ResponsorialPsalmItem(BaseModel):
    """Responsorial psalm section."""
    id: Optional[str] = None
    reference: Optional[str] = None
    response: Optional[str] = None
    verses: Optional[str] = None

    class Config:
        from_attributes = True


# ───────────────────────────────────────────────
# 🔹 Gospel Acclamation
# ───────────────────────────────────────────────
class GospelAcclamationItem(BaseModel):
    """Gospel acclamation section."""
    id: Optional[str] = None
    reference: Optional[str] = None
    primary_acclamation: Optional[str] = None
    verse: Optional[str] = None

    class Config:
        from_attributes = True


# ───────────────────────────────────────────────
# 🔹 Introductory Rites
# ───────────────────────────────────────────────
class IntroductoryRitesItem(BaseModel):
    """Entrance antiphon and collect."""
    entrance_antiphon_reference: Optional[str] = None
    entrance_antiphon_text: Optional[str] = None
    collect_text: Optional[str] = None

    class Config:
        from_attributes = True


# ───────────────────────────────────────────────
# 🔹 Special Sections
# ───────────────────────────────────────────────
class SpecialSectionsItem(BaseModel):
    """Prayers over offerings, communion, and after communion."""
    prayer_over_offerings_text: Optional[str] = None
    communion_antiphon_reference: Optional[str] = None
    communion_antiphon_text: Optional[str] = None
    prayer_after_communion_text: Optional[str] = None
    prayer_over_the_people_reference: Optional[str] = None
    prayer_over_the_people_text: Optional[str] = None

    class Config:
        from_attributes = True


# ───────────────────────────────────────────────
# 🔹 Full Liturgical Day Response
# ───────────────────────────────────────────────
class LiturgicalReadingResponse(BaseModel):
    """
    Complete response for one liturgical day,
    including all readings, psalm, gospel acclamation,
    introductory rites, special sections, and metadata.
    """
    id: Optional[str] = None

    # Accept either "YYYY-MM-DD" strings or Python date objects
    date: Optional[Union[str, date]] = None

    theme: Optional[str] = None
    title: Optional[str] = None
    season: Optional[str] = None
    liturgical_day_type: Optional[str] = None

    readings: Optional[List[ReadingItem]] = Field(default_factory=list)
    responsorial_psalm: Optional[ResponsorialPsalmItem] = None
    gospel_acclamation: Optional[GospelAcclamationItem] = None
    introductory_rites: Optional[IntroductoryRitesItem] = None
    special_sections: Optional[SpecialSectionsItem] = None

    metadata: Optional[dict] = Field(
        default_factory=dict,
        description="Cycle/year data: sunday_cycle, weekday_cycle, liturgical_year, etc."
    )

    class Config:
        from_attributes = True


# ───────────────────────────────────────────────
# 🔹 List + Pagination Response
# ───────────────────────────────────────────────
class LiturgicalReadingListResponse(BaseModel):
    """Used by /all, /search, /season endpoints."""
    data: List[LiturgicalReadingResponse]
    meta: dict

    class Config:
        from_attributes = True
