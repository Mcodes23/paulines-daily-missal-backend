from django.contrib import admin

from .models import UserProfile, Subscription, SubscriptionPlan


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number", "country_code", "is_email_verified", "created_at")
    list_filter = ("is_email_verified", "country_code")
    search_fields = ("user__email", "user__first_name", "user__last_name", "phone_number")
    raw_id_fields = ("user",)
    ordering = ("-created_at",)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "currency", "duration_days", "is_active")
    list_filter = ("is_active", "currency")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "trial_end", "current_period_end")
    list_filter = ("status",)
    search_fields = ("user__email",)
    raw_id_fields = ("user",)
