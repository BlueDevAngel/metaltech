from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from quoting.views import get_or_create_quote
import requests
from .models import Order, OrderItem


def checkout_view(request):
    """صفحه تکمیل اطلاعات خریدار/شرکت و تبدیل سبد استعلام به سفارش رسمی"""
    quote = get_or_create_quote(request)
    if quote.items.count() == 0:
        messages.error(
            request, "سبد استعلام شما خالی است. ابتدا یک نقشه آپلود کنید."
        )
        return redirect("quoting:workspace")

    if request.method == "POST":
        customer_name = request.POST.get("customer_name")
        customer_phone = request.POST.get("customer_phone")
        company_name = request.POST.get("company_name", "")
        national_id = request.POST.get("national_id", "")
        shipping_address = request.POST.get("shipping_address")
        want_official = request.POST.get("want_official_invoice") == "on"
        payment_method = request.POST.get("payment_method", "online")

        subtotal = quote.total_price
        tax = int(subtotal * 0.10) if want_official else 0
        payable = subtotal + tax

        # ۱. ایجاد سفارش رسمی
        order = Order.objects.create(
            quote=quote,
            customer_name=customer_name,
            customer_phone=customer_phone,
            company_name=company_name,
            national_id=national_id,
            shipping_address=shipping_address,
            want_official_invoice=want_official,
            subtotal_price=subtotal,
            tax_amount=tax,
            payable_amount=payable,
            payment_method=payment_method,
        )

        # ۲. انتقال و قفل کردن قطعات در سفارش
        for q_item in quote.items.all():
            OrderItem.objects.create(
                order=order,
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

        # پاک کردن نشست سبد قبلی تا کاربر بتواند استعلام جدیدی بسازد
        if "active_quote_id" in request.session:
            del request.session["active_quote_id"]

        if payment_method == "online":
            return redirect("orders:zarinpal_pay", order_id=order.id)

        messages.success(
            request,
            f"پیش‌فاکتور رسمی شماره {order.order_number} صادر شد. می‌توانید آن را چاپ کنید یا فیش واریزی را بارگذاری نمایید.",
        )
        return redirect("orders:detail", order_id=order.id)

    return render(request, "orders/checkout.html", {"quote": quote})


def order_detail_view(request, order_id):
    """صفحه اختصاصی رهگیری ۵ مرحله‌ای سفارش و مشاهده عکس QC قطعه اول"""
    order = get_object_or_404(Order, id=order_id)
    return render(request, "orders/order_detail.html", {"order": order})


def official_invoice_view(request, order_id):
    """صفحه پیش‌فاکتور رسمی استاندارد با قابلیت چاپ و ذخیره مستقیم به PDF"""
    order = get_object_or_404(Order, id=order_id)
    return render(request, "orders/invoice_print.html", {"order": order})


@require_POST
def upload_receipt_view(request, order_id):
    """بارگذاری فیش واریز بانکی/پایا توسط مدیر خرید شرکت"""
    order = get_object_or_404(Order, id=order_id)
    receipt = request.FILES.get("receipt_file")
    ref_id = request.POST.get("payment_ref_id", "")

    if receipt:
        order.receipt_file = receipt
        order.payment_ref_id = ref_id
        order.save()
        messages.success(
            request,
            "✅ تصویر فیش واریزی ثبت شد. پس از تایید واحد مالی، سفارش وارد مرحله برش لیزر می‌شود.",
        )
    return redirect("orders:detail", order_id=order.id)


def zarinpal_request_view(request, order_id):
    """ارسال مشتری به درگاه پرداخت زرین‌پال (پشتیبانی از حالت Sandbox و واقعی)"""
    order = get_object_or_404(Order, id=order_id)
    callback_url = request.build_absolute_uri(
        reverse("orders:zarinpal_verify", args=[order.id])
    )

    subdomain = "sandbox" if settings.ZARINPAL_SANDBOX else "payment"
    req_url = f"https://{subdomain}.zarinpal.com/pg/v4/payment/request.json"
    startpay_url = f"https://{subdomain}.zarinpal.com/pg/StartPay/"

    payload = {
        "merchant_id": settings.ZARINPAL_MERCHANT_ID,
        "amount": order.payable_amount * 10,  # تبدیل تومان به ریال
        "callback_url": callback_url,
        "description": f"پرداخت سفارش {order.order_number} در سامانه متال‌تک",
        "metadata": {"mobile": order.customer_phone},
    }

    try:
        response = requests.post(req_url, json=payload, timeout=10)
        res_data = response.json()
        if (
            res_data.get("data")
            and res_data["data"].get("code") == 100
        ):
            authority = res_data["data"]["authority"]
            order.zarinpal_authority = authority
            order.save()
            return redirect(f"{startpay_url}{authority}")
    except Exception:
        pass

    # اگر در محیط لوکال بدون اینترنت یا بدون درگاه تست می‌کنید، شبیه‌ساز داخلی فعال می‌شود
    if settings.DEBUG:
        order.is_paid = True
        order.status = "step1_engineering"
        order.payment_ref_id = "TEST-LOCAL-1405"
        order.save()
        messages.success(
            request,
            "✅ (حالت تست توسعه): پرداخت با موفقیت شبیه‌سازی شد و سفارش به مرحله ۱ (تایید مهندسی) رفت!",
        )
        return redirect("orders:detail", order_id=order.id)

    messages.error(
        request,
        "خطا در ارتباط با درگاه زرین‌پال. لطفاً از گزینه پیش‌فاکتور و واریز بانکی استفاده کنید.",
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
                messages.success(
                    request,
                    f"پرداخت با موفقیت انجام شد! کد رهگیری: {order.payment_ref_id}",
                )
                return redirect("orders:detail", order_id=order.id)
        except Exception:
            pass

    messages.error(
        request,
        "پرداخت ناموفق بود یا توسط کاربر لغو شد. می‌توانید مجدداً تلاش کنید یا فیش بانکی بارگذاری نمایید.",
    )
    return redirect("orders:detail", order_id=order.id)