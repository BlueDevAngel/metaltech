from collections import defaultdict
import math
import uuid
from catalog.models import Material, SheetThickness
from django.db import models

UNIT_MULTIPLIERS = {
    "mm": 1.0,
    "cm": 10.0,
    "inch": 25.4,
    "m": 1000.0,
}

MAX_SHEET_LENGTH_MM = 3000.0
MAX_SHEET_WIDTH_MM = 1500.0


class Quote(models.Model):
    """سبد استعلام قیمت مشتری با محاسبه تجمیعی حداقل اجرت هر ضخامت"""

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
    def subtotal_items_price(self) -> int:
        """جمع خالص قیمت قطعات بدون مابه‌التفاوت کف اجرت"""
        return sum(item.total_price for item in self.items.all())

    @property
    def min_fee_supplement(self) -> int:
        """
        محاسبه مابه‌التفاوت حداقل اجرت کارگاه به صورت تجمیعی برای هر جنس/ضخامت ورق.
        اگر چند قطعه از یک ضخامت ورق در سبد باشند، اجرت برش و خم آن‌ها با هم جمع می‌شود.
        """
        grouped_fees = defaultdict(int)
        thickness_map = {}

        for item in self.items.select_related("sheet_thickness").all():
            st_id = item.sheet_thickness_id
            item_total_fee = (
                item.unit_cutting_cost + item.unit_bending_cost
            ) * item.quantity
            grouped_fees[st_id] += item_total_fee
            thickness_map[st_id] = item.sheet_thickness

        supplement = 0
        for st_id, total_fee in grouped_fees.items():
            min_fee = thickness_map[st_id].min_order_fee
            if total_fee < min_fee:
                supplement += min_fee - total_fee

        return int(math.ceil(supplement / 1000.0) * 1000) if supplement > 0 else 0

    @property
    def total_price(self) -> int:
        """مبلغ نهایی سبد استعلام (جمع قطعات + مابه‌التفاوت کف اجرت کارگاه)"""
        return self.subtotal_items_price + self.min_fee_supplement

    @property
    def total_weight_kg(self) -> float:
        return round(
            sum(item.unit_weight_kg * item.quantity for item in self.items.all()),
            2,
        )

    @property
    def has_oversized_items(self) -> bool:
        """بررسی اینکه آیا قطعه‌ای بزرگ‌تر از میز لیزر (3000x1500) در سبد وجود دارد"""
        return any(item.is_oversized for item in self.items.all())

    def __str__(self):
        return f"استعلام {str(self.id)[:8]} - مبلغ: {self.total_price:,} تومان"


