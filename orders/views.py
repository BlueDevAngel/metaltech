from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from quoting.views import get_or_create_quote
import requests
from .models import Order, OrderItem
from .notifications import (
    normalize_and_validate_phone,
    notify_new_order,
    notify_payment_event,
)


def checkout_view(request):
    """صفحه تکمیل اطلاعات خریدار/شرکت و تبدیل سبد استعلام به سفارش رسمی"""
    quote = get_or_create_quote(request)
    if quote.items.count() == 0:
        messages.error(
            request, "سبد استعلام شما خالی است. ابتدا یک نقشه آپلود کنید."
        )
        return redirect("quoting:workspace")

    if quote.has_oversized_items:
        messages.error(
            request,
            "یکی از قطعات سبد شما بزرگ‌تر از ابعاد استاندارد میز لیزر است. لطفاً ابتدا واحد نقشه را اصلاح کنید.",
        )
        return redirect("quoting:workspace")

    if request.method == "POST":
        customer_name = (request.POST.get("customer_name") or "").strip()
        raw_phone = request.POST.get("customer_phone") or ""
        company_name = (request.POST.get("company_name") or "").strip()
        national_id = (request.POST.get("national_id") or "").strip()
        shipping_address = (request.POST.get("shipping_address") or "").strip()
        want_official = request.POST.get("want_official_invoice") == "on"
        payment_method = request.POST.get("payment_method", "online")

        is_valid_phone, clean_phone = normalize_and_validate_phone(raw_phone)
        if not is_valid_phone:
            messages.error(
                request,
                "شماره موبایل وارد شده معتبر نیست. لطفاً شماره ۱۱ رقمی خود را با پیش‌شماره 09 وارد نمایید.",
            )
            return render(request, "orders/checkout.html", {"quote": quote})

        subtotal = quote.total_price
        supplement = quote.min_fee_supplement
        tax = int(subtotal * 0.10) if want_official else 0
        payable = subtotal + tax

        order = Order.objects.create(
            quote=quote,
            customer_name=customer_name,
            customer_phone=clean_phone,
            company_name=company_name,
            national_id=national_id,
            shipping_address=shipping_address,
            want_official_invoice=want_official,
            min_fee_supplement=supplement,
            subtotal_price=subtotal,
            tax_amount=tax,
            payable_amount=payable,
            payment_method=payment_method,
        )

        for q_item in quote.items.all():
            OrderItem.objects.create(
                order=order,
                sheet_thickness=q_item.sheet_thickness,
                file_name=q_item.file_name,
                dxf_file=q_item.dxf_file,
                svg_preview=q_item.svg_preview,
                material_title=str(q_item.sheet_thickness),
                dimensions_str=f"{q_item.width_mm} × {q_item.height_mm}",
                cut_length_m=q_item.cut_length_m,
                pierce_count=q_item.pierce_count,
                bend_count=q_item.bend_count,
                unit_weight_kg=q_item.unit_weight_kg,
                quantity=q_item.quantity,
                unit_price=q_item.unit_price,
                total_price=q_item.total_price,
            )

        if "active_quote_id" in request.session:
            del request.session["active_quote_id"]

        notify_new_order(order)

        if payment_method == "online":
            return redirect("orders:zarinpal_pay", order_id=order.id)

        messages.success(
            request,
            f"پیش‌فاکتور رسمی شماره {order.order_number} صادر شد. اعتبار قیمت این پیش‌فاکتور ۲۴ ساعت می‌باشد.",
        )
        return redirect("orders:detail", order_id=order.id)

    return render(request, "orders/checkout.html", {"quote": quote})


def order_detail_view(request, order_id):
    """صفحه اختصاصی رهگیری ۵ مرحله‌ای سفارش و مشاهده عکس QC قطعه اول"""
    order = get_object_or_404(Order, id=order_id)
    return render(request, "orders/order_detail.html", {"order": order})


