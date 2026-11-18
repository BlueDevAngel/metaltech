from django.contrib import admin
from .models import Material, SheetThickness


class SheetThicknessInline(admin.TabularInline):
    model = SheetThickness
    extra = 1
    fields = (
        "thickness_mm",
        "cut_price_per_meter",
        "pierce_price",
        "bend_price_per_stroke",
        "scrap_factor_percent",
        "is_active",
    )


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "base_price_per_kg",
        "density",
        "is_active",
        "updated_at",
    )
    list_editable = ("base_price_per_kg", "is_active")
    search_fields = ("name", "code")
    inlines = [SheetThicknessInline]


@admin.register(SheetThickness)
class SheetThicknessAdmin(admin.ModelAdmin):
    list_display = (
        "material",
        "thickness_mm",
        "cut_price_per_meter",
        "pierce_price",
        "bend_price_per_stroke",
        "scrap_factor_percent",
        "is_active",
    )
    list_filter = ("material", "is_active", "can_bend")
    list_editable = (
        "cut_price_per_meter",
        "pierce_price",
        "bend_price_per_stroke",
        "scrap_factor_percent",
        "is_active",
    )