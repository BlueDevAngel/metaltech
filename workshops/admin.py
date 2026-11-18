from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.urls import reverse
from django.utils.html import format_html
from .models import JobAssignment, Workshop


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner_name",
        "phone",
        "laser_power_kw",
        "has_bending",
        "has_welding",
        "has_night_shift",
        "agreed_discount_percent",
        "quality_rating",
        "is_active",
    )
    list_filter = (
        "has_laser",
        "has_bending",
        "has_welding",
        "has_night_shift",
        "is_active",
    )
    list_editable = ("quality_rating", "agreed_discount_percent", "is_active")
    search_fields = ("name", "owner_name", "phone", "address")


@admin.register(JobAssignment)
class JobAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "laser_workshop",
        "customer_revenue_display",
        "actual_cost_display",
        "net_profit_display",
        "margin_display",
        "first_article_approved",
        "scrap_returned_to_shed",
        "work_order_link",
    )
    list_filter = (
        "laser_workshop",
        "first_article_approved",
        "scrap_returned_to_shed",
        "is_settled_with_workshop",
    )
    list_editable = ("first_article_approved", "scrap_returned_to_shed")
    readonly_fields = (
        "customer_revenue_display",
        "actual_cost_display",
        "net_profit_display",
        "retention_info_display",
    )

    def customer_revenue_display(self, obj):
        return f"{intcomma(obj.order.subtotal_price)} تومان"

    customer_revenue_display.short_description = "فروش به مشتری (خالص)"

    def actual_cost_display(self, obj):
        return f"{intcomma(obj.total_actual_cost)} تومان"

    actual_cost_display.short_description = "هزینه تمام‌شده واقعی"

    def net_profit_display(self, obj):
        profit = obj.net_profit
        color = "#10b981" if profit > 0 else "#f43f5e"
        return format_html(
            '<strong style="color: {};">{} تومان</strong>', color, intcomma(profit)
        )

    net_profit_display.short_description = "سود خالص شما"

    def margin_display(self, obj):
        return f"%{obj.profit_margin_percent}"

    margin_display.short_description = "حاشیه سود"

    def retention_info_display(self, obj):
        return (
            f"پرداخت نقدی هفتگی (۹۰٪): {intcomma(obj.workshop_payable_90_percent)} تومان | "
            f"سپرده حسن انجام کار نزد شما (۱۰٪): {intcomma(obj.workshop_retention_10_percent)} تومان"
        )

    retention_info_display.short_description = "فرمول تسویه با کارگاه (حبس ۱۰٪)"

    def work_order_link(self, obj):
        url = reverse("workshops:work_order_sheet", args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background:#0284c7; color:white; padding:4px 8px; border-radius:4px;">🖨️ برگه کارگاه</a>',
            url,
        )

    work_order_link.short_description = "دستور کار بی‌نام"