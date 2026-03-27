from django.contrib import admin

from .models import PlannedOrder


@admin.register(PlannedOrder)
class PlannedOrderAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "warehouse", "need_by", "status")
    list_filter = ("status", "priority", "warehouse")
    search_fields = ("product__name", "warehouse__name")
