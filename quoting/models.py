import math
import uuid
from catalog.models import Material, SheetThickness
from django.db import models


class Quote(models.Model):
    """سبد استعلام قیمت مشتری (شبیه سبد خرید Xometry)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(
        "شناسه نشست", max_length=100, blank=True, null=True
    )
    customer_name = models.CharField("نام مشتری/شرکت", max_length=150, blank=True)
    customer_phone = models.CharField("شماره تماس", max_length=20, blank=True)
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)

    class Meta:
        verbose_name = "سبد استعلام قیمت"
        verbose_name_plural = "۱. سبدهای استعلام آنی (DXF)"

    @property
    def total_price(self) -> int:
        return sum(item.total_price for item in self.items.all())

    @property
    def total_weight_kg(self) -> float:
        return round(
            sum(
                item.unit_weight_kg * item.quantity for item in self.items.all()
            ),
            2,
        )

    def __str__(self):
        return f"استعلام {str(self.id)[:8]} - مبلغ: {self.total_price:,} تومان"


class QuoteItem(models.Model):
    """هر قطعه آپلود شده در سبد استعلام"""

    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="سبد استعلام",
    )
    file_name = models.CharField("نام فایل", max_length=255)
    dxf_file = models.FileField("فایل DXF", upload_to="quotes/dxf/")
    svg_preview = models.TextField("پیش‌نمایش SVG", blank=True)

    # خروجی‌های موتور هندسی (ثابت برای هر فایل)
    width_mm = models.FloatField("عرض قطعه (mm)", default=0)
    height_mm = models.FloatField("طول قطعه (mm)", default=0)
    area_mm2 = models.FloatField("مساحت باکس (mm2)", default=0)
    cut_length_m = models.FloatField("طول برش (متر)", default=0)
    pierce_count = models.PositiveIntegerField("تعداد پیرسینگ", default=1)

    # انتخاب‌های کاربر در صفحه وب (متغیر با HTMX)
    sheet_thickness = models.ForeignKey(
        SheetThickness,
        on_delete=models.PROTECT,
        verbose_name="جنس و ضخامت ورق",
    )
    quantity = models.PositiveIntegerField("تعداد (تیراژ)", default=1)
    bend_count = models.PositiveIntegerField(
        "تعداد خم در هر قطعه", default=0
    )

    # مقادیر محاسبه شده مالی (ذخیره برای سرعت و گزارش‌گیری)
    unit_weight_kg = models.FloatField("وزن ناخالص هر قطعه (kg)", default=0)
    unit_material_cost = models.PositiveBigIntegerField(
        "هزینه ورق هر قطعه (تومان)", default=0
    )
    unit_cutting_cost = models.PositiveBigIntegerField(
        "اجرت برش هر قطعه (تومان)", default=0
    )
    unit_bending_cost = models.PositiveBigIntegerField(
        "اجرت خم هر قطعه (تومان)", default=0
    )
    unit_price = models.PositiveBigIntegerField(
        "قیمت نهایی هر قطعه (تومان)", default=0
    )
    total_price = models.PositiveBigIntegerField(
        "قیمت کل این ردیف (تومان)", default=0
    )

    class Meta:
        verbose_name = "ردیف قطعه استعلام"
        verbose_name_plural = "قطعات استعلام شده"
        ordering = ["-id"]

    def calculate_pricing(self):
        """فرمول مهندسی محاسبه وزن ورق، اجرت برش، پیرسینگ، خم و تخفیف تیراژ"""
        st = self.sheet_thickness
        mat = st.material

        # ۱. محاسبه وزن ورق مصرفی به همراه ضریب پرت (Scrap Factor)
        # فرمول حجم به سانتی‌متر مکعب: (مساحت به میلی‌متر مربع * ضخامت) / 1000
        volume_cm3 = (self.area_mm2 * st.thickness_mm) / 1000.0
        raw_weight_kg = (volume_cm3 * mat.density) / 1000.0
        scrap_multiplier = 1.0 + (st.scrap_factor_percent / 100.0)
        self.unit_weight_kg = round(raw_weight_kg * scrap_multiplier, 3)

        # ۲. هزینه ورق مصرفی
        self.unit_material_cost = int(
            self.unit_weight_kg * mat.base_price_per_kg
        )

        # ۳. هزینه برش لیزر (طول برش به متر * نرخ متر + تعداد پیرسینگ * نرخ پیرسینگ)
        raw_cut_cost = (self.cut_length_m * st.cut_price_per_meter) + (
            self.pierce_count * st.pierce_price
        )

        # اعمال تخفیف تیراژ روی اجرت برش (تشویق مشتری به سفارش تعداد بالا)
        discount = 1.0
        if self.quantity >= 100:
            discount = 0.80  # ۲۰ درصد تخفیف اجرت برای تیراژ بالای ۱۰۰ عدد
        elif self.quantity >= 20:
            discount = 0.90  # ۱۰ درصد تخفیف اجرت برای تیراژ بالای ۲۰ عدد

        self.unit_cutting_cost = max(5000, int(raw_cut_cost * discount))

        # ۴. هزینه خم‌کاری
        if st.can_bend and self.bend_count > 0:
            self.unit_bending_cost = int(
                self.bend_count * st.bend_price_per_stroke * discount
            )
        else:
            self.unit_bending_cost = 0

        # ۵. جمع قیمت واحد و قیمت کل (با رعایت حداقل اجرت کارگاه)
        raw_unit_price = (
            self.unit_material_cost
            + self.unit_cutting_cost
            + self.unit_bending_cost
        )
        # گرد کردن به ۱۰۰۰ تومان نزدیک برای تمیزی فاکتور
        self.unit_price = int(math.ceil(raw_unit_price / 1000.0) * 1000)

        calculated_total = self.unit_price * self.quantity
        # اگر کل اجرت برش از کف سفارش ضخامت کمتر بود، مابه‌التفاوت لحاظ شود
        total_cutting_fee = (
            self.unit_cutting_cost + self.unit_bending_cost
        ) * self.quantity
        if total_cutting_fee < st.min_order_fee:
            diff = st.min_order_fee - total_cutting_fee
            calculated_total += diff

        self.total_price = int(math.ceil(calculated_total / 1000.0) * 1000)

    def save(self, *args, **kwargs):
        self.calculate_pricing()
        super().save(*args, **kwargs)


class CustomRFQ(models.Model):
    """مسیر دوم: سفارش‌های بدون فایل استاندارد (عکس نقشه دستی، PDF، یا پروژه جوش و رنگ کامل)"""

    customer_name = models.CharField("نام و نام خانوادگی / شرکت", max_length=150)
    customer_phone = models.CharField("شماره موبایل", max_length=20)
    attachment = models.FileField(
        "فایل نقشه / عکس قطعه (PDF, JPG, ZIP)", upload_to="quotes/custom/"
    )
    description = models.TextField(
        "توضیحات فنی (جنس، ضخامت، تعداد، خم یا جوش و رنگ)"
    )
    need_design = models.BooleanField(
        "نیاز به طراحی مهندسی دارد؟", default=False
    )
    is_reviewed = models.BooleanField("بررسی شده توسط مهندس دفتر؟", default=False)
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "استعلام سفارشی (بدون DXF)"
        verbose_name_plural = "۲. استعلام‌های سفارشی و نقشه دستی"

    def __str__(self):
        return f"{self.customer_name} ({self.customer_phone})"