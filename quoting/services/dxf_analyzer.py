from dataclasses import dataclass
from ezdxf.path import make_path
import ezdxf
import matplotlib
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge, snap, unary_union

matplotlib.use("Agg")

# حداکثر تعداد خطوط مجاز در یک فایل برای جلوگیری از قفل شدن سرور (DoS Protection)
MAX_ENTITIES_LIMIT = 5000

# لایه‌های غیربرشی استاندارد در اتوکد (کادر، اندازه، محور، خطوط مخفی)
IGNORED_LAYERS = {
    "DEFPOINTS",
    "DIM",
    "DIMENSIONS",
    "DIMENSION",
    "TITLE",
    "TITLEBLOCK",
    "BORDER",
    "FRAME",
    "TEXT",
    "ANNOTATION",
    "HATCH",
    "CENTER",
    "CENTERLINE",
    "HIDDEN",
    "CONSTRUCTION",
    "AXIS",
    "VIEWPORT",
}

# خطوط خط‌چین و محور که نباید توسط لیزر بریده شوند
IGNORED_LINETYPES = {
    "DASHED",
    "CENTER",
    "HIDDEN",
    "PHANTOM",
    "DOT",
    "DASHDOT",
    "BORDER",
}

# نگاشت کد واحد هدر اتوکد ($INSUNITS) به واحدهای استاندارد سیستم ما
INSUNITS_TO_UNIT_CODE = {
    0: "mm",    # Unitless -> پیش‌فرض اولیه میلی‌متر
    1: "inch",  # Inches
    4: "mm",    # Millimeters
    5: "cm",    # Centimeters
    6: "m",     # Meters
}


@dataclass
class DXFAnalysisResult:
    is_valid: bool
    error_message: str = ""
    detected_unit: str = "mm"
    raw_width: float = 0.0       # عرض خام در مختصات فایل
    raw_height: float = 0.0      # طول خام در مختصات فایل
    raw_cut_length: float = 0.0  # طول برش خام در مختصات فایل
    pierce_count: int = 0        # تعداد پیرسینگ (مسیرهای بسته/مستقل)
    svg_preview: str = ""        # تصویر وکتور قطعه