def official_invoice_view(request, order_id):
    """صفحه پیش‌فاکتور رسمی استاندارد با مشخصات حساب بانکی و شبا جهت چاپ/PDF"""
    order = get_object_or_404(Order, id=order_id)
    bank_info = {
        "legal_name": getattr(settings, "COMPANY_LEGAL_NAME", "متال‌تک"),
        "bank_name": getattr(settings, "COMPANY_BANK_NAME", "-"),
        "account_owner": getattr(settings, "COMPANY_ACCOUNT_OWNER", "-"),
        "account_number": getattr(settings, "COMPANY_ACCOUNT_NUMBER", "-"),
        "iban": getattr(settings, "COMPANY_IBAN", "-"),
    }
    return render(
        request,
        "orders/invoice_print.html",
        {"order": order, "bank_info": bank_info},
    )


@require_POST
def refresh_order_price_view(request, order_id):
    """بروزرسانی پیش‌فاکتور منقضی‌شده به نرخ روز ورق بازار آهن"""
    order = get_object_or_404(Order, id=order_id)
    if order.is_paid:
        messages.error(request, "این سفارش قبلاً تسویه شده است.")
        return redirect("orders:detail", order_id=order.id)

    order.refresh_to_current_rates()
    messages.success(
        request,
        f"قیمت پیش‌فاکتور بر اساس آخرین نرخ روز ورق بازار آهن بروزرسانی شد و به مدت ۲۴ ساعت دیگر معتبر است. مبلغ جدید: {order.payable_amount:,} تومان.",
    )
    return redirect("orders:detail", order_id=order.id)


@require_POST
def upload_receipt_view(request, order_id):
    """بارگذاری فیش واریز بانکی/پایا توسط مدیر خرید شرکت"""
    order = get_object_or_404(Order, id=order_id)

    if order.is_price_expired:
        messages.error(
            request,
            "مهلت اعتبار ۲۴ ساعته این پیش‌فاکتور منقضی شده است. لطفاً ابتدا دکمه «بروزرسانی قیمت به نرخ روز» را بزنید.",
        )
        return redirect("orders:detail", order_id=order.id)

    receipt = request.FILES.get("receipt_file")
    ref_id = (request.POST.get("payment_ref_id") or "").strip()

    if receipt:
        order.receipt_file = receipt
        order.payment_ref_id = ref_id
        order.save()
        notify_payment_event(order, "بارگذاری تصویر فیش بانکی / پایا")
        messages.success(
            request,
            "تصویر فیش واریزی ثبت شد. پس از تایید واحد مالی، سفارش وارد مرحله برش لیزر می‌شود.",
        )
    return redirect("orders:detail", order_id=order.id)


def zarinpal_request_view(request, order_id):
    """ارسال مشتری به درگاه پرداخت زرین‌پال با کنترل قفل اعتبار ۲۴ ساعته"""
    order = get_object_or_404(Order, id=order_id)

    if order.is_paid:
        messages.success(request, "این سفارش قبلاً پرداخت شده است.")
        return redirect("orders:detail", order_id=order.id)

    if order.is_price_expired:
        messages.error(
            request,
            "اعتبار ۲۴ ساعته قیمت این پیش‌فاکتور به پایان رسیده است. لطفاً ابتدا قیمت را به نرخ روز بازار آهن بروزرسانی نمایید.",
        )
        return redirect("orders:detail", order_id=order.id)

    callback_url = request.build_absolute_uri(
        reverse("orders:zarinpal_verify", args=[order.id])
    )

    subdomain = "sandbox" if settings.ZARINPAL_SANDBOX else "payment"
    req_url = f"https://{subdomain}.zarinpal.com/pg/v4/payment/request.json"
    startpay_url = f"https://{subdomain}.zarinpal.com/pg/StartPay/"

    payload = {
        "merchant_id": settings.ZARINPAL_MERCHANT_ID,
        "amount": order.payable_amount * 10,
        "callback_url": callback_url,
        "description": f"پرداخت سفارش {order.order_number} در سامانه متال‌تک",
        "metadata": {"mobile": order.customer_phone},
    }

    try:
        response = requests.post(req_url, json=payload, timeout=10)
        res_data = response.json()
        if res_data.get("data") and res_data["data"].get("code") == 100:
            authority = res_data["data"]["authority"]
            order.zarinpal_authority = authority
            order.save()
            return redirect(f"{startpay_url}{authority}")
    except Exception:
        pass

    if settings.DEBUG:
        order.is_paid = True
        order.status = "step1_engineering"
        order.payment_ref_id = "TEST-LOCAL-1405"
        order.save()
        notify_payment_event(order, "پرداخت آنلاین (شبیه‌ساز توسعه)")
        messages.success(
            request,
            "پرداخت در محیط تست با موفقیت ثبت شد و سفارش به مرحله ۱ (تایید مهندسی نقشه) منتقل گردید.",
        )
        return redirect("orders:detail", order_id=order.id)

    messages.error(
        request,
        "خطا در ارتباط با درگاه زرین‌پال. لطفاً از گزینه پیش‌فاکتور رسمی و واریز بانکی استفاده نمایید.",
    )
    return redirect("orders:detail", order_id=order.id)


