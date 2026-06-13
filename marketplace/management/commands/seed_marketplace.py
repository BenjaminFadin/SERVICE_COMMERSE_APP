"""
Unified marketplace seeder.

Replaces the previous separate commands.
Seeds the database with:
  - Salon categories (beauty, tennis, billiard, restaurants, PC clubs)
  - Salons with auto-generated QR tokens
  - Services + Masters + Working Hours
  - Sample appointments

Run with:
    python manage.py seed_marketplace
    python manage.py seed_marketplace --salons-per-sub 3
    python manage.py seed_marketplace --reset    # wipe everything first
"""

import random
import secrets
from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from faker import Faker

from marketplace.models import (
    Category, Salon, SalonPhoto, Service, Master, SalonWorkingHours,
    Address, Appointment,
)
from pc_clubs.models import PCClub, PCPhoto, PCPlan, PCAddress, PCWorkingHours


# ---------------------------------------------------------------------------
# VENUE DEFINITIONS
# ---------------------------------------------------------------------------

BEAUTY_HIERARCHY = [
    # (parent_name_ru, slug, icon, [subcategory names])
    ("Парикмахерские",  "parikmaherskie",  "bi bi-scissors",     ["Женская стрижка", "Окрашивание", "Укладка"]),
    ("Барбершопы",      "barbershopy",     "bi bi-person-badge", ["Мужская стрижка", "Стрижка бороды", "Бритье", "Детская стрижка"]),
    ("Ногтевой сервис", "nogtevoj-servis", "bi bi-palette",      ["Маникюр", "Педикюр", "Наращивание"]),
    ("Уход за кожей",   "uhod-za-kozhej",  "bi bi-magic",        ["Чистка лица", "Пилинг", "Маски"]),
    ("Брови и Ресницы", "brovi-i-resnicy", "bi bi-eye",          ["Коррекция бровей", "Ламинирование ресниц"]),
    ("Массаж",          "massazh",         "bi bi-heart-pulse",  ["Классический", "Тайский", "Спортивный"]),
    ("Макияж",          "makiyazh",        "bi bi-brush",        ["Вечерний макияж", "Свадебный макияж"]),
    ("Тату и Пирсинг",  "tatu-i-pirsing",  "bi bi-stars",        ["Татуировка", "Пирсинг"]),
]

