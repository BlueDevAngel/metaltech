from catalog.models import Material, SheetThickness
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import CustomRFQ, Quote, QuoteItem
from .services.dxf_analyzer import analyze_dxf_file

# دیتابیس صفحات فرود سئو (SEO Landing Pages) برای کلمات کلیدی اصلی گوگل
SEO_SERVICES = {
    "laser-cutting": {
        "code": "SRV-01",
        "title": "خدمات برش لیزر فلزات و ورق صنعتی",
        "meta_description": "استعلام قیمت آنلاین و لحظه‌ای برش لیزر ورق سیاه ST37، روغنی، استیل و گالوانیزه با آپلود فایل DXF. تحویل از سوله مرکزی بازار آهن شادآباد.",
        "h1": "برش لیزر فایبر CNC ورق‌های صنعتی",
        "subtitle": "محاسبه خودکار طول مسیر برش و پیرسینگ از روی فایل DXF با تلرانس تضمین‌شده ±0.1 میلی‌متر و تامین مستقیم ورق از بازار آهن شادآباد.",
        "specs": [
            ("توان سورس فایبر", "3 کیلووات تا 12 کیلووات"),
            ("حداکثر ابعاد میز کارگیر", "1500×3000 و 2000×6000 میلی‌متر"),
            ("ضخامت قابل برش فولاد (ST37/ST52)", "0.5 الی 25 میلی‌متر"),
            ("ضخامت قابل برش استیل (304/316)", "0.5 الی 15 میلی‌متر (برش با گاز نیتروژن)"),
            ("دقت تکرارپذیری ابعادی", "±0.05 میلی‌متر (استاندارد ISO 2768-m)"),
            ("فرمت‌های ورودی استاندارد", "DXF, DWG (AutoCAD 2004+), STEP"),
        ],
        "technical_notes": [
            "حداقل قطر سوراخ در طراحی نقشه باید حداقل برابر با ضخامت ورق (1x Thickness) در نظر گرفته شود تا از تغییر شکل حرارتی جلوگیری گردد.",
            "کلیه نقشه‌ها قبل از ارسال به دستگاه توسط نرم‌افزار CypCut نستینگ (چیدمان بهینه) شده تا ضایعات ورق به حداقل برسد.",
            "قطعه اول هر تیراژ در سوله مرکزی با کولیس دیجیتال کنترل ابعادی شده و گزارش آن در پنل کارفرما ثبت می‌گردد.",
        ],
    },
    "cnc-bending": {
        "code": "SRV-02",
        "title": "خدمات خمکاری ورق CNC و پرس برک دقیق",
        "meta_description": "خدمات خمکاری CNC ورق فلزی با دستگاه پرس برک چندمحوره در شادآباد. کنترل زاویه خم و محاسبه آنلاین هزینه هر ضرب خم.",
        "h1": "خمکاری ورق با پرس برک CNC هیدرولیک",
        "subtitle": "اجرای خم‌های دقیق صنعتی با کنترل بک‌گیج (Backgauge) اتوماتیک و قالب‌های استاندارد V-Die بدون ترک‌خوردگی یا تغییر فرم سوراخ‌های مجاور خط خم.",
        "specs": [
            ("حداکثر طول خم‌کاری یکپارچه", "3000 الی 4000 میلی‌متر"),
            ("حداکثر تناژ پرس برک", "125 الی 300 تن"),
            ("دقت زاویه خم", "±0.5 درجه در کل طول قطعه"),
            ("ضخامت قابل خم‌کاری", "0.8 الی 15 میلی‌متر"),
            ("محاسبه گسترده ورق (Flat Pattern)", "مبتنی بر K-Factor استاندارد هر ضخامت"),
            ("کنترل کیفیت مرحله‌ای", "بررسی قطعه اول با گونیا و زاویه‌سنج دیجیتال"),
        ],
        "technical_notes": [
            "حداقل لبه خم (Minimum Flange Length) باید حداقل 4 برابر ضخامت ورق به اضافه شعاع داخلی خم باشد تا ورق داخل ماتریس سقوط نکند.",
            "فاصله لبه سوراخ‌ها تا خط خم باید حداقل 2.5 برابر ضخامت ورق باشد تا سوراخ در حین پرس بیضی نشود.",
            "در سفارش‌های ترکیبی (برش لیزر + خم)، مسئولیت تطابق نقشه گسترده و قطعه خم‌شده به صورت یکپارچه بر عهده واحد فنی متال‌تک است.",
        ],
    },
    "welding-assembly": {
        "code": "SRV-03",
        "title": "خدمات جوشکاری صنعتی CO2، آرگون (TIG) و مونتاژ",
        "meta_description": "جوشکاری صنعتی CO2 (MIG/MAG) و آرگون (TIG) روی فیکسچر، قلاویزکاری و مونتاژ قطعات فلزی در سوله اختصاصی بازار آهن شادآباد.",
        "h1": "جوشکاری صنعتی، فیکسچربندی و مونتاژ قطعات",
        "subtitle": "تحویل قطعه و زیرمجموعه تکمیل‌شده (Ready-to-Install) شامل برش، خم، جوشکاری روی میز فیکسچر، سنگ‌زنی و قلاویزکاری در سوله مرکزی.",
        "specs": [
            ("فرآیندهای جوشکاری", "MIG/MAG (CO2)، TIG (آرگون)، جوش گل‌پیچ (Stud)"),
            ("متریال‌های قابل اجرا", "فولاد ساختمانی، استنلس استیل، آلومینیوم"),
            ("عملیات تکمیلی مکانیکی", "قلاویزکاری، خزینه‌کاری، پرس مهره پرچین (PEM)"),
            ("کنترل پیچیدگی حرارتی", "مونتاژ روی فیکسچرهای модуلار و جوش منقطع مهندسی"),
            ("پوشش سطحی و رنگ", "رنگ پودری الکترواستاتیک کوره‌ای، گالوانیزه گرم و سرد"),
            ("بسته‌بندی صنعتی", "پالت‌بندی، شیرینک و تسمه‌کشی جهت ارسال بین‌شهری"),
        ],
        "technical_notes": [
            "برای کاهش زمان مونتاژ و حذف خطای انسانی در جوشکاری، طراحی زبانه‌های قفل‌شونده (Tab & Slot) در فایل برش لیزر توصیه می‌شود.",
            "تمامی قطعات پیش از ورود به کوره رنگ الکترواستاتیک، چربی‌زدایی و فسفاته می‌شوند.",
        ],
    },
    "enclosure-fabrication": {
        "code": "SRV-04",
        "title": "ساخت باکس فلزی، تابلو برق و شاسی ماشین‌آلات صنعتی",
        "meta_description": "تولید سفارشی انواع باکس فلزی، رک، بدنه دستگاه و شاسی‌های صنعتی از ورق روغنی، سیاه و استیل با تحویل یکپارچه در تهران و شادآباد.",
        "h1": "تولید شاسی ماشین‌آلات، کاور صنعتی و باکس فلزی",
        "subtitle": "مدیریت متمرکز کل زنجیره ساخت از تامین ورق در بازار آهن تا برش لیزر، خم CNC، جوشکاری و رنگ کوره‌ای با یک پیش‌فاکتور رسمی واحد.",
        "specs": [
            ("کاربردهای اصلی", "بدنه ماشین‌آلات، شاسی صنعتی، باکس تابلو برق، براکت‌های سازه‌ای"),
            ("تیراژ قابل پذیرش", "از 1 عدد نمونه‌سازی (Prototype) تا تیراژ تولید انبوه"),
            ("ضخامت ورق‌های مصرفی", "ورق روغنی 1 تا 2 میل (پوسته‌ها) / ورق سیاه 3 تا 20 میل (شاسی)"),
            ("مستندات تحویلی", "پیش‌فاکتور رسمی مودیان + گزارش کنترل ابعاد قطعه اول"),
            ("تامین متریال", "مستقیم از بنکداری بازار آهن شادآباد بدون واسطه"),
            ("مدل تحویل", "تحویل درب کارخانه مشتری یا بارگیری از سوله مرکزی"),
        ],
        "technical_notes": [
            "در صورت عدم وجود فایل سه‌بعدی یا DXF، واحد مهندسی متال‌تک امکان مهندسی معکوس از روی نمونه قطعه یا نقشه کاغذی را دارد.",
            "هزینه طراحی مهندسی در صورت ثبت سفارش ساخت تیراژ، از صورت‌حساب نهایی کسر می‌گردد.",
        ],
    },
}


