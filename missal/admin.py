from django.contrib import admin
from django import forms
from nested_admin import NestedModelAdmin, NestedStackedInline, NestedTabularInline
from django_ckeditor_5.widgets import CKEditor5Widget
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html


from .models import (
    LiturgicalSeason, LiturgicalDayType, WeekTitle, DayTitle,
    YearCycle, WeekdayCycle, ReadingKind,
    LiturgicalDay, Reading,
    ResponsorialPsalm, GospelAcclamation,
    IntroductoryRites, SpecialSections,
    EntranceAntiphonAltItem, CollectAltItem,
    PrayerOverOfferingsAltItem, CommunionAntiphonAltItem,
    PrayerAfterCommunionAltItem, PrayerOverThePeopleAltItem,
    ResponsorialPsalmAltItem, GospelAcclamationAltItem,
    Preface,
)

# ───────────────────────────────────────────────
# 🖋️ Shared Rich-Text Form
# ───────────────────────────────────────────────
class RichTextForm(forms.ModelForm):
    class Meta:
        widgets = {
            "content": CKEditor5Widget(config_name="default"),
            "text": CKEditor5Widget(config_name="default"),
            "introduction": CKEditor5Widget(config_name="default"),
            "conclusion": CKEditor5Widget(config_name="default"),
            "verse": CKEditor5Widget(config_name="default"),
            "response": CKEditor5Widget(config_name="default"),
        }

# ───────────────────────────────────────────────
# 📖 Readings (Cycle-Aware)
# ───────────────────────────────────────────────
class ReadingInlineFormSet(BaseInlineFormSet):
    """Force correct ReadingKind assignment before save, fully Django-safe."""

    def save_new(self, form, commit=True):
        # Ensure saved_forms always exists (for admin compatibility)
        if not hasattr(self, "saved_forms"):
            self.saved_forms = []

        instance = super().save_new(form, commit=False)
        inline = getattr(self, "inline", None)
        if inline and getattr(inline, "reading_kind_slug", None):
            kind = ReadingKind.objects.filter(slug=inline.reading_kind_slug).first()
            if kind:
                instance.kind = kind
        if commit:
            instance.save()
            form.save_m2m()

        # Track saved form
        self.saved_forms.append(form)
        return instance

    def save_existing_objects(self, commit=True):
        # Ensure saved_forms always exists (admin expects it)
        if not hasattr(self, "saved_forms"):
            self.saved_forms = []

        saved_instances = super().save_existing_objects(commit=False)
        inline = getattr(self, "inline", None)

        if inline and getattr(inline, "reading_kind_slug", None):
            kind = ReadingKind.objects.filter(slug=inline.reading_kind_slug).first()
            if kind:
                for obj in saved_instances:
                    if obj and not getattr(obj, "kind_id", None):
                        obj.kind = kind

        if commit:
            for obj in saved_instances:
                obj.save()

        # Track each saved instance's corresponding form
        for form in self.forms:
            if form.instance in saved_instances:
                self.saved_forms.append(form)

        return saved_instances

class ReadingInlineBase(NestedStackedInline):
    model = Reading
    form = RichTextForm
    formset = ReadingInlineFormSet
    extra = 0
    reading_kind_slug = None  # overridden below

    fieldsets = ((None, {
        "fields": (
            "reference", "quote", "introduction", "content", "conclusion",
            "sunday_cycles", "weekday_cycles",
        )
    }),)

    def get_formset(self, request, obj=None, **kwargs):
        """Inject this inline instance into the formset so it can access reading_kind_slug."""
        FormSet = super().get_formset(request, obj, **kwargs)
        FormSet.inline = self   # ✅ this fixes the assignment issue
        return FormSet

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self.reading_kind_slug:
            return qs.filter(kind__slug=self.reading_kind_slug)
        return qs.none()


class FirstReadingInline(ReadingInlineBase):
    verbose_name_plural = "First Reading"
    reading_kind_slug = "first-reading"
    

class SecondReadingInline(ReadingInlineBase):
    verbose_name_plural = "Second Reading"
    reading_kind_slug = "second-reading"


class GospelInline(ReadingInlineBase):
    verbose_name_plural = "Gospel"
    reading_kind_slug = "gospel"


# ───────────────────────────────────────────────
# 🎵 Psalms & Acclamations
# ───────────────────────────────────────────────
class PsalmAltInline(NestedTabularInline):
    model = ResponsorialPsalmAltItem
    form = RichTextForm
    extra = 0
    fields = ("reference", "response", "verses")


class PsalmInline(NestedStackedInline):
    model = ResponsorialPsalm
    form = RichTextForm
    inlines = [PsalmAltInline]
    extra = 0
    fieldsets = ((None, {"fields": ("reference", "response", "verses")}),)


class GospelAcclAltInline(NestedTabularInline):
    model = GospelAcclamationAltItem
    form = RichTextForm
    extra = 0
    fields = ("reference", "primary_acclamation", "verse")


class GospelAcclamationInline(NestedStackedInline):
    model = GospelAcclamation
    form = RichTextForm
    inlines = [GospelAcclAltInline]
    extra = 0
    fieldsets = ((None, {"fields": ("reference", "primary_acclamation", "verse")}),)

# ───────────────────────────────────────────────
# 🙏 Introductory & Concluding Rites
# ───────────────────────────────────────────────
class EntranceAltInline(NestedTabularInline):
    model = EntranceAntiphonAltItem
    form = RichTextForm
    extra = 0
    fields = ("reference", "text")


class CollectAltInline(NestedTabularInline):
    model = CollectAltItem
    form = RichTextForm
    extra = 0
    fields = ("text",)


class OfferingsAltInline(NestedTabularInline):
    model = PrayerOverOfferingsAltItem
    form = RichTextForm
    extra = 0
    fields = ("text",)


