from django.db import models
from orders.models import Order


class Workshop(models.Model):
    """بانک اطلاعات کارگاه‌های طرف قرارداد در شادآباد و بازار آهن"""

    name = models.CharField("نام کارگاه", max_length=150)
    owner_name = models.CharField("نام مسئول / صاحب کارگاه", max_length=150)
    phone = models.CharField("شماره تماس / واتس‌اپ قیمت‌دهی", max_length=20)
    address = models.TextField("آدرس دقیق در شادآباد / شهرک صنعتی")

    # قابلیت‌ها و مشخصات فنی دستگاه‌ها (طبق پرسشنامه بازدید)
    has_laser = models.BooleanField("برش لیزر دارد؟", default=True)
    laser_power_kw = models.FloatField(
        "توان سورس لیزر (کیلووات)", default=3.0, help_text="مثلا 3 یا 6 یا 12"
    )
    table_size = models.CharField(
        "ابعاد میز لیزر", max_length=50, default="1.5x3 متر"
    )
    max_thickness_mm = models.FloatField(
        "حداکثر ضخامت برش تمیز (mm)", default=15.0
    )

    has_bending = models.BooleanField("خم‌کاری (پرس برک) دارد؟", default=False)
    is_cnc_Brake = models.BooleanField("دستگاه خم CNC است؟", default=True)
    max_bend_length_m = models.FloatField("حداکثر طول خم (متر)", default=3.0)

    has_welding = models.BooleanField(
        "جوشکاری (CO2/آرگون) دارد؟", default=False
    )
    has_painting = models.BooleanField(
        "رنگ‌کاری الکترواستاتیک دارد؟", default=False
    )
    has_crane_or_forklift = models.BooleanField(
        "جرثقیل سقفی / لیفتراک دارد؟", default=True
    )
    has_night_shift = models.BooleanField(
        "شیفت شب (ظرفیت فوری) دارد؟", default=False
    )

    # توافقات مالی و امتیاز عملکرد
    agreed_discount_percent = models.FloatField(
        "درصد تخفیف همکاری نقد نسبت به بازار", default=15.0
    )
    quality_rating = models.PositiveSmallIntegerField(
        "امتیاز کیفیت و خوش‌قولی (۱ تا ۵)", default=5
    )
    notes = models.TextField(
        "یادداشت‌های بازدید (نام اپراتور، نرخ‌های توافقی و...)", blank=True
    )
    is_active = models.BooleanField("همکاری فعال؟", default=True)

    class Meta:
        verbose_name = "کارگاه طرف قرارداد"
        verbose_name_plural = "۱. بانک کارگاه‌های شادآباد"
        ordering = ["-quality_rating", "name"]

    def __str__(self):
        services = []
        if self.has_laser:
            services.append(f"لیزر {self.laser_power_kw}KW")
        if self.has_bending:
            services.append("خم CNC" if self.is_cnc_Brake else "خم دستی")
        if self.has_welding:
            services.append("جوش")
        return f"{self.name} ({' + '.join(services)}) - ⭐{self.quality_rating}"