VENUES = [
    # ------------------------------------------------------------------
    #  PADDLE TENNIS
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
            ("Аренда 1 час",          "1-hour rental",       "1 soatlik ijara",       60,  80_000),
            ("Аренда 2 часа",         "2-hour rental",       "2 soatlik ijara",      120, 150_000),
            ("Корт + тренер (1 час)", "Court + coach (1h)",  "Maydon + trener (1s)",  60, 150_000),
        ],
        "open":  time(8, 0),
        "close": time(23, 0),
        "brand_pool": ["Padel Arena", "Smash Club", "Ace Padel", "Set Point"],
    },

    # ------------------------------------------------------------------
    #  BIG TENNIS
    # ------------------------------------------------------------------
    {
        "slug": "big-tennis",
        "name_ru": "Большой теннис",
        "name_en": "Big Tennis",
        "name_uz": "Katta tennis",
        "icon": "bi bi-dribbble",
        "sub": [
            ("Хард корты",      "Hard Courts",     "Qattiq maydonlar"),
            ("Грунтовые корты", "Clay Courts",     "Tuproq maydonlar"),
            ("Крытые корты",    "Indoor Courts",   "Yopiq maydonlar"),
            ("Тренировки",      "Lessons",         "Mashg'ulotlar"),
        ],
        "resource_prefix": ("Корт", "Court", "Maydon"),
        "resource_count": 3,
        "services": [
            ("Аренда корта 1 час",  "1-hour court rental", "Maydon ijarasi 1 soat",  60, 100_000),
            ("Аренда корта 2 часа", "2-hour court rental", "Maydon ijarasi 2 soat", 120, 180_000),
            ("Индивидуальный урок", "Private lesson",      "Shaxsiy dars",           60, 200_000),
        ],
        "open":  time(7, 0),
        "close": time(23, 0),
        "brand_pool": ["Grand Tennis", "Match Point", "Royal Tennis", "Ace Court"],
    },

    # ------------------------------------------------------------------
    #  BILLIARD
    # ------------------------------------------------------------------
    {
        "slug": "billiard",
        "name_ru": "Бильярд",
        "name_en": "Billiard",
        "name_uz": "Bilyard",
        "icon": "bi bi-bullseye",
        "sub": [
            ("Русская пирамида", "Russian Pyramid", "Rus piramidasi"),
            ("Американский пул", "American Pool",   "Amerikan pul"),
            ("Снукер",           "Snooker",         "Snuker"),
        ],
        "resource_prefix": ("Стол", "Table", "Stol"),
        "resource_count": 6,
        "services": [
            ("1 час",            "1 hour",        "1 soat",         60,  40_000),
            ("2 часа",           "2 hours",       "2 soat",        120,  75_000),
            ("VIP-зал (3 часа)", "VIP room (3h)", "VIP-xona (3s)", 180, 180_000),
        ],
        "open":  time(12, 0),
        "close": time(2, 0),
        "brand_pool": ["Pyramid Hall", "Pool Kings", "Classic Billiard", "VIP Cue"],
    },

    # ------------------------------------------------------------------
    #  RESTAURANT
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
        "services": [
            ("Бронь на 2 персон", "Reservation for 2", "2 kishilik bron", 30, 0),
            ("Бронь на 4 персон", "Reservation for 4", "4 kishilik bron", 30, 0),
            ("Бронь на 6 персон", "Reservation for 6", "6 kishilik bron", 30, 0),
        ],
        "open":  time(10, 0),
        "close": time(23, 0),
        "brand_pool": ["Besh Qozon", "Каштан", "Sofra", "Old Tashkent", "Saryk"],
    },
]


TASHKENT_DISTRICTS = [
    "Mirzo Ulug'bek", "Chilonzor", "Yunusobod", "Shayxontohur",
    "Yashnobod", "Yakkasaroy", "Olmazor", "Mirobod", "Sergeli", "Bektemir",
]


# ---------------------------------------------------------------------------
# PC CLUB DEFINITIONS  (seeded into the pc_clubs app, not as Salon objects)
# ---------------------------------------------------------------------------

PC_CLUBS_DATA = [
    {
        "name": "Cyberia Pro Gaming",
        "district": "Yunusobod",
        "total_pcs": 30,
        "plans": [
            {"name": "Standard",     "price": 10_000, "color": "#00A3AD", "icon": "bi bi-pc-display",          "sort": 0},
            {"name": "VIP",          "price": 20_000, "color": "#6f42c1", "icon": "bi bi-stars",               "sort": 1},
            {"name": "Stream Room",  "price": 35_000, "color": "#e63946", "icon": "bi bi-broadcast",           "sort": 2},
        ],
    },
    {
        "name": "NeoArena",
        "district": "Chilonzor",
        "total_pcs": 25,
        "plans": [
            {"name": "Economy",   "price":  8_000, "color": "#198754", "icon": "bi bi-pc-display-horizontal", "sort": 0},
            {"name": "Bootcamp",  "price": 15_000, "color": "#fd7e14", "icon": "bi bi-controller",            "sort": 1},
            {"name": "Pro Zone",  "price": 25_000, "color": "#0d6efd", "icon": "bi bi-trophy",               "sort": 2},
        ],
    },
    {
        "name": "LanArena",
        "district": "Mirzo Ulug'bek",
        "total_pcs": 20,
        "plans": [
            {"name": "Standard", "price": 12_000, "color": "#00A3AD", "icon": "bi bi-pc-display",   "sort": 0},
            {"name": "VIP",      "price": 22_000, "color": "#9c27b0", "icon": "bi bi-gem",           "sort": 1},
            {"name": "PS5 Zone", "price": 40_000, "color": "#e91e63", "icon": "bi bi-joystick",      "sort": 2},
        ],
    },
    {
        "name": "PixelPlay Shayxontohur",
        "district": "Shayxontohur",
        "total_pcs": 15,
        "plans": [
            {"name": "Обычные ПК", "price":  8_000, "color": "#607d8b", "icon": "bi bi-pc-display-horizontal", "sort": 0},
            {"name": "Gaming ПК",  "price": 15_000, "color": "#00A3AD", "icon": "bi bi-pc-display",             "sort": 1},
            {"name": "VIP Кабина", "price": 30_000, "color": "#ff5722", "icon": "bi bi-door-closed",            "sort": 2},
        ],
    },
    {
        "name": "GameHub Pro",
        "district": "Yashnobod",
        "total_pcs": 18,
        "plans": [
            {"name": "Standard",  "price": 10_000, "color": "#2196f3", "icon": "bi bi-pc-display",   "sort": 0},
            {"name": "VIP",       "price": 18_000, "color": "#ff9800", "icon": "bi bi-stars",         "sort": 1},
            {"name": "Night Pack","price": 50_000, "color": "#212121", "icon": "bi bi-moon-stars",    "sort": 2},
        ],
    },
]


