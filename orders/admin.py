from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "file_name",
        "dxf_file",
        "material_title",
        "dimensions_str",
        "quantity",
        "unit_price",
        "total_price",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer_name",
        "company_name",
        "customer_phone",
        "payable_amount_display",
        "is_paid",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "is_paid",
        "payment_method",
        "want_official_invoice",
    )
    list_editable = ("status", "is_paid")
    search_fields = (
        "order_number",
        "customer_name",
        "customer_phone",
        "company_name",
    )
    inlines = [OrderItemInline]

    def payable_amount_display(self, obj):
        return f"{obj.payable_amount:,} تومان"

    payable_amount_display.short_description = "مبلغ قابل پرداخت"