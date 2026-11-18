import os
from django.conf import settings
from django.core.management.base import BaseCommand
import ezdxf
from quoting.services.dxf_analyzer import analyze_dxf_file


class Command(BaseCommand):
    help = "ساخت یک فایل DXF نمونه (فلنج 200x200 با 5 سوراخ) و تست موتور تحلیل‌گر"

    def handle(self, *args, **kwargs):
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        sample_path = os.path.join(settings.MEDIA_ROOT, "sample_flange.dxf")

        # ۱. ساخت یک نقشه واقعی DXF با کد پایتون
        doc = ezdxf.new("R2010")
        doc.header["$INSUNITS"] = 4  # واحد: میلی‌متر
        msp = doc.modelspace()

        # کشیدن کادر بیرونی قطعه: مربع 200 در 200 میلی‌متر (محیط = 800 میلی‌متر)
        msp.add_lwpolyline(
            [(0, 0), (200, 0), (200, 200), (0, 200), (0, 0)], close=True
        )

        # کشیدن 4 سوراخ به شعاع 10 میلی‌متر در چهار گوشه
        for x, y in [(30, 30), (170, 30), (170, 170), (30, 170)]:
            msp.add_circle((x, y), radius=10)

        # کشیدن 1 سوراخ بزرگ در مرکز به شعاع 40 میلی‌متر
        msp.add_circle((100, 100), radius=40)

        doc.saveas(sample_path)
        self.stdout.write(
            self.style.WARNING(f"📁 فایل نمونه ساخته شد در: {sample_path}")
        )

        # ۲. اجرای موتور تحلیل‌گر MetalTech روی فایل
        result = analyze_dxf_file(sample_path)

        if result.is_valid:
            self.stdout.write(
                self.style.SUCCESS("\n✅ تحلیل هندسی با موفقیت انجام شد:")
            )
            self.stdout.write(
                f"📏 ابعاد قطعه (Bounding Box): {result.width_mm} × {result.height_mm} میلی‌متر"
            )
            self.stdout.write(
                f"📐 مساحت مستطیل ورق مصرفی: {result.area_mm2:,} میلی‌متر مربع"
            )
            self.stdout.write(
                f"✂️ مجموع طول مسیر برش لیزر: {result.cut_length_mm:,} میلی‌متر ({result.cut_length_m} متر)"
            )
            self.stdout.write(
                f"🔥 تعداد پیرسینگ (سوراخ‌کاری اولیه): {result.pierce_count} عدد (۱ کادر بیرونی + ۵ سوراخ داخلی)"
            )
            self.stdout.write(
                f"🖼️ پیش‌نمایش SVG تولید شد (طول رشته: {len(result.svg_preview)} کاراکتر)"
            )
        else:
            self.stdout.write(self.style.ERROR(f"❌ خطا: {result.error_message}"))