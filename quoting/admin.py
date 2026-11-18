from django.contrib import admin
from .models import CustomRFQ, Quote, QuoteItem


class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0
    readonly_fields = (
        "file_name",
        "width_mm",
        "height_mm",
        "cut_length_m",
        "pierce_count",
        "unit_weight_kg",
        "unit_price",
        "total_price",
    )


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer_name",
        "customer_phone",
        "total_price_display",
        "created_at",
    )
    inlines = [QuoteItemInline]

    def total_price_display(self, obj):
        return f"{obj.total_price:,} تومان"

    total_price_display.short_description = "مبلغ کل استعلام"


@admin.register(CustomRFQ)
class CustomRFQAdmin(admin.ModelAdmin):
    list_display = (
        "customer_name",
        "customer_phone",
        "need_design",
        "is_reviewed",
        "created_at",
    )
    list_filter = ("is_reviewed", "need_design")
    list_editable = ("is_reviewed",)