import random
from datetime import datetime, timedelta, time

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from django.db import transaction
from django.contrib.auth import get_user_model

from django_seed import Seed
from faker import Faker

from marketplace.models import (
    Category,
    Salon,
    Service,
    Master,
    Appointment,
    SalonWorkingHours,
)

# http://127.0.0.1:8000/api/salon/102/service/928/slots/

CATEGORIES = [
    # (name_ru, slug, icon_class)
    ("Парикмахерские", "parikmaherskie", "bi bi-scissors"),
    ("Барбершопы", "barbershopy", "bi bi-person-badge"),
    ("Ногтевой сервис", "nogtevoj-servis", "bi bi-palette"),
    ("Уход за кожей", "uhod-za-kozhej", "bi bi-magic"),
    ("Брови и Ресницы", "brovi-i-resnicy", "bi bi-eye"),
    ("Массаж", "massazh", "bi bi-heart-pulse"),
    ("Макияж", "makiyazh", "bi bi-brush"),
    ("Тату и Пирсинг", "tatu-i-pirsing", "bi bi-stars"),
]


SERVICE_TEMPLATES = [
    ("Стрижка", "Haircut"),
    ("Окрашивание", "Coloring"),
    ("Укладка", "Styling"),
    ("Маникюр", "Manicure"),
    ("Педикюр", "Pedicure"),
    ("Массаж", "Massage"),
    ("Чистка лица", "Face cleaning"),
    ("Брови", "Brows"),
    ("Ресницы", "Lashes"),
    ("Макияж", "Makeup"),
    ("Тату", "Tattoo"),
    ("Пирсинг", "Piercing"),
]

SPECIALIZATIONS = [
    ("Парикмахер", "Hair stylist"),
    ("Барбер", "Barber"),
    ("Массажист", "Masseur"),
    ("Косметолог", "Cosmetologist"),
    ("Нейл-мастер", "Nail master"),
    ("Визажист", "Makeup artist"),
    ("Мастер тату", "Tattoo artist"),
]


def clamp_close_time(open_t: time, hours_add: int) -> time:
    """
    open 09/10 + 10-12 hours => close 19-22 typically.
    If somehow exceeds 23:59, clamp to 22:00.
    """
    close_hour = open_t.hour + hours_add
    if close_hour >= 23:
        close_hour = 22
    return time(close_hour, 0)


def random_phone(fake: Faker) -> str:
    # Faker phone formats can be messy; keep it short-ish
    p = fake.msisdn()
    return f"+{p[:12]}"