def generate_qr_token() -> str:
    """Generate a URL-safe random token for QR codes."""
    return secrets.token_urlsafe(16).replace("-", "").replace("_", "")[:24]


# ---------------------------------------------------------------------------
# COMMAND
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Seed marketplace with categories: beauty, tennis, billiard, restaurants, PC clubs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--salons-per-sub",
            type=int,
            default=2,
            help="Number of demo salons per subcategory (default: 2).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Wipe ALL existing categories, salons, services, appointments before seeding.",
        )
        parser.add_argument(
            "--skip-beauty",
            action="store_true",
            help="Skip beauty categories (parikmaherskie, barbershopy, etc).",
        )
        parser.add_argument(
            "--skip-venues",
            action="store_true",
            help="Skip venues (tennis, billiard, PC club, restaurants).",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        fake = Faker("ru_RU")
        User = get_user_model()
        salons_per_sub = opts["salons_per_sub"]

        # ------- 1. OPTIONAL RESET -------
        if opts["reset"]:
            self.stdout.write("--reset: wiping all data...")
            Appointment.objects.all().delete()
            Service.objects.all().delete()
            Master.objects.all().delete()
            SalonWorkingHours.objects.all().delete()
            SalonPhoto.objects.all().delete()
            Address.objects.all().delete()
            Salon.objects.all().delete()
            Category.objects.all().delete()
            from pc_clubs.models import PCBooking as _PCBooking, PCWorkingHours as _PCWh, PCAddress as _PCAdr
            _PCBooking.objects.all().delete()
            PCPhoto.objects.all().delete()
            PCPlan.objects.all().delete()
            _PCWh.objects.all().delete()
            _PCAdr.objects.all().delete()
            PCClub.objects.all().delete()
            self.stdout.write("Wipe complete.")

        # ------- 2. OWNERS + CLIENTS -------
        self.stdout.write("Setting up users...")
        owner = User.objects.filter(is_staff=True).first() or User.objects.create_user(
            username="admin",
            password="password123",
            is_staff=True,
            is_superuser=True,
        )

        demo_owner, _ = User.objects.get_or_create(
            username="demo_venue_owner",
            defaults={"email": "demo_owner@example.com"},
        )

        clients = list(User.objects.filter(is_staff=False)[:20])
        if len(clients) < 10:
            for i in range(10):
                u, _ = User.objects.get_or_create(
                    username=f"user_{i}",
                    defaults={"email": f"user_{i}@example.com"},
                )
                if u not in clients:
                    clients.append(u)

        # ------- 3. SEED BEAUTY HIERARCHY -------
        if not opts["skip_beauty"]:
            self.stdout.write(self.style.SUCCESS("\n=== Seeding BEAUTY categories ==="))
            self._seed_beauty(fake, owner, clients, salons_per_sub)

        # ------- 4. SEED VENUES (tennis, billiard, restaurants) -------
        if not opts["skip_venues"]:
            self.stdout.write(self.style.SUCCESS("\n=== Seeding VENUE categories ==="))
            self._seed_venues(fake, demo_owner, salons_per_sub)

        # ------- 5. SEED PC CLUBS (separate app, always runs unless --skip-venues) -------
        if not opts["skip_venues"]:
            self.stdout.write("=== Seeding PC CLUBS ===")
            self._seed_pc_clubs(fake, demo_owner)

        self.stdout.write(self.style.SUCCESS("\nDatabase seeded successfully!"))

    # =====================================================================
    # BEAUTY SEEDING
    # =====================================================================

    def _seed_beauty(self, fake, owner, clients, salons_per_sub):
        leaf_categories = []
        for p_name, p_slug, p_icon, subs in BEAUTY_HIERARCHY:
            parent, _ = Category.objects.get_or_create(
                slug=p_slug,
                defaults={
                    "name_ru": p_name,
                    "icon_class": p_icon,
                    "is_pc_club": False,
                },
            )
            self.stdout.write(self.style.SUCCESS(f" {parent.name_ru}"))

            for s_name in subs:
                child_slug = self._unique_slug(slugify(f"{p_slug}-{s_name}", allow_unicode=False) or f"{p_slug}-sub")
                child, _ = Category.objects.get_or_create(
                    slug=child_slug,
                    defaults={
                        "name_ru": s_name,
                        "icon_class": p_icon,
                        "parent": parent,
                        "is_pc_club": False,
                    },
                )
                leaf_categories.append(child)
                self.stdout.write(f"    {child.name_ru}")

        # Create salons for subcategories
        for cat in leaf_categories:
            for _ in range(salons_per_sub):
                salon_name = f"{fake.company()} ({cat.name_ru})"
                h = abs(hash(salon_name))
                salon = Salon.objects.create(
                    owner=owner,
                    category=cat,
                    name=salon_name,
                    address=fake.address(),
                    phone=self._random_phone(fake),
                    qr_token=generate_qr_token(),
                    logo_url=f"https://picsum.photos/seed/{h % 500}/200/200",
                    cover_url=f"https://picsum.photos/seed/{(h + 500) % 1000}/1200/450",
                )
                self._seed_salon_photos(salon_name, salon)

                for day in range(7):
                    SalonWorkingHours.objects.create(
                        salon=salon, weekday=day,
                        open_time=time(9, 0), close_time=time(21, 0),
                        is_closed=False,
                    )

                masters = [
                    Master.objects.create(
                        salon=salon,
                        name=fake.name(),
                        specialization_ru=cat.parent.name_ru if cat.parent else cat.name_ru,
                    )
                    for _ in range(2)
                ]

                services = []
                for tier in ["Стандарт", "Премиум", "VIP"]:
                    s = Service.objects.create(
                        salon=salon,
                        name_ru=f"{cat.name_ru} {tier}",
                        price=random.choice([50_000, 150_000, 300_000]),
                        duration_minutes=random.choice([30, 60, 90]),
                    )
                    services.append(s)

                self._quick_appointments(clients, salon, masters, services)

    # =====================================================================
    # VENUE SEEDING
    # =====================================================================

    def _seed_venues(self, fake, demo_owner, salons_per_sub):
        for venue in VENUES:
            parent = self._ensure_category(
                name_ru=venue["name_ru"],
                name_en=venue["name_en"],
                name_uz=venue["name_uz"],
                slug=venue["slug"],
                icon=venue["icon"],
                parent=None,
                is_pc_club=False, # Now False for PC Club
            )
            self.stdout.write(self.style.SUCCESS(
                f" Parent: {parent.name_ru} ({parent.slug})"
            ))

            for sub_ru, sub_en, sub_uz in venue["sub"]:
                sub = self._ensure_category(
                    name_ru=sub_ru,
                    name_en=sub_en,
                    name_uz=sub_uz,
                    slug=self._unique_slug(f"{venue['slug']}-{slugify(sub_en)}"),
                    icon=venue["icon"],
                    parent=parent,
                    is_pc_club=False, # Now False for PC Club
                )
                self.stdout.write(f"    {sub.name_ru}")

                for _ in range(salons_per_sub):
                    salon = self._create_salon(
                        fake=fake,
                        owner=demo_owner,
                        category=sub,
                        venue=venue,
                    )

                    self._create_resources(salon, venue)
                    self._create_working_hours(salon, venue)
                    # All venues now use Services
                    self._create_services(salon, venue)

    # =====================================================================
    # PC CLUBS SEEDING
    # =====================================================================

    def _seed_pc_clubs(self, fake, owner):
        # Ensure parent PC club category
        parent_cat, _ = Category.objects.get_or_create(
            slug="computer-cafe",
            defaults={
                "name_ru": "Компьютерный клуб",
                "name_en": "Computer Cafe",
                "name_uz": "Kompyuter klubi",
                "icon_class": "bi bi-pc-display",
                "is_pc_club": True,
            },
        )
        parent_cat.is_pc_club = True
        parent_cat.save(update_fields=["is_pc_club"])

        for data in PC_CLUBS_DATA:
            district = data["district"]
            club_name = data["name"]

            if PCClub.objects.filter(name=club_name).exists():
                self.stdout.write(f"    {club_name} already exists, skipping.")
                continue

            h = abs(hash(club_name))
            club = PCClub.objects.create(
                name=club_name,
                owner=owner,
                category=parent_cat,
                description_ru=f"{club_name} — лучший игровой клуб в районе {district}. Высокоскоростные ПК, комфортные кресла, 24/7.",
                description_en=f"{club_name} — top gaming club in {district}. High-speed PCs, comfortable chairs, 24/7.",
                description_uz=f"{club_name} — {district} tumanidagi eng yaxshi o'yin klubi. Tezkor kompyuterlar, qulay kreslolar, 24/7.",
                address=f"{district}, {fake.street_address()}",
                phone=f"+998{random.randint(70, 99)}{random.randint(1000000, 9999999)}",
                total_pcs=data["total_pcs"],
                logo_url=f"https://picsum.photos/seed/{h % 500}/200/200",
                cover_url=f"https://picsum.photos/seed/{(h + 500) % 1000}/1200/450",
            )
            for i in range(4):
                PCPhoto.objects.create(
                    pc_club=club,
                    photo_url=f"https://picsum.photos/seed/{(h + 100 + i * 100) % 1000}/800/600",
                    is_main=(i == 0),
                )

            PCAddress.objects.create(
                pc_club=club,
                full_address=club.address,
                latitude=Decimal(f"{41.2 + random.uniform(-0.1, 0.15):.6f}"),
                longitude=Decimal(f"{69.2 + random.uniform(-0.1, 0.15):.6f}"),
            )

            for day in range(7):
                PCWorkingHours.objects.create(
                    pc_club=club,
                    weekday=day,
                    is_closed=False,
                    open_time=time(0, 0),
                    close_time=time(23, 59),
                )

            for p in data["plans"]:
                PCPlan.objects.create(
                    pc_club=club,
                    name=p["name"],
                    price_per_hour=Decimal(p["price"]),
                    color=p["color"],
                    icon_class=p["icon"],
                    sort_order=p["sort"],
                    is_active=True,
                )

            self.stdout.write(self.style.SUCCESS(
                f"    {club_name} ({data['total_pcs']} PCs, {len(data['plans'])} plans)"
            ))

    # =====================================================================
    # HELPERS
    # =====================================================================

    def _ensure_category(self, *, name_ru, name_en, name_uz, slug, icon, parent, is_pc_club=False):
        cat, created = Category.objects.get_or_create(
            slug=slug,
            defaults={
                "name_ru": name_ru,
                "name_en": name_en,
                "name_uz": name_uz,
                "icon_class": icon,
                "parent": parent,
                "is_pc_club": is_pc_club,
            },
        )
        if not created:
            cat.name_ru = name_ru
            cat.name_en = name_en
            cat.name_uz = name_uz
            cat.icon_class = icon
            cat.parent = parent
            cat.is_pc_club = is_pc_club
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
        brand = random.choice(venue.get("brand_pool", ["Club"]))
        salon_name = f"{brand} {district}"

        h = abs(hash(salon_name))
        salon = Salon.objects.create(
            name=salon_name,
            owner=owner,
            category=category,
            description_ru=f"{brand} в районе {district}. Добро пожаловать!",
            description_en=f"{brand} in {district} district. Welcome!",
            description_uz=f"{district} tumanidagi {brand}. Xush kelibsiz!",
            address=f"{district}, {fake.street_address()}",
            phone=f"+998{random.randint(70, 99)}{random.randint(1000000, 9999999)}",
            qr_token=generate_qr_token(),
            logo_url=f"https://picsum.photos/seed/{h % 500}/200/200",
            cover_url=f"https://picsum.photos/seed/{(h + 500) % 1000}/1200/450",
        )
        self._seed_salon_photos(salon_name, salon)

        Address.objects.create(
            salon=salon,
            full_address=salon.address,
            latitude=Decimal(f"{41.2 + random.uniform(-0.1, 0.15):.6f}"),
            longitude=Decimal(f"{69.2 + random.uniform(-0.1, 0.15):.6f}"),
        )
        return salon

    def _create_resources(self, salon, venue):
        prefix_ru, prefix_en, prefix_uz = venue["resource_prefix"]
        count = venue["resource_count"]

        for i in range(1, count + 1):
            name = f"{prefix_ru} {i}"
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

    def _create_services(self, salon, venue):
        for name_ru, name_en, name_uz, duration, price in venue["services"]:
            Service.objects.create(
                salon=salon,
                name_ru=name_ru,
                name_en=name_en,
                name_uz=name_uz,
                price=Decimal(price),
                duration_minutes=duration,
            )

    def _create_working_hours(self, salon, venue):
        open_t = venue["open"]
        close_t = venue["close"]

        if close_t <= open_t:
            close_t = time(23, 59)

        for weekday in range(7):
            SalonWorkingHours.objects.update_or_create(
                salon=salon,
                weekday=weekday,
                defaults={
                    "is_closed": False,
                    "open_time": open_t,
                    "close_time": close_t,
                },
            )

    def _seed_salon_photos(self, name, salon):
        h = abs(hash(name))
        for i in range(4):
            SalonPhoto.objects.create(
                salon=salon,
                photo_url=f"https://picsum.photos/seed/{(h + 100 + i * 100) % 1000}/800/600",
                is_main=(i == 0),
            )

    def _random_phone(self, fake):
        p = fake.msisdn()
        return f"+{p[:12]}"

    def _quick_appointments(self, clients, salon, masters, services):
        if not clients or not masters or not services:
            return
        for _ in range(5):
            try:
                Appointment.objects.create(
                    client=random.choice(clients),
                    salon=salon,
                    master=random.choice(masters),
                    service=random.choice(services),
                    start_time=timezone.now() + timedelta(
                        days=random.randint(1, 5),
                        hours=random.randint(1, 8),
                    ),
                    status="confirmed",
                )
            except Exception:
                continue

# =============================================================================
# USAGE
# =============================================================================
# python manage.py seed_marketplace                    # 2 salons per subcategory
# python manage.py seed_marketplace --salons-per-sub 3 # more data
# python manage.py seed_marketplace --reset            # wipe DB first, then seed
# python manage.py seed_marketplace --skip-beauty      # only venues
# python manage.py seed_marketplace --skip-venues      # only beauty

