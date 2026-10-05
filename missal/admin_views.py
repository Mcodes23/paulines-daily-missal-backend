# File: missal/admin_views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.timezone import now
from missal.models import LiturgicalDay


@staff_member_required
def preview_liturgical_day(request, pk):
    """
    Admin preview for a Liturgical Day.
    Loads all related data for full Missal rendering (readings, psalms, acclamations, rites, cycles).
    """

    day = get_object_or_404(
        LiturgicalDay.objects
        .select_related(
            "season",
            "liturgical_day_type",
            "responsorial_psalm",
            "gospel_acclamation",
            "introductory_rites",
            "special_sections",
        )
        .prefetch_related(
            # ──────── Cycles ────────
            "sunday_cycles",
            "weekday_cycles",

            # ──────── Readings ────────
            "readings",
            "readings__kind",
            "readings__alternatives_items",
            "readings__sunday_cycles",
            "readings__weekday_cycles",

            # ──────── Responsorial Psalm ────────
            "responsorial_psalm__alternatives_items",  # ✅ Correct related_name

            # ──────── Gospel Acclamation ────────
            "gospel_acclamation__alternatives_items",  # ✅ Correct related_name

            # ──────── Introductory Rites ────────
            "introductory_rites__entrance_alts",
            "introductory_rites__collect_alts",

            # ──────── Concluding Rites ────────
            "special_sections__offerings_alts",
            "special_sections__comm_alts",
            "special_sections__after_comm_alts",
            "special_sections__over_people_alts",
        ),
        pk=pk,
    )

    context = {
        "day": day,
        "now": now(),
    }
    return render(request, "admin/missal/preview_liturgical_day.html", context)
