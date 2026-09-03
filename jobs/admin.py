from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Job, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer_name",
        "license_plate",
        "vehicle_make",
        "vehicle_model",
        "status",
        "assigned_technician",
        "created_at",
    )
    list_filter = ("status", "assigned_technician", "created_at")
    search_fields = (
        "customer_name",
        "customer_phone",
        "license_plate",
        "vin",
        "vehicle_make",
        "vehicle_model",
    )
    ordering = ("-created_at",)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(UserProfile)