def get_or_create_quote(request) -> Quote:
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    quote_id = request.session.get("active_quote_id")

    if quote_id:
        quote = Quote.objects.filter(id=quote_id).first()
        if quote:
            return quote

    quote = Quote.objects.create(session_key=session_key)
    request.session["active_quote_id"] = str(quote.id)
    return quote


def home_view(request):
    """صفحه اصلی مهندسی (Landing Page) + ماشین‌حساب وزن ورق + جدول نرخ روز"""
    quote = get_or_create_quote(request)
    materials = Material.objects.filter(is_active=True).prefetch_related("thicknesses")
    thicknesses = SheetThickness.objects.filter(
        is_active=True, material__is_active=True
    ).select_related("material")

    return render(
        request,
        "quoting/home.html",
        {
            "quote": quote,
            "materials": materials,
            "thicknesses": thicknesses,
            "services": SEO_SERVICES,
        },
    )


def service_landing_view(request, slug):
    """صفحات فرود تخصصی سئو برای کلمات کلیدی گوگل"""
    service = SEO_SERVICES.get(slug)
    if not service:
        raise Http404("صفحه خدمات مورد نظر یافت نشد.")

    materials = Material.objects.filter(is_active=True).prefetch_related("thicknesses")
    return render(
        request,
        "quoting/service_landing.html",
        {
            "service": service,
            "slug": slug,
            "materials": materials,
            "services": SEO_SERVICES,
        },
    )


