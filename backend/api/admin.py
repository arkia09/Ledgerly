from django.contrib import admin

from .models import Correction, Customer, Entry, Page


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "model_name", "extraction_seconds", "uploaded_at")
    readonly_fields = ("extracted_json",)   # the model's original output is immutable


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "date", "date_text", "type", "amount", "struck_out")
    list_filter = ("type", "struck_out")
    search_fields = ("customer__name", "item")


@admin.register(Correction)
class CorrectionAdmin(admin.ModelAdmin):
    list_display = ("id", "page", "row_index", "field", "model_value", "user_value", "created_at")
    list_filter = ("field",)