class CommunionAltInline(NestedTabularInline):
    model = CommunionAntiphonAltItem
    form = RichTextForm
    extra = 0
    fields = ("reference", "text")


class AfterCommunionAltInline(NestedTabularInline):
    model = PrayerAfterCommunionAltItem
    form = RichTextForm
    extra = 0
    fields = ("text",)


class OverPeopleAltInline(NestedTabularInline):
    model = PrayerOverThePeopleAltItem
    form = RichTextForm
    extra = 0
    fields = ("reference", "text")


# ✝️ Introductory Rites (Entrance + Collect)
class IntroductoryRitesInline(NestedStackedInline):
    model = IntroductoryRites
    form = RichTextForm
    verbose_name_plural = "Introductory Rites"
    extra = 0
    max_num = 1
    fk_name = "day"
    inlines = [EntranceAltInline, CollectAltInline]
    fieldsets = (
        ("Entrance Antiphon", {"fields": ("entrance_antiphon_reference", "entrance_antiphon_text")}),
        ("Collect", {"fields": ("collect_text",)}),
    )


# 🙏 Concluding Rites (Offerings → Communion → After → People)
class ConcludingRitesInline(NestedStackedInline):
    model = SpecialSections
    form = RichTextForm
    verbose_name_plural = "Concluding Rites"
    extra = 0
    max_num = 1
    fk_name = "day"
    inlines = [OfferingsAltInline, CommunionAltInline, AfterCommunionAltInline, OverPeopleAltInline]
    fieldsets = (
        ("Prayer Over Offerings", {"fields": ("prayer_over_offerings_text",)}),
        ("Communion Antiphon", {"fields": ("communion_antiphon_reference", "communion_antiphon_text")}),
        ("Prayer After Communion", {"fields": ("prayer_after_communion_text",)}),
        ("Prayer Over the People", {"fields": ("prayer_over_the_people_reference", "prayer_over_the_people_text")}),
    )

# ───────────────────────────────────────────────
# 🕊️ Main Liturgical Day Admin
# ───────────────────────────────────────────────
@admin.register(LiturgicalDay)
class LiturgicalDayAdmin(NestedModelAdmin):
    """Fully separated Introductory & Concluding Rites tabs."""
    save_on_top = True
    autocomplete_fields = ("title_ref", "liturgical_week", "liturgical_day_type", "season")

    # 🔹 Add "Preview" column to list display
    list_display = ("title_ref", "season", "liturgical_day_type", "date", "preview_link")

    fieldsets = (
        ("🕊️ Day Details", {
            "fields": (
                ("title_ref", "liturgical_week"),
                ("season", "liturgical_day_type"),
                ("date", "override_color"),
                "theme",
            )
        }),
    )

    inlines = [
        IntroductoryRitesInline,
        FirstReadingInline,
        SecondReadingInline,
        PsalmInline,
        GospelAcclamationInline,
        GospelInline,
        ConcludingRitesInline,
    ]

    # ───────────────────────────────
    # 🧭 Custom URLs for preview
    # ───────────────────────────────
    def get_urls(self):
        from django.urls import path
        from . import admin_views

        urls = super().get_urls()
        custom_urls = [
            path(
                "<uuid:pk>/preview/",
                self.admin_site.admin_view(admin_views.preview_liturgical_day),
                name="missal_liturgicalday_preview",
            ),
        ]
        return custom_urls + urls

    # ───────────────────────────────
    # 👁️ Preview button in list view
    # ───────────────────────────────
    from django.utils.html import format_html

    def preview_link(self, obj):
        return format_html(
            '<a class="button" href="{}/preview/" target="_blank" '
            'style="background:#5b9bd5;color:white;padding:4px 8px;'
            'border-radius:4px;text-decoration:none;">Preview</a>',
            obj.pk
        )
    preview_link.short_description = "Preview"

    # ───────────────────────────────
    # 💅 Existing Media assets
    # ───────────────────────────────
    class Media:
        css = {"all": ("admin/css/missal_tabs.css",)}
        js = ("admin/js/missal_tabs.js",)

# ───────────────────────────────────────────────
# 📘 Lookup Admins
# ───────────────────────────────────────────────
@admin.register(YearCycle)
class YearCycleAdmin(admin.ModelAdmin):
    list_display = ("code",)
    search_fields = ("code",)

@admin.register(WeekdayCycle)
class WeekdayCycleAdmin(admin.ModelAdmin):
    list_display = ("code",)
    search_fields = ("code",)

@admin.register(ReadingKind)
class ReadingKindAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order_hint")
    search_fields = ("name", "slug")

@admin.register(LiturgicalSeason)
class LiturgicalSeasonAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "start_date", "end_date")
    list_filter = ("color",)
    search_fields = ("name", "description")

@admin.register(LiturgicalDayType)
class LiturgicalDayTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "rank_num", "color", "requires_second_reading")
    list_filter = ("color",)
    search_fields = ("name",)

@admin.register(WeekTitle)
class WeekTitleAdmin(admin.ModelAdmin):
    list_display = ("name", "season", "week_number")
    list_filter = ("season",)
    autocomplete_fields = ("season",)
    search_fields = ("name", "season__name")

@admin.register(DayTitle)
class DayTitleAdmin(admin.ModelAdmin):
    list_display = ("name", "week", "weekday", "default_day_type")
    list_filter = ("week__season", "weekday", "default_day_type")
    autocomplete_fields = ("week", "default_day_type")
    search_fields = ("name", "week__name", "default_day_type__name")

@admin.register(Preface)
class PrefaceAdmin(admin.ModelAdmin):
    search_fields = ("title", "note", "body")
    def get_model_perms(self, request): return {}
