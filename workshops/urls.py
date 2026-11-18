from django.urls import path
from . import views

app_name = "workshops"

urlpatterns = [
    path(
        "job/<int:assignment_id>/print/",
        views.work_order_sheet_view,
        name="work_order_sheet",
    ),
]