from catalog.models import Material, SheetThickness
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "پر کردن اولیه دیتابیس با متریال‌ها و ضخامت‌های استاندارد بازار آهن"

    def handle(self, *args, **kwargs):
        materials_data = [
            {
                "name": "ورق سیاه (فولاد ST37)",
                "code": "st37",
                "density": 7.85,
                "price": 44000,
                "thicknesses": [
                    (2.0, 12000, 600, 4000),
                    (3.0, 16000, 800, 5500),
                    (4.0, 22000, 1000, 7000),
                    (5.0, 28000, 1300, 9000),
                    (6.0, 35000, 1600, 12000),
                    (8.0, 48000, 2200, 18000),
                    (10.0, 65000, 3000, 25000),
                    (12.0, 85000, 4000, 35000),
                    (15.0, 115000, 5500, 50000),
                ],
            },
            {
                "name": "ورق روغنی (نورد سرد)",
                "code": "cold-rolled",
                "density": 7.85,
                "price": 52000,
                "thicknesses": [
                    (1.0, 8000, 400, 3000),
                    (1.25, 9500, 450, 3200),
                    (1.5, 10500, 500, 3500),
                    (2.0, 12500, 600, 4000),
                ],
            },
            {
                "name": "ورق گالوانیزه",
                "code": "galvanized",
                "density": 7.85,
                "price": 58000,
                "thicknesses": [
                    (1.0, 9000, 450, 3000),
                    (1.5, 11500, 550, 3500),
                    (2.0, 14000, 650, 4500),
                ],
            },
            {
                "name": "ورق استیل ۳۰۴ (بگیر/نگیر)",
                "code": "stainless-304",
                "density": 7.93,
                "price": 210000,
                "thicknesses": [
                    (1.0, 15000, 800, 5000),
                    (1.5, 20000, 1000, 6000),
                    (2.0, 26000, 1300, 7500),
                    (3.0, 38000, 1800, 10000),
                ],
            },
        ]

        for m_data in materials_data:
            mat, _ = Material.objects.update_or_create(
                code=m_data["code"],
                defaults={
                    "name": m_data["name"],
                    "density": m_data["density"],
                    "base_price_per_kg": m_data["price"],
                },
            )
            for thick, cut_p, pierce_p, bend_p in m_data["thicknesses"]:
                SheetThickness.objects.update_or_create(
                    material=mat,
                    thickness_mm=thick,
                    defaults={
                        "cut_price_per_meter": cut_p,
                        "pierce_price": pierce_p,
                        "bend_price_per_stroke": bend_p,
                    },
                )
        self.stdout.write(
            self.style.SUCCESS(
                "✅ دیتابیس متریال‌ها و ضخامت‌ها با موفقیت پر شد!"
            )
        )