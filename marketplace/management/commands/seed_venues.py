"""
Seed venue categories: Paddle Tennis, Big Tennis, PC Club, Billiard, Restaurant.
Matches the current models.py structure (Category.icon_class).
"""

import random
from datetime import time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from faker import Faker

from marketplace.models import (
    Category, Salon, Service, Master, SalonWorkingHours, Address
)

# ---------------------------------------------------------------------------
# VENUE DEFINITIONS
# ---------------------------------------------------------------------------
VENUES = [
    {
        "slug": "paddle-tennis",
        "name_ru": "Паддл-теннис",
        "name_en": "Paddle Tennis",
        "name_uz": "Paddl-tennis",
        "icon_class": "bi bi-trophy",
        "sub": [
            ("Крытые корты", "Indoor Courts", "Yopiq maydonlar"),
            ("Открытые корты", "Outdoor Courts", "Ochiq maydonlar"),
        ],
        "resource_prefix": ("Корт", "Court", "Maydon"),
        "resource_count": 4,
        "services": [
            ("Аренда 1 час", "1-hour rental", "1 soatlik ijara", 60, 80000),
            ("Аренда 2 часа", "2-hour rental", "2 soatlik ijara", 120, 150000),
        ],
        "open": time(8, 0),
        "close": time(23, 0),
    },
    {
        "slug": "big-tennis",
        "name_ru": "Большой теннис",
        "name_en": "Big Tennis",
        "name_uz": "Katta tennis",
        "icon_class": "bi bi-dribbble",
        "sub": [
            ("Хард корты", "Hard Courts", "Qattiq maydonlar"),
            ("Грунтовые корты", "Clay Courts", "Tuproq maydonlar"),
        ],
        "resource_prefix": ("Корт", "Court", "Maydon"),
        "resource_count": 3,
        "services": [
            ("Аренда корта 1 час", "1-hour court rental", "Maydon ijarasi 1 soat", 60, 100000),
            ("Аренда корта 2 часа", "2-hour court rental", "Maydon ijarasi 2 soat", 120, 180000),
        ],
        "open": time(7, 0),
        "close": time(23, 0),
    },
    {
        "slug": "pc-club",
        "name_ru": "Компьютерный клуб",
        "name_en": "PC Club",
        "name_uz": "Kompyuter klubi",
        "icon_class": "bi bi-pc-display",
        "sub": [
            ("Игровые ПК", "Gaming PCs", "O'yin kompyuterlari"),
            ("VIP-кабины", "VIP Booths", "VIP kabinalari"),
            ("PS5 станции", "PS5 Stations", "PS5 stantsiyalari"),
        ],
        "resource_prefix": ("ПК", "PC", "PC"),
        "resource_count": 15,
        "services": [
            ("1 час", "1 hour", "1 soat", 60, 15000),
            ("2 часа", "2 hours", "2 soat", 120, 28000),
            ("5 часов", "5 hours", "5 soat", 300, 65000),
            ("Ночной пакет (8ч)", "Night pack (8h)", "Tungi paket (8s)", 480, 90000),
        ],
        "open": time(0, 0),
        "close": time(23, 59),
    },
    {
        "slug": "billiard",
        "name_ru": "Бильярд",
        "name_en": "Billiard",
        "name_uz": "Bilyard",
        "icon_class": "bi-bullseye",
        "sub": [
            ("Русская пирамида", "Russian Pyramid", "Rus piramidasi"),
            ("Американский пул", "American Pool", "Amerikan pul"),
        ],
        "resource_prefix": ("Стол", "Table", "Stol"),
        "resource_count": 6,
        "services": [
            ("1 час", "1 hour", "1 soat", 60, 40000),
            ("2 часа", "2 hours", "2 soat", 120, 75000),
        ],
        "open": time(12, 0),
        "close": time(2, 0),
    },
    {
        "slug": "restaurant",
        "name_ru": "Рестораны",
        "name_en": "Restaurants",
        "name_uz": "Restoranlar",
        "icon_class": "bi bi-cup-hot",
        "sub": [
            ("Европейская кухня", "European Cuisine", "Yevropa oshxonasi"),
            ("Азиатская кухня", "Asian Cuisine", "Osiyo oshxonasi"),
            ("Узбекская кухня", "Uzbek Cuisine", "O'zbek oshxonasi"),
        ],
        "resource_prefix": ("Стол", "Table", "Stol"),
        "resource_count": 10,
        "services": [
            ("Бронь на 2 персон", "Reservation for 2", "2 kishilik bron", 30, 0),
            ("Бронь на 4 персон", "Reservation for 4", "4 kishilik bron", 30, 0),
            ("Бронь на 6 персон", "Reservation for 6", "6 kishilik bron", 30, 0),
            ("Бронь на 8 персон", "Reservation for 8", "8 kishilik bron", 30, 0),
            ("Бронь на 10 персон", "Reservation for 10", "10 kishilik bron", 30, 0),
            ("Бронь на 12 персон", "Reservation for 12", "12 kishilik bron", 30, 0),
            ("Бронь на 14 персон", "Reservation for 14", "14 kishilik bron", 30, 0),
            ("Бронь на 14+ персон", "Reservation for 14+", "14+ kishilik bron", 30, 0),
        ],
        "open": time(10, 0),
        "close": time(23, 0),
    },
]

