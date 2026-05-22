from django.contrib import admin
from .models import DashboardWidget


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ["user", "widget_key", "position", "is_visible", "width"]
    list_filter = ["is_visible", "width"]
    search_fields = ["user__email", "widget_key"]
    ordering = ["user", "position"]
