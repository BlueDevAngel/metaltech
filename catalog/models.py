from django.db import models


class Material(models.Model):
    """مدل جنس ورق (مثلاً ورق سیاه ST37، روغنی، استیل 304، گالوانیزه)"""

    name = models.CharField("نام متریال", max_length=100)
    code = models.SlugField(
        "کد انگلیسی (Slug)",
        max_length=50,
        unique=True,
        help_text="مثلا: st37 یا steel-304",
    )
    density = models.FloatField(
        "چگالی (g/cm3)",
        default=7.85,
        help_text="چگالی آهن/فولاد 7.85، استیل 7.93، آلومینیوم 2.70 است",
    )
    base_price_per_kg = models.PositiveBigIntegerField(
        "قیمت روز هر کیلوگرم (تومان)",
        help_text="قیمت کف بازار آهن به تومان (مثلا 45000)",
    )
    is_active = models.BooleanField("فعال در سایت؟", default=True)
    updated_at = models.DateTimeField("آخرین بروزرسانی قیمت", auto_now=True)

    class Meta:
        verbose_name = "جنس ورق (متریال)"
        verbose_name_plural = "۱. اجناس ورق و قیمت روز"

    def __str__(self):
        return f"{self.name} ({self.base_price_per_kg:,} تومان/کیلو)"


class SheetThickness(models.Model):
    """جدول تعرفه برش لیزر و خم بر اساس ضخامت ورق"""

    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name="thicknesses",
        verbose_name="جنس ورق",
    )
    thickness_mm = models.FloatField(
        "ضخامت ورق (میلی‌متر)", help_text="مثلا 1.5 یا 2 یا 10"
    )

    # نرخ‌های برش لیزر (بر اساس خروجی CypCut)
    cut_price_per_meter = models.PositiveIntegerField(
        "نرخ برش هر متر (تومان)",
        help_text="هزینه برش لیزر به ازای هر ۱ متر (۱۰۰۰ میلی‌متر) مسیر برش",
    )
    pierce_price = models.PositiveIntegerField(
        "هزینه هر پیرسینگ/سوراخ اولیه (تومان)",
        default=500,
        help_text="هزینه سوراخ‌کاری اولیه لیزر برای هر کانتور بسته",
    )

    # نرخ خم‌کاری
    can_bend = models.BooleanField("قابلیت خم‌کاری دارد؟", default=True)
    bend_price_per_stroke = models.PositiveIntegerField(
        "نرخ هر ضرب خم (تومان)", default=5000
    )

    # ضریب پرت ورق و کف سفارش
    scrap_factor_percent = models.FloatField(
        "ضریب پرت ورق (درصد)",
        default=15.0,
        help_text="چند درصد به وزن مستطیل دور قطعه بابت پرت ورق اضافه شود؟ (مثلا 15)",
    )
    min_order_fee = models.PositiveIntegerField(
        "حداقل اجرت این ضخامت (تومان)", default=150000
    )
    is_active = models.BooleanField("موجود در انبار/کارگاه؟", default=True)

    class Meta:
        verbose_name = "تعرفه ضخامت و برش"
        verbose_name_plural = "۲. تعرفه‌های ضخامت، برش و خم"
        ordering = ["material", "thickness_mm"]
        unique_together = ("material", "thickness_mm")

    def __str__(self):
        return f"{self.material.name} - ضخامت {self.thickness_mm} میل"