def zarinpal_verify_view(request, order_id):
    """بازگشت از درگاه زرین‌پال و تایید نهایی تراکنش"""
    order = get_object_or_404(Order, id=order_id)
    status_param = request.GET.get("Status")
    authority = request.GET.get("Authority")

    if status_param == "OK" and authority == order.zarinpal_authority:
        subdomain = "sandbox" if settings.ZARINPAL_SANDBOX else "payment"
        verify_url = (
            f"https://{subdomain}.zarinpal.com/pg/v4/payment/verify.json"
        )
        payload = {
            "merchant_id": settings.ZARINPAL_MERCHANT_ID,
            "amount": order.payable_amount * 10,
            "authority": authority,
        }
        try:
            response = requests.post(verify_url, json=payload, timeout=10)
            res_data = response.json()
            if res_data.get("data") and res_data["data"].get("code") in (
                100,
                101,
            ):
                order.is_paid = True
                order.status = "step1_engineering"
                order.payment_ref_id = str(res_data["data"].get("ref_id"))
                order.save()
                notify_payment_event(order, "پرداخت آنلاین زرین‌پال تایید شد")
                messages.success(
                    request,
                    f"پرداخت با موفقیت انجام شد. کد رهگیری تراکنش: {order.payment_ref_id}",
                )
                return redirect("orders:detail", order_id=order.id)
        except Exception:
            pass

    messages.error(
        request,
        "تراکنش ناموفق بود یا توسط کاربر لغو گردید. می‌توانید مجدداً اقدام کنید یا فیش بانکی بارگذاری نمایید.",
    )
    return redirect("orders:detail", order_id=order.id)
from .notifications import PERSIAN_TO_ENGLISH_DIGITS


def track_order_view(request):
    """ترمینال پیگیری سفارش با شماره پیش‌فاکتور و شماره موبایل (بدون نیاز به لاگین پیچیده)"""
    if request.method == "POST":
        raw_order_num = (request.POST.get("order_number") or "").strip().upper()
        raw_phone = request.POST.get("customer_phone") or ""

        clean_order_num = raw_order_num.translate(PERSIAN_TO_ENGLISH_DIGITS)
        if clean_order_num.isdigit():
            clean_order_num = f"MT-{clean_order_num}"

        is_valid_phone, clean_phone = normalize_and_validate_phone(raw_phone)
        if not is_valid_phone:
            messages.error(
                request,
                "شماره موبایل وارد شده معتبر نیست. لطفاً شماره ۱۱ رقمی ثبت‌شده در سفارش را وارد نمایید.",
            )
            return render(request, "orders/track.html")

        order = Order.objects.filter(
            order_number__iexact=clean_order_num,
            customer_phone=clean_phone,
        ).first()

        if not order:
            messages.error(
                request,
                f"سفارشی با کد «{clean_order_num}» و شماره همراه «{clean_phone}» یافت نشد.",
            )
            return render(request, "orders/track.html")

        return redirect("orders:detail", order_id=order.id)

    return render(request, "orders/track.html")