"""
seed_data.py — Populate the database with realistic mock data.
Run: python manage.py shell < seed_data.py
  OR: python seed_data.py (from project root with manage.py)
"""
import os
import sys
import django
from datetime import date, timedelta
import random

# ── Bootstrap Django ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tracker.models import Beekeeper, Farm, Hive, Season, Harvest
from django.contrib.auth.hashers import make_password

random.seed(42)   # reproducible data

# ── Wipe existing data ────────────────────────────────────────────────────────
print("Clearing existing data...")
Harvest.objects.all().delete()
Hive.objects.all().delete()
Farm.objects.all().delete()
Beekeeper.objects.all().delete()
Season.objects.all().delete()

# ── 1. Seasons ────────────────────────────────────────────────────────────────
print("Seeding seasons...")
seasons_data = [
    ('Spring', 3, 5),
    ('Summer', 6, 8),
    ('Fall',   9, 11),
    ('Winter', 12, 2),   # wraps year boundary
]
seasons = {}
for name, start, end in seasons_data:
    s = Season.objects.create(name=name, start_month=start, end_month=end)
    seasons[name] = s
    print(f"  Season: {name} (months {start}–{end})")

# ── 2. Beekeepers ─────────────────────────────────────────────────────────────
print("Seeding beekeepers...")
beekeepers_data = [
    ('Alice Nakamura', 'alice@beefarmer.com', 'Pass1234!'),
    ('Bernard Ochieng', 'bernard@hiveworks.co', 'Honey#99'),
    ('Clara Wanjiku', 'clara@apiary.ke', 'Clover@22'),
]
beekeepers = []
for name, email, pw in beekeepers_data:
    bk = Beekeeper.objects.create(
        name=name, email=email,
        password_hash=make_password(pw)
    )
    beekeepers.append(bk)
    print(f"  Beekeeper: {name}")

# ── 3. Farms (2 per beekeeper = 6 farms) ──────────────────────────────────────
print("Seeding farms...")
farms_data = [
    # (beekeeper_index, name, location, established_date)
    (0, 'Nakamura Highland Apiary',  'Kinangop, Nyandarua',   date(2019, 3, 15)),
    (0, 'Nakamura Valley Hives',     'Thika, Kiambu',          date(2021, 7, 1)),
    (1, 'Ochieng Lakeside Apiary',   'Kisumu, Western Kenya',  date(2018, 1, 20)),
    (1, 'Ochieng Savannah Farm',     'Nakuru, Rift Valley',    date(2020, 5, 10)),
    (2, 'Wanjiku Forest Hives',      'Nyeri, Mount Kenya',     date(2017, 9, 5)),
    (2, 'Wanjiku Riverside Apiary',  'Meru, Eastern Kenya',    date(2022, 2, 28)),
]
farms = []
for bk_idx, name, location, est_date in farms_data:
    f = Farm.objects.create(
        name=name, location=location,
        established_date=est_date,
        beekeeper=beekeepers[bk_idx]
    )
    farms.append(f)
    print(f"  Farm: {name}")

# ── 4. Hives (5–8 per farm) ───────────────────────────────────────────────────
print("Seeding hives...")
hive_types   = ['langstroth', 'langstroth', 'langstroth', 'top_bar', 'warre', 'flow']
queen_states = ['mated', 'mated', 'mated', 'new', 'replaced']
statuses     = ['active'] * 8 + ['inactive']  # mostly active

all_hives = []
for farm in farms:
    count = random.randint(5, 8)
    for i in range(1, count + 1):
        hive = Hive.objects.create(
            hive_number=f"{farm.name[:3].upper()}-{i:02d}",
            hive_type=random.choice(hive_types),
            install_date=farm.established_date + timedelta(days=random.randint(0, 90)),
            queen_status=random.choice(queen_states),
            status=random.choice(statuses),
            farm=farm,
        )
        all_hives.append(hive)
print(f"  Created {len(all_hives)} hives across {len(farms)} farms")

# ── 5. Harvests (covering 2024 & 2025) ───────────────────────────────────────
print("Seeding harvests...")
honey_types = ['wildflower', 'wildflower', 'clover', 'clover', 'acacia', 'buckwheat', 'other']

# Generate ~30 harvest dates spread across 2024 and 2025
harvest_dates = []
for year in [2024, 2025]:
    # Multiple harvests per season per year
    monthly_distribution = [
        # (month, weight) – higher weight = more harvests that month
        (3, 2), (4, 3), (5, 3),   # Spring – active
        (6, 4), (7, 5), (8, 4),   # Summer – peak
        (9, 3), (10, 3), (11, 2), # Fall – winding down
        (12, 1), (1, 1), (2, 1),  # Winter – minimal
    ]
    for month, weight in monthly_distribution:
        actual_year = year if month != 1 and month != 2 else year + (1 if year == 2024 else 0)
        if actual_year > 2025:
            continue
        for _ in range(weight):
            day = random.randint(1, 28)
            harvest_dates.append(date(actual_year, month, day))

harvest_dates.sort()

harvests_created = 0
active_hives = [h for h in all_hives if h.status == 'active']

for hdate in harvest_dates:
    hive = random.choice(active_hives)
    # Yields vary by season: Summer highest, Winter lowest
    month = hdate.month
    if 6 <= month <= 8:       # Summer
        yield_kg = round(random.uniform(18, 35), 2)
    elif 3 <= month <= 5:     # Spring
        yield_kg = round(random.uniform(12, 25), 2)
    elif 9 <= month <= 11:    # Fall
        yield_kg = round(random.uniform(8, 20), 2)
    else:                      # Winter
        yield_kg = round(random.uniform(3, 10), 2)

    Harvest.objects.create(
        harvest_date=hdate,
        yield_kg=yield_kg,
        honey_type=random.choice(honey_types),
        notes=random.choice([
            '', '', '',   # mostly blank
            'Excellent colour and viscosity.',
            'Light floral aroma.',
            'Dense comb, good yield.',
            'Queen activity high, colony strong.',
            'Some moisture content – stored to dry.',
        ]),
        hive=hive,
        # season is auto-assigned in Harvest.save()
    )
    harvests_created += 1

print(f"  Created {harvests_created} harvest records")

# ── Summary ───────────────────────────────────────────────────────────────────
from django.db.models import Sum
total_kg = Harvest.objects.aggregate(t=Sum('yield_kg'))['t'] or 0
print("\n=== SEED COMPLETE ===")
print(f"  Beekeepers : {Beekeeper.objects.count()}")
print(f"  Farms      : {Farm.objects.count()}")
print(f"  Hives      : {Hive.objects.count()} ({Hive.objects.filter(status='active').count()} active)")
print(f"  Harvests   : {Harvest.objects.count()}")
print(f"  Total yield: {round(total_kg, 2)} kg")
print("\nLogin to admin with: python manage.py createsuperuser")
