from django.conf import settings
import requests


def send_order_notification(order):
    """ارسال نوتیفیکیشن فنی به تلگرام یا بله هنگام ثبت سفارش جدید"""
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", "")

    if not bot_token or not chat_id:
        return

    text = (
        f"[METALTECH ORDER ALERT]\n"
        f"شماره سفارش: {order.order_number}\n"
        f"خریدار: {order.customer_name} ({order.company_name or 'حقیقی'})\n"
        f"تلفن: {order.customer_phone}\n"
        f"مبلغ قابل پرداخت: {order.payable_amount:,} تومان\n"
        f"روش تسویه: {order.get_payment_method_display()}\n"
        f"تعداد اقلام: {order.items.count()} ردیف نقشه"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=5)
    except Exception:
        pass