class Command(BaseCommand):
    help = "Seed marketplace: categories + salons + working hours + services + masters + appointments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--number",
            type=int,
            default=10,
            help="How many salons to create PER CATEGORY (use 100 for 100 salons per category).",
        )
        parser.add_argument(
            "--services-min",
            type=int,
            default=6,
            help="Min services per salon.",
        )
        parser.add_argument(
            "--services-max",
            type=int,
            default=12,
            help="Max services per salon.",
        )
        parser.add_argument(
            "--masters-min",
            type=int,
            default=2,
            help="Min masters per salon.",
        )
        parser.add_argument(
            "--masters-max",
            type=int,
            default=4,
            help="Max masters per salon.",
        )
        parser.add_argument(
            "--appointments",
            type=int,
            default=15,
            help="Appointments per salon.",
        )
        parser.add_argument(
            "--clients",
            type=int,
            default=50,
            help="How many fake client users to ensure exist.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        salons_per_category = options["number"]
        services_min = options["services_min"]
        services_max = options["services_max"]
        masters_min = options["masters_min"]
        masters_max = options["masters_max"]
        appts_per_salon = options["appointments"]
        clients_needed = options["clients"]

        fake = Faker("ru_RU")
        seeder = Seed.seeder(locale="ru_RU")

        User = get_user_model()

        # -------------------------
        # 1) Ensure clients exist
        # -------------------------
        existing_clients = User.objects.filter(is_staff=False).count()
        to_create = max(0, clients_needed - existing_clients)

        clients = list(User.objects.filter(is_staff=False)[:clients_needed])
        if to_create > 0:
            self.stdout.write(self.style.WARNING(f"Creating {to_create} fake client users..."))
            for _ in range(to_create):
                username = f"user_{fake.unique.user_name()}"
                email = fake.unique.email()
                # If your custom user requires email, this is OK. Password is simple for dev seed.
                u = User.objects.create_user(username=username, email=email, password="test12345")
                clients.append(u)

        if not clients:
            # fallback: create at least 1 client
            u = User.objects.create_user(username="test_user", email="test_user@example.com", password="test12345")
            clients = [u]

        # -------------------------
        # 2) Ensure an owner exists
        # -------------------------
        owner = User.objects.filter(is_staff=True).first()
        if not owner:
            owner = User.objects.create_user(
                username="business_owner",
                email="owner@example.com",
                password="test12345",
                is_staff=True,
            )

        # -------------------------
        # 3) Create categories
        # -------------------------
        self.stdout.write(self.style.SUCCESS("Ensuring categories..."))

        categories = []
        for name_ru, slug, icon_class in CATEGORIES:
            defaults = {
                "name_ru": name_ru,
                "name_en": "",  # optional
                "name_uz": "",  # optional
            }

            # support both schemas:
            # - old: icon ImageField (ignored here)
            # - new: icon_class CharField
            cat, created = Category.objects.get_or_create(slug=slug, defaults=defaults)
            if not created:
                # Keep existing names if you want; here we update to match seed (safe)
                cat.name_ru = name_ru

            if hasattr(cat, "icon_class"):
                cat.icon_class = icon_class

            cat.save()
            categories.append(cat)

        # -------------------------
        # 4) Create salons + related data
        # -------------------------
        total_salons = 0
        total_services = 0
        total_masters = 0
        total_appts = 0

        self.stdout.write(self.style.SUCCESS("Seeding salons, services, masters, working hours, appointments..."))

        for cat in categories:
            for i in range(salons_per_category):
                # Salon
                salon_name = f"{fake.company()} {random.choice(['Studio', 'Salon', 'Barbershop', 'Beauty'])}"
                salon = Salon.objects.create(
                    owner=owner,
                    category=cat,
                    name_ru=salon_name,
                    name_en=salon_name,
                    name_uz=salon_name,
                    description_ru=fake.text(max_nb_chars=180),
                    description_en=fake.text(max_nb_chars=180),
                    description_uz=fake.text(max_nb_chars=180),
                    address=fake.address(),
                    phone=random_phone(fake),
                )
                total_salons += 1

                # Working hours (Mon-Sun)
                # open 9 or 10, close after 10-12 hours
                open_hour = random.choice([9, 10])
                hours_add = random.choice([10, 11, 12])
                open_t = time(open_hour, 0)
                close_t = clamp_close_time(open_t, hours_add)

                for wd in range(7):
                    SalonWorkingHours.objects.update_or_create(
                        salon=salon,
                        weekday=wd,
                        defaults={
                            "is_closed": False,
                            "open_time": open_t,
                            "close_time": close_t,
                        },
                    )

                # Masters
                master_count = random.randint(masters_min, masters_max)
                masters = []
                for _ in range(master_count):
                    spec_ru, spec_en = random.choice(SPECIALIZATIONS)
                    m = Master.objects.create(
                        salon=salon,
                        user=None,
                        name=fake.name(),
                        specialization_ru=spec_ru,
                        specialization_en=spec_en,
                        specialization_uz=spec_ru,
                        is_active=True,
                    )
                    masters.append(m)
                total_masters += len(masters)

                # Services
                svc_count = random.randint(services_min, services_max)
                services = []
                for _ in range(svc_count):
                    base_ru, base_en = random.choice(SERVICE_TEMPLATES)
                    svc_name = f"{base_ru} {random.choice(['Premium', 'Standard', 'Pro', ''])}".strip()
                    duration = random.choice([30, 45, 60, 75, 90, 120])
                    price = random.choice([50000, 70000, 90000, 120000, 150000, 200000])

                    s = Service.objects.create(
                        salon=salon,
                        name_ru=svc_name,
                        name_en=base_en,
                        name_uz=svc_name,
                        description_ru=fake.sentence(nb_words=8),
                        description_en=fake.sentence(nb_words=8),
                        description_uz=fake.sentence(nb_words=8),
                        price=price,
                        duration_minutes=duration,
                    )
                    services.append(s)
                total_services += len(services)

                # Appointments
                created_here = self._create_appointments(
                    fake=fake,
                    clients=clients,
                    salon=salon,
                    masters=masters,
                    services=services,
                    count=appts_per_salon,
                )
                total_appts += created_here

        self.stdout.write(self.style.SUCCESS("DONE"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Created/ensured categories={len(categories)} | salons={total_salons} | "
                f"masters={total_masters} | services={total_services} | appointments={total_appts}"
            )
        )

    def _create_appointments(self, *, fake, clients, salon, masters, services, count: int) -> int:
        """
        Create non-overlapping appointments inside working hours.
        Uses Appointment.save() validation; retries to avoid collisions.
        """
        if not masters or not services:
            return 0

        tz = timezone.get_current_timezone()
        created = 0

        # Create appointments in next 14 days
        date_start = timezone.localdate()
        date_end = date_start + timedelta(days=14)

        attempts = 0
        max_attempts = count * 50  # plenty to avoid overlaps

        while created < count and attempts < max_attempts:
            attempts += 1

            client = random.choice(clients)
            master = random.choice(masters)
            service = random.choice(services)

            day = date_start + timedelta(days=random.randint(0, (date_end - date_start).days))
            wh = SalonWorkingHours.objects.filter(salon=salon, weekday=day.weekday()).first()
            if not wh or wh.is_closed or not wh.open_time or not wh.close_time:
                continue

            # Build a random start time within working hours, step 15 minutes
            open_dt = timezone.make_aware(datetime.combine(day, wh.open_time), tz)
            close_dt = timezone.make_aware(datetime.combine(day, wh.close_time), tz)

            duration = timedelta(minutes=service.duration_minutes)
            if open_dt + duration >= close_dt:
                continue

            # choose random slot at 15-minute increments
            total_minutes = int((close_dt - open_dt - duration).total_seconds() // 60)
            slot_minutes = random.choice(range(0, max(1, total_minutes), 15))
            start_dt = open_dt + timedelta(minutes=slot_minutes)

            status = random.choice(["pending", "confirmed", "completed"])

            try:
                Appointment.objects.create(
                    client=client,
                    salon=salon,
                    master=master,
                    service=service,
                    start_time=start_dt,
                    status=status,
                    comment=fake.sentence(nb_words=6) if random.random() < 0.35 else "",
                )
                created += 1
            except Exception:
                # overlap / validation / edge cases
                continue

        return created


# python manage.py seed_marketplace --number 100

# Example with fewer services/appointments:
# python manage.py seed_marketplace --number 100 --services-min 15 --services-max 20 --appointments 15