class JobAssignment(models.Model):
    """تخصیص سفارش مشتری به کارگاه، مدیریت ورق ارسالی از سوله و محاسبه سود خالص"""

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="job_assignment",
        verbose_name="سفارش مشتری",
    )
    laser_workshop = models.ForeignKey(
        Workshop,
        on_delete=models.PROTECT,
        related_name="laser_jobs",
        verbose_name="کارگاه برش لیزر / خم",
    )
    secondary_workshop = models.ForeignKey(
        Workshop,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_jobs",
        verbose_name="کارگاه تکمیلی (خم/جوش/رنگ مجزا)",
    )

    # ۱. هزینه‌های واقعی شما در پشت‌صحنه (Cost of Goods Sold)
    raw_material_purchase_cost = models.PositiveBigIntegerField(
        "هزینه واقعی خرید ورق از بازار آهن (تومان)",
        default=0,
        help_text="مبلغی که به بنکدار آهن بابت ورق خام پرداخت کردید",
    )
    workshop_cutting_bending_fee = models.PositiveBigIntegerField(
        "اجرت توافقی کارگاه لیزر و خم (تومان)",
        default=0,
        help_text="اجرتی که کارگاه با تخفیف همکاری از شما می‌گیرد",
    )
    secondary_workshop_fee = models.PositiveBigIntegerField(
        "اجرت کارگاه تکمیلی / جوش و رنگ (تومان)", default=0
    )
    logistics_cost = models.PositiveBigIntegerField(
        "هزینه حمل‌ونقل (وانت/خاور بین سوله و کارگاه)", default=0
    )

    # ۲. مدیریت ضایعات (پرت ورق) و جرایم کنترل کیفیت
    scrap_returned_to_shed = models.BooleanField(
        "ضایعات و شبکه ورق به سوله برگشت؟", default=False
    )
    scrap_recovered_value = models.PositiveBigIntegerField(
        "ارزش ریالی ضایعات برگشتی / استفاده مجدد (تومان)",
        default=0,
        help_text="این مبلغ به سود خالص شما اضافه می‌شود",
    )
    operator_penalty_deduction = models.PositiveBigIntegerField(
        "جریمه کسر شده از کارگاه بابت خرابی قطعه (تومان)", default=0
    )

    # ۳. وضعیت کنترل کیفیت و تسویه با کارگاه
    first_article_approved = models.BooleanField(
        "قطعه اول توسط مهندس تایید شد؟ (First-Article)", default=False
    )
    is_settled_with_workshop = models.BooleanField(
        "با کارگاه تسویه شد؟", default=False
    )
    created_at = models.DateTimeField("تاریخ ارجاع به کارگاه", auto_now_add=True)

    class Meta:
        verbose_name = "تخصیص پروژه و محاسبه سود"
        verbose_name_plural = "۲. تخصیص پروژه‌ها و سود خالص (P&L)"

    @property
    def total_actual_cost(self) -> int:
        """کل هزینه تمام‌شده واقعی برای شما (با کسر ارزش ضایعات برگشتی و جریمه کارگاه)"""
        gross_cost = (
            self.raw_material_purchase_cost
            + self.workshop_cutting_bending_fee
            + self.secondary_workshop_fee
            + self.logistics_cost
        )
        net_cost = (
            gross_cost
            - self.scrap_recovered_value
            - self.operator_penalty_deduction
        )
        return max(0, net_cost)

    @property
    def net_profit(self) -> int:
        """سود خالص شما = مبلغ خالص دریافتی از مشتری منهای کل هزینه تمام‌شده واقعی"""
        return self.order.subtotal_price - self.total_actual_cost

    @property
    def profit_margin_percent(self) -> float:
        """درصد حاشیه سود خالص در این سفارش"""
        if self.order.subtotal_price <= 0:
            return 0.0
        return round((self.net_profit / self.order.subtotal_price) * 100.0, 1)

    @property
    def workshop_payable_90_percent(self) -> int:
        """مبلغ قابل پرداخت هفتگی به کارگاه (با حبس ۱۰٪ سپرده حسن انجام کار)"""
        total_fee = (
            self.workshop_cutting_bending_fee
            - self.operator_penalty_deduction
        )
        return max(0, int(total_fee * 0.90))

    @property
    def workshop_retention_10_percent(self) -> int:
        """۱۰ درصد سپرده حسن انجام کار نزد شما"""
        total_fee = (
            self.workshop_cutting_bending_fee
            - self.operator_penalty_deduction
        )
        return max(0, int(total_fee * 0.10))

    def __str__(self):
        return f"پروژه {self.order.order_number} -> {self.laser_workshop.name} (سود خالص: {self.net_profit:,} ت)"