def quote_workspace_view(request):
    """میز کار مهندسی استعلام قیمت آنی (CAD Quoting Workspace)"""
    quote = get_or_create_quote(request)
    materials = Material.objects.filter(is_active=True).prefetch_related("thicknesses")
    thicknesses = SheetThickness.objects.filter(
        is_active=True, material__is_active=True
    ).select_related("material")

    return render(
        request,
        "quoting/workspace.html",
        {
            "quote": quote,
            "materials": materials,
            "thicknesses": thicknesses,
        },
    )


@require_POST
def upload_dxf_view(request):
    quote = get_or_create_quote(request)
    uploaded_file = request.FILES.get("dxf_file")

    if not uploaded_file or not uploaded_file.name.lower().endswith(".dxf"):
        messages.error(
            request, "خطای فرمت: فقط فایل مهندسی استاندارد با پسوند .DXF قابل پردازش خودکار است."
        )
        return redirect("quoting:workspace")

    default_thickness = SheetThickness.objects.filter(is_active=True).first()
    if not default_thickness:
        messages.error(request, "خطای سیستم: جدول تعرفه ضخامت ورق در دیتابیس تعریف نشده است.")
        return redirect("quoting:workspace")

    item = QuoteItem(
        quote=quote,
        file_name=uploaded_file.name,
        dxf_file=uploaded_file,
        sheet_thickness=default_thickness,
        quantity=10,
    )
    item.save()

    analysis = analyze_dxf_file(item.dxf_file.path)

    if not analysis.is_valid:
        item.delete()
        messages.error(request, f"خطای هندسه فایل: {analysis.error_message}")
        return redirect("quoting:workspace")

    item.width_mm = analysis.width_mm
    item.height_mm = analysis.height_mm
    item.area_mm2 = analysis.area_mm2
    item.cut_length_m = analysis.cut_length_m
    item.pierce_count = analysis.pierce_count
    item.svg_preview = analysis.svg_preview
    item.save()

    messages.success(
        request,
        f"فایل {item.file_name} پردازش شد. ابعاد باکس: {item.width_mm}x{item.height_mm} میلی‌متر | مسیر برش: {item.cut_length_m} متر.",
    )
    return redirect("quoting:workspace")


@require_POST
def update_item_htmx(request, item_id):
    quote = get_or_create_quote(request)
    item = get_object_or_404(QuoteItem, id=item_id, quote=quote)

    thickness_id = request.POST.get("sheet_thickness")
    quantity = request.POST.get("quantity", 1)
    bend_count = request.POST.get("bend_count", 0)

    if thickness_id:
        item.sheet_thickness = get_object_or_404(
            SheetThickness, id=thickness_id, is_active=True
        )

    try:
        item.quantity = max(1, int(quantity))
        item.bend_count = max(0, int(bend_count))
    except ValueError:
        pass

    item.save()

    thicknesses = SheetThickness.objects.filter(
        is_active=True, material__is_active=True
    ).select_related("material")
    return render(
        request,
        "quoting/partials/quote_dashboard.html",
        {
            "quote": quote,
            "thicknesses": thicknesses,
        },
    )


@require_POST
def delete_item_view(request, item_id):
    quote = get_or_create_quote(request)
    item = get_object_or_404(QuoteItem, id=item_id, quote=quote)
    item.delete()
    return redirect("quoting:workspace")


@require_POST
def submit_custom_rfq_view(request):
    name = request.POST.get("customer_name")
    phone = request.POST.get("customer_phone")
    desc = request.POST.get("description")
    need_design = request.POST.get("need_design") == "on"
    attachment = request.FILES.get("attachment")

    if name and phone and attachment:
        CustomRFQ.objects.create(
            customer_name=name,
            customer_phone=phone,
            description=desc,
            need_design=need_design,
            attachment=attachment,
        )
        messages.success(
            request,
            "درخواست استعلام مهندسی ثبت شد. پیش‌فاکتور رسمی پس از بررسی نقشه توسط واحد فنی به شماره همراه شما ارسال می‌گردد.",
        )
    else:
        messages.error(
            request, "تکمیل نام، شماره تماس و بارگذاری فایل نقشه الزامی است."
        )
    return redirect("quoting:workspace")