from django.urls import path
from . import views

app_name = "quoting"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("workspace/", views.quote_workspace_view, name="workspace"),
    path("services/<slug:slug>/", views.service_landing_view, name="service_detail"),
    path("upload-dxf/", views.upload_dxf_view, name="upload_dxf"),
    path("item/<int:item_id>/update/", views.update_item_htmx, name="update_item"),
    path("item/<int:item_id>/delete/", views.delete_item_view, name="delete_item"),
    path("custom-rfq/", views.submit_custom_rfq_view, name="custom_rfq"),
]