class QuoteItem(models.Model):
    """هر قطعه آپلود شده در سبد استعلام با قابلیت تغییر واحد مقیاس"""

    UNIT_CHOICES = [
        ("mm", "میلی‌متر (mm)"),
        ("cm", "سانتی‌متر (cm)"),
        ("inch", "اینچ (inch)"),
        ("m", "متر (m)"),
    ]

    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="سبد استعلام",
    )
    file_name = models.CharField("نام فایل", max_length=255)
    dxf_file = models.FileField("فایل DXF", upload_to="quotes/dxf/")
    svg_preview = models.TextField("پیش‌نمایش SVG", blank=True)

    # مقادیر خام هندسی استخراج‌شده از فایل (بدون ضریب واحد)
    raw_width = models.FloatField("عرض خام در فایل", default=0)
    raw_height = models.FloatField("طول خام در فایل", default=0)
    raw_cut_length = models.FloatField("طول برش خام در فایل", default=0)
    drawing_unit = models.CharField(
        "واحد ترسیم نقشه", max_length=10, choices=UNIT_CHOICES, default="mm"
    )

    # مقادیر نهایی تبدیل‌شده به میلی‌متر و متر
    width_mm = models.FloatField("عرض قطعه (mm)", default=0)
    height_mm = models.FloatField("طول قطعه (mm)", default=0)
    area_mm2 = models.FloatField("مساحت باکس (mm2)", default=0)
    cut_length_m = models.FloatField("طول برش (متر)", default=0)
    pierce_count = models.PositiveIntegerField("تعداد پیرسینگ", default=1)

    # انتخاب‌های کاربر در صفحه وب
    sheet_thickness = models.ForeignKey(
        SheetThickness,
        on_delete=models.PROTECT,
        verbose_name="جنس و ضخامت ورق",
    )
    quantity = models.PositiveIntegerField("تعداد (تیراژ)", default=1)
    bend_count = models.PositiveIntegerField("تعداد خم در هر قطعه", default=0)

    # مقادیر محاسبه‌شده مالی
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

    @property
    def is_oversized(self) -> bool:
        """بررسی تجاوز ابعاد قطعه از ابعاد ورق و میز لیزر استاندارد (3000x1500 mm)"""
        longer_side = max(self.width_mm, self.height_mm)
        shorter_side = min(self.width_mm, self.height_mm)
        return (
            longer_side > MAX_SHEET_LENGTH_MM
            or shorter_side > MAX_SHEET_WIDTH_MM
        )

    @property
    def engineering_warnings(self) -> list[str]:
        """تشخیص خودکار خطاهای احتمالی در نقشه (مقیاس اشتباه، کادر اضافی، ابعاد خارج از میز)"""
        warnings = []
        longer_side = max(self.width_mm, self.height_mm)
        shorter_side = min(self.width_mm, self.height_mm)

        if self.is_oversized:
            warnings.append(
                f"ابعاد قطعه ({self.width_mm}×{self.height_mm} میلی‌متر) بزرگ‌تر از شیت استاندارد و میز لیزر (3000×1500 میلی‌متر) است. در صورت اشتباه بودن مقیاس، «واحد نقشه» را اصلاح کنید."
            )
        elif longer_side < 15.0:
            warnings.append(
                f"ابعاد قطعه ({self.width_mm}×{self.height_mm} میلی‌متر) بسیار کوچک است. اگر نقشه با واحد سانتی‌متر یا اینچ ترسیم شده، از منوی پایین «واحد نقشه» را تغییر دهید."
            )

        # تشخیص وجود فضای خالی بزرگ (چند قطعه با فاصله زیاد یا کادر دور نقشه)
        cut_length_mm = self.cut_length_m * 1000.0
        box_perimeter = 2.0 * (self.width_mm + self.height_mm)
        if (
            longer_side > 400.0
            and shorter_side > 400.0
            and cut_length_mm < (box_perimeter * 0.95)
        ):
            warnings.append(
                "نسبت مسیر برش به مساحت ورق بسیار کم است. مطمئن شوید چند قطعه با فاصله زیاد یا کادر راهنما در یک فایل قرار نگرفته باشند."
            )

        return warnings

    def calculate_pricing(self):
        """محاسبه ابعاد بر اساس واحد انتخابی و محاسبه قیمت خالص قطعه"""
        scale = UNIT_MULTIPLIERS.get(self.drawing_unit, 1.0)

        # بروزرسانی ابعاد میلی‌متری بر اساس واحد نقشه
        if self.raw_width > 0 and self.raw_height > 0:
            self.width_mm = round(self.raw_width * scale, 2)
            self.height_mm = round(self.raw_height * scale, 2)
            self.cut_length_m = round(
                (self.raw_cut_length * scale) / 1000.0, 4
            )
        self.area_mm2 = round(self.width_mm * self.height_mm, 2)

        st = self.sheet_thickness
        mat = st.material

        # ۱. محاسبه وزن ورق مصرفی به همراه ضریب پرت (Scrap Factor)
        volume_cm3 = (self.area_mm2 * st.thickness_mm) / 1000.0
        raw_weight_kg = (volume_cm3 * mat.density) / 1000.0
        scrap_multiplier = 1.0 + (st.scrap_factor_percent / 100.0)
        self.unit_weight_kg = round(raw_weight_kg * scrap_multiplier, 3)

        # ۲. هزینه ورق مصرفی
        self.unit_material_cost = int(
            self.unit_weight_kg * mat.base_price_per_kg
        )

        # ۳. هزینه برش لیزر و پیرسینگ با تخفیف تیراژ
        raw_cut_cost = (self.cut_length_m * st.cut_price_per_meter) + (
            self.pierce_count * st.pierce_price
        )

        discount = 1.0
        if self.quantity >= 100:
            discount = 0.80
        elif self.quantity >= 20:
            discount = 0.90

        self.unit_cutting_cost = max(2000, int(raw_cut_cost * discount))

        # ۴. هزینه خم‌کاری
        if st.can_bend and self.bend_count > 0:
            self.unit_bending_cost = int(
                self.bend_count * st.bend_price_per_stroke * discount
            )
        else:
            self.unit_bending_cost = 0

        # ۵. قیمت واحد و قیمت ردیف (کف اجرت کارگاهی در سطح کل سبد Quote محاسبه می‌شود)
        raw_unit_price = (
            self.unit_material_cost
            + self.unit_cutting_cost
            + self.unit_bending_cost
        )
        self.unit_price = int(math.ceil(raw_unit_price / 1000.0) * 1000)
        self.total_price = self.unit_price * self.quantity

    def save(self, *args, **kwargs):
        self.calculate_pricing()
        super().save(*args, **kwargs)

class CustomRFQ(models.Model):
    """سفارش‌های بدون فایل استاندارد با قابلیت تبدیل مستقیم به پیش‌فاکتور رسمی توسط مهندس دفتر"""

    customer_name = models.CharField("نام و نام خانوادگی / شرکت", max_length=150)
    customer_phone = models.CharField("شماره موبایل", max_length=20)
    attachment = models.FileField(
        "فایل نقشه / عکس قطعه (PDF, JPG, ZIP)", upload_to="quotes/custom/"
    )
    description = models.TextField(
        "توضیحات فنی مشتری (جنس، ضخامت، تعداد، خم یا جوش و رنگ)"
    )
    need_design = models.BooleanField(
        "نیاز به طراحی مهندسی دارد؟", default=False
    )
    is_reviewed = models.BooleanField(
        "بررسی شده توسط مهندس دفتر؟", default=False
    )

    # بخش قیمت‌گذاری دستی توسط مهندس دفتر برای صدور پیش‌فاکتور آنلاین
    engineer_item_title = models.CharField(
        "شرح قطعه/پروژه جهت درج در پیش‌فاکتور",
        max_length=255,
        blank=True,
        help_text="مثلا: تولید ۲۰ عدد شاسی ورق سیاه ۳ میل شامل برش، خم و جوشکاری",
    )
    engineer_material_spec = models.CharField(
        "مشخصات متریال مصرفی",
        max_length=150,
        blank=True,
        default="طبق نقشه پیوست",
    )
    engineer_quantity = models.PositiveIntegerField("تیراژ کل", default=1)
    engineer_total_price = models.PositiveBigIntegerField(
        "مبلغ کل خالص برآورد شده (تومان)",
        default=0,
        help_text="با وارد کردن این مبلغ و ذخیره، پیش‌فاکتور آنلاین خودکار ساخته می‌شود",
    )
    converted_order = models.OneToOneField(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="پیش‌فاکتور صادر شده",
    )

    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "استعلام سفارشی (بدون DXF)"
        verbose_name_plural = "۲. استعلام‌های سفارشی و نقشه دستی"

    def __str__(self):
        return f"{self.customer_name} ({self.customer_phone})"