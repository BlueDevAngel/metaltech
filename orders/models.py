from datetime import timedelta
import math
import random
import uuid
from catalog.models import SheetThickness
from django.conf import settings
from django.db import models
from django.utils import timezone
from quoting.models import Quote


def generate_order_number():
    return f"MT-{random.randint(100000, 999999)}"


class Order(models.Model):
    """مدل سفارش قطعی، پیش‌فاکتور رسمی و رهگیری ۵ مرحله‌ای تولید"""

    STATUS_CHOICES = [
        ("pending_payment", "در انتظار پرداخت / تایید مالی"),
        ("step1_engineering", "۱. تایید مهندسی نقشه و چیدمان (Nesting)"),
        ("step2_material", "۲. تامین ورق از سوله مرکزی شادآباد"),
        ("step3_production", "۳. در حال برش لیزر و خم‌کاری CNC"),
        ("step4_qc", "۴. کنترل کیفیت (QC) و تایید قطعه اول"),
        ("step5_ready", "۵. آماده بارگیری و ارسال به مشتری"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("online", "پرداخت آنلاین (درگاه زرین‌پال)"),
        ("bank_transfer", "واریز بانکی / پایا (پس از دریافت پیش‌فاکتور رسمی)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(
        "شماره سفارش/پیش‌فاکتور",
        max_length=20,
        default=generate_order_number,
        unique=True,
    )
    quote = models.OneToOneField(
        Quote,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="سبد استعلام مبدا",
    )

    # اطلاعات مشتری و اطلاعات حقوقی برای فاکتور رسمی
    customer_name = models.CharField("نام خریدار / نماینده", max_length=150)
    customer_phone = models.CharField("شماره موبایل", max_length=20)
    company_name = models.CharField(
        "نام شرکت / سازمان (اختیاری)", max_length=150, blank=True
    )
    national_id = models.CharField(
        "شناسه ملی / کد اقتصادی", max_length=30, blank=True
    )
    shipping_address = models.TextField("آدرس دقیق تحویل بار")

    # اطلاعات مالی و قفل ۲۴ ساعته قیمت
    want_official_invoice = models.BooleanField(
        "درخواست فاکتور رسمی (با ارزش افزوده ۱۰٪)", default=False
    )
    min_fee_supplement = models.PositiveBigIntegerField(
        "مابه‌التفاوت حداقل اجرت کارگاه (تومان)", default=0
    )
    subtotal_price = models.PositiveBigIntegerField(
        "جمع خالص کل (تومان)", default=0
    )
    tax_amount = models.PositiveBigIntegerField(
        "مالیات ارزش افزوده (تومان)", default=0
    )
    payable_amount = models.PositiveBigIntegerField(
        "مبلغ نهایی قابل پرداخت (تومان)", default=0
    )
    price_locked_at = models.DateTimeField(
        "زمان قفل شدن قیمت روز", default=timezone.now
    )

    payment_method = models.CharField(
        "روش پرداخت",
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="online",
    )
    is_paid = models.BooleanField("پرداخت تایید شده؟", default=False)
    zarinpal_authority = models.CharField(
        "کد Authority زرین‌پال", max_length=100, blank=True
    )
    payment_ref_id = models.CharField(
        "کد رهگیری پرداخت / فیش", max_length=100, blank=True
    )
    receipt_file = models.FileField(
        "تصویر فیش واریزی (مخصوص شرکت‌ها)",
        upload_to="orders/receipts/",
        blank=True,
        null=True,
    )

    # وضعیت رهگیری تولید و کنترل کیفیت (QC) در سوله
    status = models.CharField(
        "وضعیت فعلی سفارش",
        max_length=30,
        choices=STATUS_CHOICES,
        default="pending_payment",
    )
    qc_first_article_image = models.ImageField(
        "تصویر قطعه اول زیر کولیس (QC)",
        upload_to="orders/qc/",
        blank=True,
        null=True,
    )
    qc_engineer_note = models.TextField(
        "گزارش مهندس کنترل کیفیت سوله", blank=True
    )

    created_at = models.DateTimeField("تاریخ ثبت اولیه", auto_now_add=True)

    class Meta:
        verbose_name = "سفارش و پیش‌فاکتور"
        verbose_name_plural = "۱. سفارشات و رهگیری تولید"
        ordering = ["-created_at"]

    @property
    def current_step_number(self) -> int:
        mapping = {
            "pending_payment": 0,
            "step1_engineering": 1,
            "step2_material": 2,
            "step3_production": 3,
            "step4_qc": 4,
            "step5_ready": 5,
        }
        return mapping.get(self.status, 0)

    @property
    def price_expires_at(self):
        hours = getattr(settings, "ORDER_PRICE_VALIDITY_HOURS", 24)
        return self.price_locked_at + timedelta(hours=hours)

    @property
    def is_price_expired(self) -> bool:
        """اگر سفارش هنوز پرداخت نشده و بیش از ۲۴ ساعت از قفل قیمت گذشته باشد، منقضی می‌شود."""
        if self.is_paid:
            return False
        return timezone.now() > self.price_expires_at

    def refresh_to_current_rates(self):
        """بروزرسانی خودکار قیمت اقلام پیش‌فاکتور منقضی‌شده به نرخ روز بازار آهن"""
        if self.is_paid:
            return

        items_sum = 0
        for item in self.items.select_related("sheet_thickness__material").all():
            st = item.sheet_thickness
            if st:
                mat = st.material
                mat_cost = int(item.unit_weight_kg * mat.base_price_per_kg)
                raw_cut = (item.cut_length_m * st.cut_price_per_meter) + (
                    item.pierce_count * st.pierce_price
                )
                discount = (
                    0.80
                    if item.quantity >= 100
                    else (0.90 if item.quantity >= 20 else 1.0)
                )
                cut_cost = max(2000, int(raw_cut * discount))
                bend_cost = (
                    int(item.bend_count * st.bend_price_per_stroke * discount)
                    if (st.can_bend and item.bend_count > 0)
                    else 0
                )
                item.unit_price = int(
                    math.ceil((mat_cost + cut_cost + bend_cost) / 1000.0) * 1000
                )
                item.total_price = item.unit_price * item.quantity
                item.save()
            items_sum += item.total_price

        self.subtotal_price = items_sum + self.min_fee_supplement
        self.tax_amount = (
            int(self.subtotal_price * 0.10)
            if self.want_official_invoice
            else 0
        )
        self.payable_amount = self.subtotal_price + self.tax_amount
        self.price_locked_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.order_number} - {self.customer_name} ({self.payable_amount:,} تومان)"


class OrderItem(models.Model):
    """اقلام قفل‌شده داخل سفارش"""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="سفارش",
    )
    sheet_thickness = models.ForeignKey(
        SheetThickness,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="مرجع ضخامت ورق (جهت بروزرسانی نرخ روز)",
    )
    file_name = models.CharField("نام نقشه / شرح قطعه", max_length=255)
    dxf_file = models.FileField(
        "فایل نقشه", upload_to="orders/dxf/", blank=True, null=True
    )
    svg_preview = models.TextField("پیش‌نمایش SVG", blank=True)

    material_title = models.CharField("جنس و ضخامت ورق", max_length=150)
    dimensions_str = models.CharField(
        "ابعاد (mm)", max_length=100, default="-"
    )
    cut_length_m = models.FloatField("طول برش (متر)", default=0)
    pierce_count = models.PositiveIntegerField("تعداد پیرسینگ", default=1)
    bend_count = models.PositiveIntegerField("تعداد خم", default=0)
    unit_weight_kg = models.FloatField("وزن واحد (kg)", default=0)

    quantity = models.PositiveIntegerField("تعداد", default=1)
    unit_price = models.PositiveBigIntegerField("قیمت واحد (تومان)", default=0)
    total_price = models.PositiveBigIntegerField("قیمت کل (تومان)", default=0)

    class Meta:
        verbose_name = "ردیف سفارش"
        verbose_name_plural = "اقلام سفارش"

    def __str__(self):
        return f"{self.file_name} ({self.quantity} عدد)"