def analyze_dxf_file(file_path: str) -> DXFAnalysisResult:
    """فایل DXF را با فیلتر کردن کادرها و لایه‌های غیربرشی تحلیل می‌کند."""
    try:
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()
    except Exception as e:
        return DXFAnalysisResult(
            is_valid=False,
            error_message=f"ساختار فایل DXF استاندارد نیست یا آسیب دیده است: {str(e)}",
        )

    insunits = doc.header.get("$INSUNITS", 0)
    detected_unit = INSUNITS_TO_UNIT_CODE.get(insunits, "mm")

    lines = []
    entity_counter = 0

    def extract_entities(entity_space):
        nonlocal entity_counter
        for entity in entity_space:
            entity_counter += 1
            if entity_counter > MAX_ENTITIES_LIMIT:
                raise ValueError(
                    f"تعداد المان‌های نقشه بیش از حد مجاز ({MAX_ENTITIES_LIMIT} خط) است. لطفاً هاشورها و نقشه‌های اضافی را پاک کنید."
                )

            dxftype = entity.dxftype()
            if dxftype in (
                "TEXT",
                "MTEXT",
                "DIMENSION",
                "HATCH",
                "LEADER",
                "POINT",
                "VIEWPORT",
                "ATTRIB",
                "ATTDEF",
                "IMAGE",
                "SOLID",
            ):
                continue

            # فیلتر کردن لایه‌های کادر و اندازه‌گذاری
            layer_name = (entity.dxf.get("layer", "") or "").upper().strip()
            if layer_name in IGNORED_LAYERS or layer_name.startswith("DIM"):
                continue

            # فیلتر کردن خطوط راهنما و خط‌چین
            linetype_name = (entity.dxf.get("linetype", "") or "").upper().strip()
            if linetype_name in IGNORED_LINETYPES:
                continue

            if dxftype == "INSERT":
                try:
                    for virtual_entity in entity.virtual_entities():
                        extract_entities([virtual_entity])
                except ValueError:
                    raise
                except Exception:
                    pass
                continue

            try:
                path = make_path(entity)
                vertices = list(path.flattening(distance=0.25))
                if len(vertices) >= 2:
                    coords = [(v.x, v.y) for v in vertices]
                    line = LineString(coords)
                    if line.length > 0.001:
                        lines.append(line)
            except Exception:
                continue

    try:
        extract_entities(msp)
    except ValueError as limit_err:
        return DXFAnalysisResult(is_valid=False, error_message=str(limit_err))

    if not lines:
        return DXFAnalysisResult(
            is_valid=False,
            error_message="هیچ خط برش معتبری در فایل یافت نشد. مطمئن شوید نقشه در لایه DEFPOINTS یا به صورت Block قفل‌شده نباشد.",
        )

    # ۱. حذف خطوط تکراری روی هم افتاده (Overlapping Lines)
    merged_geometry = unary_union(lines)

    # ۲. محاسبه کادر محاطی خام (Raw Bounding Box)
    minx, miny, maxx, maxy = merged_geometry.bounds
    raw_width = round(maxx - minx, 3)
    raw_height = round(maxy - miny, 3)

    if raw_width <= 0.001 or raw_height <= 0.001:
        return DXFAnalysisResult(
            is_valid=False,
            error_message="ابعاد هندسی استخراج‌شده صفر است (نقشه دوبعدی معتبر نیست).",
        )

    # تشخیص هوشمند واحد: اگر فایل Unitless است و ابعاد زیر 15 واحد است، احتمالاً به سانتی‌متر کشیده شده
    if insunits == 0 and max(raw_width, raw_height) < 15.0:
        detected_unit = "cm"

    # ۳. طول کل مسیر برش در واحد خام فایل
    raw_cut_length = round(merged_geometry.length, 3)

    # ۴. شمارش دقیق پیرسینگ با جوش دادن درزهای ریز (Snap Tolerance)
    snap_tol = max(raw_width, raw_height) * 0.0005  # تلرانس نسبی (حدود 0.1 میلی‌متر)
    pierce_count = _estimate_pierce_count(merged_geometry, snap_tol)

    # ۵. تولید پیش‌نمایش وکتور مهندسی (SVG)
    svg_preview = _generate_svg_preview(merged_geometry, minx, miny, maxx, maxy)

    return DXFAnalysisResult(
        is_valid=True,
        detected_unit=detected_unit,
        raw_width=raw_width,
        raw_height=raw_height,
        raw_cut_length=raw_cut_length,
        pierce_count=pierce_count,
        svg_preview=svg_preview,
    )


def _estimate_pierce_count(geometry, tolerance: float = 0.05) -> int:
    """با استفاده از Snap درزهای ریز بین خطوط را می‌بندد تا تعداد واقعی کانتورها شمرده شود."""
    try:
        snapped_geom = snap(geometry, geometry, tolerance)
        merged_lines = linemerge(snapped_geom)
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
    width = maxx - minx
    height = maxy - miny
    padding = max(width, height) * 0.08 or 1.0

    vb_minx = minx - padding
    vb_width = width + (padding * 2)
    vb_height = height + (padding * 2)
    stroke_width = max(vb_width, vb_height) * 0.008

    paths = []
    geoms = geometry.geoms if hasattr(geometry, "geoms") else [geometry]

    for geom in geoms:
        if hasattr(geom, "coords"):
            coords = list(geom.coords)
            if len(coords) >= 2:
                d_parts = [f"M {coords[0][0]:.3f} {-coords[0][1]:.3f}"]
                for x, y in coords[1:]:
                    d_parts.append(f"L {x:.3f} {-y:.3f}")
                paths.append(" ".join(d_parts))

    svg_viewbox = f"{vb_minx:.3f} {-(maxy + padding):.3f} {vb_width:.3f} {vb_height:.3f}"
    path_elements = "\n".join(
        [
            f'<path d="{p}" fill="none" stroke="#f59e0b" stroke-width="{stroke_width:.3f}" stroke-linecap="round" stroke-linejoin="round"/>'
            for p in paths
        ]
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{svg_viewbox}" class="w-full h-full bg-zinc-950 border border-zinc-800 p-2">
        {path_elements}
    </svg>"""