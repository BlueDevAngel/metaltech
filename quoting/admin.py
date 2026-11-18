from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from orders.models import Order, OrderItem
from .models import CustomRFQ, Quote, QuoteItem


class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0
    readonly_fields = (
        "file_name",
        "drawing_unit",
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
        "engineer_total_price",
        "order_invoice_link",
        "created_at",
    )
    list_filter = ("is_reviewed", "need_design")
    list_editable = ("is_reviewed",)
    readonly_fields = ("converted_order", "order_invoice_link")

    def save_model(self, request, obj, form, change):
        """تولید خودکار پیش‌فاکتور آنلاین به محض اینکه مهندس مبلغ برآورد شده را وارد کند"""
        if obj.engineer_total_price > 0 and not obj.converted_order:
            qty = max(1, obj.engineer_quantity)
            unit_p = int(obj.engineer_total_price / qty)
            order = Order.objects.create(
                customer_name=obj.customer_name,
                customer_phone=obj.customer_phone,
                shipping_address="تعیین هنگام بارگیری / هماهنگی تلفنی",
                subtotal_price=obj.engineer_total_price,
                payable_amount=obj.engineer_total_price,
                payment_method="online",
            )
            OrderItem.objects.create(
                order=order,
                file_name=obj.engineer_item_title
                or f"پروژه سفارشی طبق نقشه ({obj.customer_name})",
                dxf_file=obj.attachment,
                material_title=obj.engineer_material_spec or "طبق نقشه مهندسی",
                dimensions_str="طبق نقشه",
                quantity=qty,
                unit_price=unit_p,
                total_price=obj.engineer_total_price,
            )
            obj.converted_order = order
            obj.is_reviewed = True
        super().save_model(request, obj, form, change)

    def order_invoice_link(self, obj):
        if obj.converted_order:
            url = reverse("orders:detail", args=[obj.converted_order.id])
            return format_html(
                '<a href="{}" target="_blank" style="background:#f59e0b; color:#09090b; padding:3px 8px; font-weight:bold; text-decoration:none;">لینک پیش‌فاکتور: {}</a>',
                url,
                obj.converted_order.order_number,
            )
        return "هنوز قیمت‌گذاری نشده"

    order_invoice_link.short_description = "لینک پرداخت و پیش‌فاکتور مشتری"