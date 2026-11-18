from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("track/", views.track_order_view, name="track"),
    path("checkout/", views.checkout_view, name="checkout"),
    path("<uuid:order_id>/", views.order_detail_view, name="detail"),
    path("<uuid:order_id>/invoice/", views.official_invoice_view, name="invoice"),
    path("<uuid:order_id>/refresh-price/", views.refresh_order_price_view, name="refresh_price"),
    path("<uuid:order_id>/upload-receipt/", views.upload_receipt_view, name="upload_receipt"),
    path("<uuid:order_id>/pay/", views.zarinpal_request_view, name="zarinpal_pay"),
    path("<uuid:order_id>/verify/", views.zarinpal_verify_view, name="zarinpal_verify"),
]