TASHKENT_DISTRICTS = [
    "Mirzo Ulug'bek", "Chilonzor", "Yunusobod", "Shayxontohur",
    "Yashnobod", "Yakkasaroy", "Olmazor", "Mirobod", "Sergeli", "Bektemir",
]

class Command(BaseCommand):
    help = "Seed venue categories based on actual Category model fields."

    def add_arguments(self, parser):
        parser.add_argument("--salons-per-sub", type=int, default=2)
        parser.add_argument("--reset", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        fake = Faker("ru_RU")
        User = get_user_model()
        salons_per_sub = opts["salons_per_sub"]

        if opts["reset"]:
            slugs = [v["slug"] for v in VENUES]
            Category.objects.filter(slug__in=slugs).delete()
            self.stdout.write(self.style.WARNING("Reset category data."))

        demo_owner, _ = User.objects.get_or_create(
            username="demo_venue_owner",
            defaults={"email": "demo_owner@example.com"},
        )

        for venue in VENUES:
            parent = self._ensure_category(
                name_ru=venue["name_ru"],
                name_en=venue["name_en"],
                name_uz=venue["name_uz"],
                slug=venue["slug"],
                icon_class=venue["icon_class"],
                parent=None
            )
            for sub_ru, sub_en, sub_uz in venue["sub"]:
                sub = self._ensure_category(
                    name_ru=sub_ru,
                    name_en=sub_en,
                    name_uz=sub_uz,
                    slug=self._unique_slug(f"{venue['slug']}-{slugify(sub_en)}"),
                    icon_class=venue["icon_class"],
                    parent=parent
                )
                for i in range(salons_per_sub):
                    salon = self._create_salon(fake, demo_owner, sub, venue)
                    self._create_resources(salon, venue)
                    self._create_services(salon, venue)
                    self._create_working_hours(salon, venue)

        self.stdout.write(self.style.SUCCESS("Success: Seeding complete."))

    def _ensure_category(self, **kwargs):
        # We find by slug, then apply the rest of the fields
        slug = kwargs.pop('slug')
        cat, created = Category.objects.get_or_create(slug=slug, defaults=kwargs)
        if not created:
            for k, v in kwargs.items():
                setattr(cat, k, v)
            cat.save()
        return cat

    def _unique_slug(self, base):
        slug = base
        n = 2
        while Category.objects.filter(slug=slug).exists():
            slug, n = f"{base}-{n}", n + 1
        return slug

    def _create_salon(self, fake, owner, category, venue):
        district = random.choice(TASHKENT_DISTRICTS)
        brand_pool = {
            "paddle-tennis": ["Padel Arena", "Smash Club"],
            "big-tennis": ["Grand Tennis", "Match Point"],
            "pc-club": ["CyberZone", "GameHub", "Matrix PC", "Respawn"],
            "billiard": ["Pyramid Hall", "Pool Kings"],
            "restaurant": ["Besh Qozon", "Sofra", "Old Tashkent"],
        }
        brand = random.choice(brand_pool.get(venue["slug"], ["Club"]))
        salon = Salon.objects.create(
            name=f"{brand} {district}", owner=owner, category=category,
            address=f"{district}, {fake.street_address()}",
            phone=f"+998{random.randint(70,99)}{random.randint(1000000,9999999)}"
        )
        Address.objects.create(
            salon=salon, full_address=salon.address,
            latitude=Decimal(f"{41.2 + random.uniform(-0.1, 0.15):.6f}"),
            longitude=Decimal(f"{69.2 + random.uniform(-0.1, 0.15):.6f}")
        )
        return salon

    def _create_resources(self, salon, venue):
        pre_ru, pre_en, pre_uz = venue["resource_prefix"]
        for i in range(1, venue["resource_count"] + 1):
            name = f"{pre_ru} {i}"
            Master.objects.create(
                salon=salon, name=name, is_active=True,
                specialization_ru=venue["name_ru"],
                specialization_en=venue["name_en"],
                specialization_uz=venue["name_uz"]
            )

    def _create_services(self, salon, venue):
        for n_ru, n_en, n_uz, dur, pr in venue["services"]:
            Service.objects.create(
                salon=salon, name_ru=n_ru, name_en=n_en, name_uz=n_uz,
                price=Decimal(pr), duration_minutes=dur
            )

    def _create_working_hours(self, salon, venue):
        open_t, close_t = venue["open"], venue["close"]
        if close_t <= open_t: close_t = time(23, 59)
        for weekday in range(7):
            SalonWorkingHours.objects.update_or_create(
                salon=salon, weekday=weekday,
                defaults={"is_closed": False, "open_time": open_t, "close_time": close_t}
            )