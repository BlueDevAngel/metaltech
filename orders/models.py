import random
import uuid
from django.db import models
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

    # اطلاعات مالی
    want_official_invoice = models.BooleanField(
        "درخواست فاکتور رسمی (با ارزش افزوده ۱۰٪)", default=False
    )
    subtotal_price = models.PositiveBigIntegerField(
        "جمع خالص اقلام (تومان)", default=0
    )
    tax_amount = models.PositiveBigIntegerField(
        "مالیات ارزش افزوده (تومان)", default=0
    )
    payable_amount = models.PositiveBigIntegerField(
        "مبلغ نهایی قابل پرداخت (تومان)", default=0
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
        help_text="این عکس در پنل رهگیری مشتری نمایش داده می‌شود تا از دقت ساخت مطمئن شود",
    )
    qc_engineer_note = models.TextField(
        "گزارش مهندس کنترل کیفیت سوله", blank=True
    )

    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

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

    def __str__(self):
        return f"{self.order_number} - {self.customer_name} ({self.payable_amount:,} تومان)"


class OrderItem(models.Model):
    """اقلام قفل‌شده داخل سفارش (ثابت ماندن قیمت در برابر نوسان روزانه بازار آهن)"""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="سفارش",
    )
    file_name = models.CharField("نام نقشه", max_length=255)
    dxf_file = models.FileField("فایل DXF", upload_to="orders/dxf/")
    svg_preview = models.TextField("پیش‌نمایش SVG", blank=True)

    material_title = models.CharField("جنس و ضخامت ورق", max_length=150)
    dimensions_str = models.CharField("ابعاد (mm)", max_length=100)
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