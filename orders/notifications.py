import re
from django.conf import settings
import requests

PERSIAN_TO_ENGLISH_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_and_validate_phone(raw_phone: str) -> tuple[bool, str]:
    """تبدیل اعداد فارسی/عربی به انگلیسی و بررسی فرمت استاندارد موبایل ایران (09xxxxxxxxx)"""
    if not raw_phone:
        return False, ""
    cleaned = raw_phone.translate(PERSIAN_TO_ENGLISH_DIGITS).strip()
    cleaned = re.sub(r"[\s\-\(\)]", "", cleaned)
    if cleaned.startswith("+98"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("98"):
        cleaned = "0" + cleaned[2:]

    if re.match(r"^09\d{9}$", cleaned):
        return True, cleaned
    return False, cleaned


def _send_telegram_message(text: str):
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", "")
    if not bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=4)
    except Exception:
        pass


def notify_new_order(order):
    """اعلان صدور پیش‌فاکتور جدید"""
    text = (
        f"[METALTECH // NEW ORDER]\n"
        f"کد سفارش: {order.order_number}\n"
        f"خریدار: {order.customer_name} ({order.company_name or 'حقیقی'})\n"
        f"تلفن: {order.customer_phone}\n"
        f"مبلغ کل: {order.payable_amount:,} تومان\n"
        f"روش تسویه: {order.get_payment_method_display()}\n"
        f"تعداد اقلام: {order.items.count()} ردیف"
    )
    _send_telegram_message(text)


def notify_payment_event(order, event_title: str):
    """اعلان پرداخت آنلاین یا بارگذاری فیش بانکی پایا"""
    text = (
        f"[METALTECH // PAYMENT UPDATE]\n"
        f"رویداد: {event_title}\n"
        f"کد سفارش: {order.order_number}\n"
        f"خریدار: {order.customer_name} ({order.customer_phone})\n"
        f"مبلغ: {order.payable_amount:,} تومان\n"
        f"کد پیگیری پرداخت: {order.payment_ref_id or '-'}"
    )
    _send_telegram_message(text)


def notify_custom_rfq(rfq):
    """اعلان ثبت نقشه دستی / PDF برای مهندس دفتر"""
    design_flag = "بله" if rfq.need_design else "خیر"
    text = (
        f"[METALTECH // CUSTOM RFQ]\n"
        f"مشتری: {rfq.customer_name}\n"
        f"تلفن: {rfq.customer_phone}\n"
        f"نیاز به طراحی مهندسی: {design_flag}\n"
        f"توضیحات: {rfq.description[:200]}"
    )
    _send_telegram_message(text)