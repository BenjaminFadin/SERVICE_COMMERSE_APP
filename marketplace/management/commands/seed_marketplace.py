import random
from datetime import datetime, timedelta, time

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from faker import Faker

from marketplace.models import (
    Category,
    Salon,
    Service,
    Master,
    Appointment,
    SalonWorkingHours,
)

# DATA STRUCTURE: (Parent Name, Slug, Icon, [List of Subcategories])
HIERARCHY = [
    ("Парикмахерские", "parikmaherskie", "bi bi-scissors", ["Женская стрижка", "Окрашивание", "Укладка"]),
    ("Барбершопы", "barbershopy", "bi bi-person-badge", ["Мужская стрижка", "Стрижка бороды", "Бритье", "Детская стрижка"]),
    ("Ногтевой сервис", "nogtevoj-servis", "bi bi-palette", ["Маникюр", "Педикюр", "Наращивание"]),
    ("Уход за кожей", "uhod-za-kozhej", "bi bi-magic", ["Чистка лица", "Пилинг", "Маски"]),
    ("Брови и Ресницы", "brovi-i-resnicy", "bi bi-eye", ["Коррекция бровей", "Ламинирование ресниц"]),
    ("Массаж", "massazh", "bi bi-heart-pulse", ["Классический", "Тайский", "Спортивный"]),
    ("Макияж", "makiyazh", "bi bi-brush", ["Вечерний макияж", "Свадебный макияж"]),
    ("Тату и Пирсинг", "tatu-i-pirsing", "bi bi-stars", ["Татуировка", "Пирсинг"]),
]

def clamp_close_time(open_t: time, hours_add: int) -> time:
    close_hour = open_t.hour + hours_add
    if close_hour >= 23: close_hour = 22
    return time(close_hour, 0)

def random_phone(fake: Faker) -> str:
    p = fake.msisdn()
    return f"+{p[:12]}"

class Command(BaseCommand):
    help = "Seed marketplace with specific parent and subcategories."

    def add_arguments(self, parser):
        parser.add_argument("--number", type=int, default=3, help="Salons per subcategory.")

    @transaction.atomic
    def handle(self, *args, **options):
        fake = Faker("ru_RU")
        User = get_user_model()
        salons_per_sub = options["number"]

        # 1. Clean and Setup Users
        self.stdout.write("Setting up users...")
        owner = User.objects.filter(is_staff=True).first() or User.objects.create_user(
            username="admin", password="password123", is_staff=True
        )
        clients = list(User.objects.filter(is_staff=False)[:20]) or [
            User.objects.create_user(username=f"user_{i}", password="password123") for i in range(10)
        ]

        # 2. Rebuild Category Tree
        self.stdout.write("Wiping and rebuilding categories...")
        Category.objects.all().delete()
        
        leaf_categories = []
        for p_name, p_slug, p_icon, subs in HIERARCHY:
            parent = Category.objects.create(name_ru=p_name, slug=p_slug, icon_class=p_icon)
            for s_name in subs:
                child = Category.objects.create(
                    name_ru=s_name,
                    slug=f"{p_slug}-{random.randint(100, 999)}", # Ensure unique slugs
                    icon_class=p_icon,
                    parent=parent
                )
                leaf_categories.append(child)

        # 3. Create Salons for Subcategories
        self.stdout.write(self.style.SUCCESS(f"Creating salons for {len(leaf_categories)} subcategories..."))
        
        for cat in leaf_categories:
            for _ in range(salons_per_sub):
                salon = Salon.objects.create(
                    owner=owner,
                    category=cat, # Assigned to Subcategory
                    name=f"{fake.company()} ({cat.name_ru})",
                    address=fake.address(),
                    phone=random_phone(fake),
                )

                # Working Hours
                open_t = time(9, 0)
                close_t = time(21, 0)
                for day in range(7):
                    SalonWorkingHours.objects.create(salon=salon, weekday=day, open_time=open_t, close_time=close_t)

                # Masters
                masters = [Master.objects.create(salon=salon, name=fake.name(), specialization_ru=cat.parent.name_ru) for _ in range(2)]

                # Services strictly based on Subcategory
                services = []
                for tier in ["Стандарт", "Премиум", "VIP"]:
                    s = Service.objects.create(
                        salon=salon,
                        name_ru=f"{cat.name_ru} {tier}",
                        price=random.choice([50000, 150000, 300000]),
                        duration_minutes=random.choice([30, 60, 90]),
                    )
                    services.append(s)

                # Small Batch of Appointments
                self._quick_appointments(clients, salon, masters, services)

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))

    def _quick_appointments(self, clients, salon, masters, services):
        for _ in range(5):
            try:
                Appointment.objects.create(
                    client=random.choice(clients),
                    salon=salon,
                    master=random.choice(masters),
                    service=random.choice(services),
                    start_time=timezone.now() + timedelta(days=random.randint(1, 5), hours=random.randint(1, 8)),
                    status="confirmed"
                )
            except: continue