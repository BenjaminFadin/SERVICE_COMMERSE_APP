"""
Seed new venue categories: Paddle Tennis, Big Tennis, Computer Cafe,
Billiard, Restaurant.

Reuses existing models:
  - Category       -> the venue type
  - Salon          -> a specific venue (club, cafe, restaurant)
  - Master         -> a resource (court, PC, table). Admin can add infinite.
  - Service        -> a bookable option ("1 hour rental", "Reservation", ...)
  - SalonWorkingHours -> schedule per weekday

Run with:
    python manage.py seed_venues
    python manage.py seed_venues --salons-per-sub 2
    python manage.py seed_venues --reset     # wipe only these categories first
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
# Each venue has:
#   - parent category (name ru/en/uz + slug + icon)
#   - subcategories
#   - resource_prefix  -> how to name masters (Court #, PC-, Table )
#   - resource_count   -> how many to create on seed (admin can add more later)
#   - services         -> list of (name_ru, name_en, name_uz, duration_min, price_uzs)
#   - working_hours    -> default open/close per weekday
# ---------------------------------------------------------------------------

VENUES = [
    # ------------------------------------------------------------------
    # 🎾 PADDLE TENNIS
    # ------------------------------------------------------------------
    {
        "slug": "paddle-tennis",
        "name_ru": "Паддл-теннис",
        "name_en": "Paddle Tennis",
        "name_uz": "Paddl-tennis",
        "icon": "bi bi-trophy",
        "sub": [
            ("Крытые корты",   "Indoor Courts",   "Yopiq maydonlar"),
            ("Открытые корты", "Outdoor Courts",  "Ochiq maydonlar"),
            ("Ночная игра",    "Night Play",      "Tungi o'yin"),
            ("Тренировки",     "Lessons",         "Mashg'ulotlar"),
        ],
        "resource_prefix": ("Корт", "Court", "Maydon"),
        "resource_count": 4,
        "services": [
            # (name_ru, name_en, name_uz, duration_min, price_uzs)
            ("Аренда 1 час",          "1-hour rental",       "1 soatlik ijara",       60,  80_000),
            ("Аренда 2 часа",         "2-hour rental",       "2 soatlik ijara",      120, 150_000),
            ("Корт + тренер (1 час)", "Court + coach (1h)",  "Maydon + trener (1s)",  60, 150_000),
        ],
        "open":  time(8, 0),
        "close": time(23, 0),
    },

    # ------------------------------------------------------------------
    # 🎾 BIG TENNIS
    # ------------------------------------------------------------------
    {
        "slug": "big-tennis",
        "name_ru": "Большой теннис",
        "name_en": "Big Tennis",
        "name_uz": "Katta tennis",
        "icon": "bi bi-circle",
        "sub": [
            ("Хард корты",      "Hard Courts",     "Qattiq maydonlar"),
            ("Грунтовые корты", "Clay Courts",     "Tuproq maydonlar"),
            ("Крытые корты",    "Indoor Courts",   "Yopiq maydonlar"),
            ("Тренировки",      "Lessons",         "Mashg'ulotlar"),
        ],
        "resource_prefix": ("Корт", "Court", "Maydon"),
        "resource_count": 3,
        "services": [
            ("Аренда корта 1 час",      "1-hour court rental", "Maydon ijarasi 1 soat",  60, 100_000),
            ("Аренда корта 2 часа",     "2-hour court rental", "Maydon ijarasi 2 soat", 120, 180_000),
            ("Индивидуальный урок",     "Private lesson",      "Shaxsiy dars",           60, 200_000),
        ],
        "open":  time(7, 0),
        "close": time(23, 0),
    },

    # ------------------------------------------------------------------
    # 💻 COMPUTER CAFE
    # ------------------------------------------------------------------
    {
        "slug": "computer-cafe",
        "name_ru": "Компьютерный клуб",
        "name_en": "Computer Cafe",
        "name_uz": "Kompyuter klubi",
        "icon": "bi bi-pc-display",
        "sub": [
            ("Игровые ПК",    "Gaming PCs",      "O'yin kompyuterlari"),
            ("VIP-кабины",    "VIP Booths",      "VIP kabinalari"),
            ("PS5 станции",   "PS5 Stations",    "PS5 stantsiyalari"),
            ("Обычные ПК",    "Standard PCs",    "Oddiy kompyuterlar"),
        ],
        "resource_prefix": ("ПК", "PC", "PC"),
        "resource_count": 15,
        "services": [
            ("1 час",               "1 hour",              "1 soat",                60,  15_000),
            ("2 часа",              "2 hours",             "2 soat",               120,  28_000),
            ("5 часов",             "5 hours",             "5 soat",               300,  65_000),
            ("Ночной пакет (8ч)",   "Night pack (8h)",     "Tungi paket (8s)",     480,  90_000),
        ],
        "open":  time(0, 0),   # 24/7 vibe
        "close": time(23, 59),
    },

    # ------------------------------------------------------------------
    # 🎱 BILLIARD
    # ------------------------------------------------------------------
    {
        "slug": "billiard",
        "name_ru": "Бильярд",
        "name_en": "Billiard",
        "name_uz": "Bilyard",
        "icon": "bi bi-circle-fill",
        "sub": [
            ("Русская пирамида", "Russian Pyramid", "Rus piramidasi"),
            ("Американский пул", "American Pool",   "Amerikan pul"),
            ("Снукер",           "Snooker",         "Snuker"),
        ],
        "resource_prefix": ("Стол", "Table", "Stol"),
        "resource_count": 6,
        "services": [
            ("1 час",                "1 hour",              "1 soat",              60,  40_000),
            ("2 часа",               "2 hours",             "2 soat",             120,  75_000),
            ("VIP-зал (3 часа)",     "VIP room (3h)",       "VIP-xona (3s)",     180, 180_000),
        ],
        "open":  time(12, 0),
        "close": time(2, 0),   # closes at 2am — your model will clamp
    },

    # ------------------------------------------------------------------
    # 🍽️ RESTAURANT
    # ------------------------------------------------------------------
    {
        "slug": "restaurant",
        "name_ru": "Рестораны",
        "name_en": "Restaurants",
        "name_uz": "Restoranlar",
        "icon": "bi bi-cup-hot",
        "sub": [
            ("Европейская кухня", "European Cuisine", "Yevropa oshxonasi"),
            ("Азиатская кухня",   "Asian Cuisine",    "Osiyo oshxonasi"),
            ("Узбекская кухня",   "Uzbek Cuisine",    "O'zbek oshxonasi"),
            ("Фастфуд",           "Fast Food",        "Fastfud"),
            ("Кафе",              "Cafe",             "Kafe"),
        ],
        "resource_prefix": ("Стол", "Table", "Stol"),
        "resource_count": 8,
        # Restaurant: "just time slot, no visible end time".
        # We still need duration_minutes (model computes end_time); use 30min hold.
        "services": [
            ("Бронь на 2 персон", "Reservation for 2", "2 kishilik bron", 30, 0),
            ("Бронь на 4 персон", "Reservation for 4", "4 kishilik bron", 30, 0),
            ("Бронь на 6 персон", "Reservation for 6", "6 kishilik bron", 30, 0),
        ],
        "open":  time(10, 0),
        "close": time(23, 0),
    },
]


TASHKENT_DISTRICTS = [
    "Mirzo Ulug'bek", "Chilonzor", "Yunusobod", "Shayxontohur",
    "Yashnobod", "Yakkasaroy", "Olmazor", "Mirobod", "Sergeli", "Bektemir",
]


# ---------------------------------------------------------------------------
# COMMAND
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Seed venue categories (tennis, computer cafe, billiard, restaurant)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--salons-per-sub",
            type=int,
            default=2,
            help="Number of demo salons to create per subcategory (default: 2).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing venue categories (and their salons) before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        fake = Faker("ru_RU")
        User = get_user_model()
        salons_per_sub = opts["salons_per_sub"]

        # ------- 1. OPTIONAL RESET -------
        if opts["reset"]:
            slugs = [v["slug"] for v in VENUES]
            to_delete = Category.objects.filter(slug__in=slugs)
            if to_delete.exists():
                # deleting parent cascades to children & salons
                count = to_delete.count()
                to_delete.delete()
                self.stdout.write(self.style.WARNING(
                    f"Deleted {count} existing parent categories (and children/salons)."
                ))

        # ------- 2. ENSURE A DEMO OWNER USER EXISTS -------
        # Fallback owner so salons always have an owner.
        demo_owner, _ = User.objects.get_or_create(
            username="demo_venue_owner",
            defaults={"email": "demo_owner@example.com"},
        )

        # ------- 3. CREATE CATEGORIES + SALONS -------
        total_salons = 0
        total_services = 0
        total_resources = 0

        for venue in VENUES:
            parent = self._ensure_category(
                name_ru=venue["name_ru"],
                name_en=venue["name_en"],
                name_uz=venue["name_uz"],
                slug=venue["slug"],
                icon=venue["icon"],
                parent=None,
            )
            self.stdout.write(self.style.SUCCESS(
                f"📂 Parent: {parent.name_ru} ({parent.slug})"
            ))

            for sub_ru, sub_en, sub_uz in venue["sub"]:
                sub = self._ensure_category(
                    name_ru=sub_ru,
                    name_en=sub_en,
                    name_uz=sub_uz,
                    slug=self._unique_slug(f"{venue['slug']}-{slugify(sub_en)}"),
                    icon=venue["icon"],
                    parent=parent,
                )
                self.stdout.write(f"   └─ {sub.name_ru}")

                for i in range(salons_per_sub):
                    salon = self._create_salon(
                        fake=fake,
                        owner=demo_owner,
                        category=sub,
                        venue=venue,
                    )
                    total_salons += 1

                    # Create "masters" = resources (courts / PCs / tables)
                    res_created = self._create_resources(salon, venue)
                    total_resources += res_created

                    # Create services
                    svc_created = self._create_services(salon, venue)
                    total_services += svc_created

                    # Create working hours
                    self._create_working_hours(salon, venue)

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Done. Salons: {total_salons}  Services: {total_services}  "
            f"Resources: {total_resources}"
        ))
        self.stdout.write(
            "Admin can add more courts/PCs/tables via Django admin "
            "(Marketplace → Masters)."
        )

    # ---------------------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------------------

    def _ensure_category(self, *, name_ru, name_en, name_uz, slug, icon, parent):
        cat, created = Category.objects.get_or_create(
            slug=slug,
            defaults={
                "name_ru": name_ru,
                "name_en": name_en,
                "name_uz": name_uz,
                "icon_class": icon,
                "parent": parent,
            },
        )
        # If it already existed, make sure translations + parent are correct
        if not created:
            cat.name_ru = name_ru
            cat.name_en = name_en
            cat.name_uz = name_uz
            cat.icon_class = icon
            cat.parent = parent
            cat.save()
        return cat

    def _unique_slug(self, base):
        slug = base
        n = 2
        while Category.objects.filter(slug=slug).exists():
            slug = f"{base}-{n}"
            n += 1
        return slug

    def _create_salon(self, *, fake, owner, category, venue):
        district = random.choice(TASHKENT_DISTRICTS)

        # Branded venue name per category
        brand_pool = {
            "paddle-tennis":  ["Padel Arena", "Smash Club", "Ace Padel", "Set Point"],
            "big-tennis":     ["Grand Tennis", "Match Point", "Royal Tennis", "Ace Court"],
            "computer-cafe":  ["CyberZone", "GameHub", "PixelPlay", "NeoGaming", "LanArena"],
            "billiard":       ["Pyramid Hall", "Pool Kings", "Classic Billiard", "VIP Cue"],
            "restaurant":     ["Besh Qozon", "Каштан", "Sofra", "Old Tashkent", "Saryk"],
        }
        brand = random.choice(brand_pool.get(venue["slug"], ["Club"]))
        salon_name = f"{brand} {district}"

        salon = Salon.objects.create(
            name=salon_name,
            owner=owner,
            category=category,
            description_ru=f"{brand} в районе {district}. Добро пожаловать!",
            description_en=f"{brand} in {district} district. Welcome!",
            description_uz=f"{district} tumanidagi {brand}. Xush kelibsiz!",
            address=f"{district}, {fake.street_address()}",
            phone=f"+998{random.randint(70,99)}{random.randint(1000000,9999999)}",
        )

        # Optional address coords (fake Tashkent-ish)
        Address.objects.create(
            salon=salon,
            full_address=salon.address,
            latitude=Decimal(f"{41.2 + random.uniform(-0.1, 0.15):.6f}"),
            longitude=Decimal(f"{69.2 + random.uniform(-0.1, 0.15):.6f}"),
        )
        return salon

    def _create_resources(self, salon, venue):
        """Create 'Master' rows representing courts / PCs / tables."""
        prefix_ru, prefix_en, prefix_uz = venue["resource_prefix"]
        created = 0
        for i in range(1, venue["resource_count"] + 1):
            name = f"{prefix_ru} {i}"
            # For restaurant tables: include capacity in name
            if venue["slug"] == "restaurant":
                capacity = random.choice([2, 4, 4, 6])
                name = f"{prefix_ru} {i} ({capacity} чел.)"

            Master.objects.create(
                salon=salon,
                name=name,
                specialization_ru=venue["name_ru"],
                specialization_en=venue["name_en"],
                specialization_uz=venue["name_uz"],
                is_active=True,
            )
            created += 1
        return created

    def _create_services(self, salon, venue):
        created = 0
        for name_ru, name_en, name_uz, duration, price in venue["services"]:
            Service.objects.create(
                salon=salon,
                name_ru=name_ru,
                name_en=name_en,
                name_uz=name_uz,
                description_ru="",
                description_en="",
                description_uz="",
                price=Decimal(price),
                duration_minutes=duration,
            )
            created += 1
        return created

    def _create_working_hours(self, salon, venue):
        open_t = venue["open"]
        close_t = venue["close"]

        # Your SalonWorkingHours.clean() requires open < close (same day).
        # Clamp close to 23:59 if it goes past midnight (billiard case).
        if close_t <= open_t:
            close_t = time(23, 59)

        for weekday in range(7):  # 0=Mon .. 6=Sun
            SalonWorkingHours.objects.update_or_create(
                salon=salon,
                weekday=weekday,
                defaults={
                    "is_closed": False,
                    "open_time": open_t,
                    "close_time": close_t,
                },
            )
          
# python manage.py seed_venues                    # 2 salons per subcategory (default)
# python manage.py seed_venues --salons-per-sub 3 # more demo data
# python manage.py seed_venues --reset            # wipe these 5 venue categories first, then reseed

