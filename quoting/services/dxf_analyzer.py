from dataclasses import dataclass
import io
import math
from typing import Optional
import ezdxf
from ezdxf import bbox
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import Configuration
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.path import make_path
import matplotlib
import matplotlib.pyplot as plt
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge, polygonize, unary_union

# جلوگیری از باز شدن پنجره گرافیکی در سرور
matplotlib.use("Agg")


@dataclass
class DXFAnalysisResult:
    is_valid: bool
    error_message: str = ""
    width_mm: float = 0.0  # عرض مستطیل دور قطعه (میلی‌متر)
    height_mm: float = 0.0  # طول مستطیل دور قطعه (میلی‌متر)
    area_mm2: float = 0.0  # مساحت مستطیل دور قطعه (میلی‌متر مربع)
    cut_length_mm: float = 0.0  # مجموع طول مسیر برش (میلی‌متر)
    cut_length_m: float = 0.0  # مجموع طول مسیر برش (متر)
    pierce_count: int = 0  # تعداد سوراخ‌کاری اولیه (پیرسینگ)
    svg_preview: str = ""  # کد تصویر پیش‌نمایش SVG


# جدول ضرایب تبدیل واحدهای اتوکد ($INSUNITS) به میلی‌متر
UNIT_TO_MM = {
    0: 1.0,  # Unitless -> فرض پیش‌فرض در ایران میلی‌متر است
    1: 25.4,  # Inches
    2: 304.8,  # Feet
    4: 1.0,  # Millimeters
    5: 10.0,  # Centimeters
    6: 1000.0,  # Meters
}


def analyze_dxf_file(file_path: str) -> DXFAnalysisResult:
    """فایل DXF را می‌خواند و ابعاد، طول برش، تعداد پیرسینگ و پیش‌نمایش SVG را برمی‌گرداند."""
    try:
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()
    except Exception as e:
        return DXFAnalysisResult(
            is_valid=False,
            error_message=f"فایل DXF معتبر نیست یا خراب است: {str(e)}",
        )

    # ۱. تشخیص ضریب تبدیل واحد به میلی‌متر
    insunits = doc.header.get("$INSUNITS", 0)
    scale = UNIT_TO_MM.get(insunits, 1.0)

    lines = []

    # ۲. استخراج تمام المان‌های هندسی (حتی اگر داخل Block باشند)
    def extract_entities(entity_space):
        for entity in entity_space:
            dxftype = entity.dxftype()
            # نادیده گرفتن متن‌ها، اندازه‌گذاری‌ها و هاشورها (که مسیر برش نیستند)
            if dxftype in (
                "TEXT",
                "MTEXT",
                "DIMENSION",
                "HATCH",
                "LEADER",
                "POINT",
                "VIEWPORT",
            ):
                continue

            if dxftype == "INSERT":
                try:
                    for virtual_entity in entity.virtual_entities():
                        extract_entities([virtual_entity])
                except Exception:
                    pass
                continue

            try:
                path = make_path(entity)
                # تبدیل منحنی‌ها و دایره‌ها به نقاط خطی با دقت بالا (0.5 میلی‌متر)
                vertices = list(path.flattening(distance=0.5 / scale))
                if len(vertices) >= 2:
                    coords = [(v.x * scale, v.y * scale) for v in vertices]
                    lines.append(LineString(coords))
            except Exception:
                continue

    extract_entities(msp)

    if not lines:
        return DXFAnalysisResult(
            is_valid=False,
            error_message="هیچ مسیر برش معتبری (خط، دایره یا پلی‌لاین) در نقشه پیدا نشد.",
        )

    # ۳. حذف خطوط تکراری روی هم افتاده (Overlapping Lines) با Shapely
    merged_geometry = unary_union(lines)

    # ۴. محاسبه ابعاد مستطیل دور قطعه (Bounding Box)
    minx, miny, maxx, maxy = merged_geometry.bounds
    width_mm = round(maxx - minx, 2)
    height_mm = round(maxy - miny, 2)

    if width_mm <= 0.1 or height_mm <= 0.1:
        return DXFAnalysisResult(
            is_valid=False, error_message="ابعاد نقشه صفر یا بسیار کوچک است."
        )

    # اگر طراح به اشتباه نقشه را با واحد متر کشیده اما هدر را Unitless گذاشته باشد (مثلا قطعه 0.5 میلی‌متری!)
    if width_mm < 5.0 and height_mm < 5.0 and insunits == 0:
        # هشدار یا اصلاح خودکار مقیاس در صورت نیاز
        pass

    area_mm2 = round(width_mm * height_mm, 2)

    # ۵. محاسبه دقیق طول مسیر برش
    cut_length_mm = round(merged_geometry.length, 2)
    cut_length_m = round(cut_length_mm / 1000.0, 4)

    # ۶. محاسبه تعداد پیرسینگ (تعداد حلقه‌های بسته + مسیرهای باز مجزا)
    pierce_count = _estimate_pierce_count(merged_geometry)

    # ۷. ساخت پیش‌نمایش وکتور (SVG)
    svg_preview = _generate_svg_preview(merged_geometry, minx, miny, maxx, maxy)

    return DXFAnalysisResult(
        is_valid=True,
        width_mm=width_mm,
        height_mm=height_mm,
        area_mm2=area_mm2,
        cut_length_mm=cut_length_mm,
        cut_length_m=cut_length_m,
        pierce_count=pierce_count,
        svg_preview=svg_preview,
    )


def _estimate_pierce_count(geometry) -> int:
    """تخمین تعداد سوراخ‌کاری اولیه لیزر (هر کانتور بسته یا زنجیره مستقل = ۱ پیرسینگ)"""
    try:
        merged_lines = linemerge(geometry)
        if isinstance(merged_lines, LineString):
            return 1
        elif isinstance(merged_lines, MultiLineString):
            return max(1, len(merged_lines.geoms))
        return 1
    except Exception:
        return 1


def _generate_svg_preview(
    geometry, minx: float, miny: float, maxx: float, maxy: float
) -> str:
    """تولید کد SVG تمیز و سبک مستقیم از روی هندسه بدون حاشیه‌های اضافی"""
    width = maxx - minx
    height = maxy - miny
    padding = max(width, height) * 0.08 or 10.0

    vb_minx = minx - padding
    vb_miny = miny - padding
    vb_width = width + (padding * 2)
    vb_height = height + (padding * 2)

    stroke_width = max(vb_width, vb_height) * 0.008

    paths = []
    geoms = geometry.geoms if hasattr(geometry, "geoms") else [geometry]

    for geom in geoms:
        if hasattr(geom, "coords"):
            coords = list(geom.coords)
            if len(coords) >= 2:
                # در SVG محور Y از بالا به پایین است، پس Y را قرینه می‌کنیم تا قطعه برعکس نشود
                d_parts = [f"M {coords[0][0]:.2f} {-coords[0][1]:.2f}"]
                for x, y in coords[1:]:
                    d_parts.append(f"L {x:.2f} {-y:.2f}")
                paths.append(" ".join(d_parts))

    svg_ViewBox = f"{vb_minx:.2f} {-(maxy + padding):.2f} {vb_width:.2f} {vb_height:.2f}"
    path_elements = "\n".join(
        [
            f'<path d="{p}" fill="none" stroke="#38bdf8" stroke-width="{stroke_width:.2f}" stroke-linecap="round" stroke-linejoin="round"/>'
            for p in paths
        ]
    )

    svg_code = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{svg_ViewBox}" class="w-full h-full bg-zinc-950 border border-zinc-800 p-2">
        {path_elements}
    </svg>'''
    return svg_code