from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout_view, name="checkout"),
    path("<uuid:order_id>/", views.order_detail_view, name="detail"),
    path(
        "<uuid:order_id>/invoice/",
        views.official_invoice_view,
        name="invoice",
    ),
    path(
        "<uuid:order_id>/upload-receipt/",
        views.upload_receipt_view,
        name="upload_receipt",
    ),
    path(
        "<uuid:order_id>/pay/",
        views.zarinpal_request_view,
        name="zarinpal_pay",
    ),
    path(
        "<uuid:order_id>/verify/",
        views.zarinpal_verify_view,
        name="zarinpal_verify",
    ),
]