from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from .models import JobAssignment


@staff_member_required
def work_order_sheet_view(request, assignment_id):
    """چاپ برگه دستور ساخت کارگاهی (بدون نام و قیمت مشتری نهایی برای جلوگیری از دور زدن پلتفرم)"""
    assignment = get_object_or_404(JobAssignment, id=assignment_id)
    return render(
        request, "workshops/work_order_print.html", {"assignment": assignment}
    )