from django.contrib import admin

from .models import Account, JournalEntry, JournalEntryLine


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 0


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "company", "is_active")
    list_filter = ("account_type", "is_active", "company")
    search_fields = ("code", "name")


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("reference", "entry_date", "source_type", "company", "created_by")
    list_filter = ("source_type", "company")
    search_fields = ("reference", "description")
    inlines = [JournalEntryLineInline]
