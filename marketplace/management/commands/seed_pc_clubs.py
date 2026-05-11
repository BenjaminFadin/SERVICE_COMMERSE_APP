import random
from datetime import time
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

# Replace 'bookings' with your actual app name where these models live
from marketplace.models import (
    Category, Salon, PCPlan, Master, 
    SalonWorkingHours, Address
)

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds the database with professional PC Club data using existing user 'a'"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Starting Seeding Process ---"))

        try:
            # 1. Fetch the specific user 'a'
            try:
                owner = User.objects.get(username='a')
                self.stdout.write(f"Using existing user: {owner.username}")
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR("Error: User with username 'a' was not found. Please create this user first."))
                return

            with transaction.atomic():
                pc_cat = self._create_category()
                self._create_clubs(pc_cat, owner)
                
            self.stdout.write(self.style.SUCCESS("Successfully seeded all PC Club data!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Seeding failed: {e}"))

    def _create_category(self):
        cat, created = Category.objects.get_or_create(
            slug="computer-cafe",
            defaults={
                "name_ru": "Компьютерные клубы",
                "name_en": "PC Clubs",
                "name_uz": "Kompyuter klublari",
                "icon_class": "bi bi-pc-display"
            }
        )
        return cat

    def _create_clubs(self, category, owner):
        clubs_data = [
            {
                "name": "Cyberia Pro Gaming",
                "address": "Tashkent, Yunusabad, 4th Block",
                "plans": [
                    {"name": "Standard", "price": 12000, "color": "#00A3AD", "icon": "bi-pc-display"},
                    {"name": "VIP Room", "price": 25000, "color": "#FFD700", "icon": "bi-gem"},
                    {"name": "Night Marathon", "price": 50000, "color": "#6A5ACD", "icon": "bi-moon-stars"},
                ]
            },
            {
                "name": "Respawn Arena",
                "address": "Tashkent, Chilanzar, 9th Block",
                "plans": [
                    {"name": "Economy", "price": 10000, "color": "#28A745", "icon": "bi-cpu"},
                    {"name": "Bootcamp Pro", "price": 35000, "color": "#DC3545", "icon": "bi-trophy"},
                ]
            }
        ]

        for club in clubs_data:
            # Create Salon with user 'a' as owner
            salon, created = Salon.objects.get_or_create(
                name=club["name"],
                defaults={
                    "owner": owner,
                    "category": category,
                    "description_ru": f"Премиальный клуб {club['name']} с мощным железом.",
                    "address": club["address"],
                    "phone": "+998901234567"
                }
            )

            if not created:
                self.stdout.write(f"  - Salon {salon.name} already exists, skipping.")
                continue

            # Create Address
            Address.objects.create(
                salon=salon,
                full_address=club["address"],
                latitude=41.3111,
                longitude=69.2406,
                map_link="https://yandex.com/maps/"
            )

            # Create 24/7 Working Hours
            for day in range(7):
                SalonWorkingHours.objects.create(
                    salon=salon,
                    weekday=day,
                    open_time=time(0, 0),
                    close_time=time(23, 59),
                    is_closed=False
                )

            # Create PC Plans
            for i, p in enumerate(club["plans"]):
                PCPlan.objects.create(
                    salon=salon,
                    name_ru=p["name"],
                    price_per_hour=p["price"],
                    color=p["color"],
                    icon_class=p["icon"],
                    sort_order=i,
                    is_active=True
                )

            # Create default Master
            Master.objects.create(
                salon=salon,
                name="Manager on Duty",
                specialization_ru="Администратор зала",
                is_active=True
            )
            
            self.stdout.write(f"  - Seeded club: {salon.name}")