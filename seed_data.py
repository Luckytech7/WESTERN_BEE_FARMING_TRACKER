"""
seed_data.py — Western Uganda apiculture mock data
Run: python seed_data.py
"""
import os, sys, django, random
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tracker.models import Beekeeper, Farm, Hive, Season, Harvest
from django.contrib.auth.hashers import make_password

random.seed(42)

print("Clearing existing data...")
Harvest.objects.all().delete()
Hive.objects.all().delete()
Farm.objects.all().delete()
Beekeeper.objects.all().delete()
Season.objects.all().delete()

# ── Seasons per year ───────────────────────────────────────────────────────
# Western Uganda has 4 seasons:
#   Long Rains:  Mar–May   (main honey flow — high yields)
#   Long Dry:    Jun–Aug   (moderate, some forage)
#   Short Rains: Sep–Nov   (second honey flow)
#   Short Dry:   Dec–Feb   (low forage, minimal yields)

print("Seeding seasons...")
season_defs = [
    ('Long Rains',   3, 5),
    ('Long Dry',     6, 8),
    ('Short Rains',  9, 11),
    ('Short Dry',   12, 2),
]
seasons = {}
for year in [2024, 2025, 2026]:
    for name, start, end in season_defs:
        s = Season.objects.create(name=name, year=year, start_month=start, end_month=end)
        seasons[(name, year)] = s
        print(f"  {name} {year} (months {start}–{end})")

# ── Beekeepers ─────────────────────────────────────────────────────────────
print("\nSeeding beekeepers...")
beekeepers_data = [
    ('Asiimwe Robert',    'asiimwe@rwenzoriapiary.ug',  'Pass1234!', 'admin'),
    ('Birungi Immaculate','birungi@kasesehives.ug',     'Honey#99',  'beekeeper'),
    ('Tumwebaze Gerald',  'tumwebaze@fortportalbees.ug','Miel@2024', 'beekeeper'),
    ('Nakamya Prossy',    'nakamya@kibaleforest.ug',    'Bees@2025', 'beekeeper'),
    ('Byaruhanga Moses',  'byaruhanga@mbararahive.ug',  'Hive#2024', 'farm_user'),
    ('Atuhaire Grace',    'atuhaire@busongora.ug',      'Farm@2025', 'farm_user'),
]
beekeepers = []
for name, email, pw, role in beekeepers_data:
    bk = Beekeeper.objects.create(
        name=name, email=email,
        password_hash=make_password(pw),
        role=role
    )
    beekeepers.append(bk)
    print(f"  {name} [{role}]")

# ── Farms — Western Uganda locations ──────────────────────────────────────
print("\nSeeding farms...")
farms_data = [
    # (beekeeper_idx, name, location, established)
    (0, 'Rwenzori Highland Apiary',  'Kasese, Rwenzori Mountains',     date(2018, 3, 10)),
    (0, 'Bukonzo Valley Hives',      'Bukonzo, Kasese District',       date(2020, 6, 1)),
    (1, 'Fort Portal Forest Apiary', 'Fort Portal, Tooro Kingdom',     date(2019, 1, 15)),
    (1, 'Kibale Canopy Hives',       'Kibale Forest, Kamwenge',        date(2021, 4, 20)),
    (2, 'Hoima Savannah Apiary',     'Hoima, Bunyoro Kingdom',         date(2017, 9, 5)),
    (2, 'Masindi Bush Farm',         'Masindi, Bunyoro',               date(2022, 2, 28)),
    (3, 'Kabale Highlands Hives',    'Kabale, Kigezi Highlands',       date(2019, 7, 12)),
    (3, 'Kisoro Gorilla Apiary',     'Kisoro, Virunga Foothills',      date(2023, 1, 5)),
]
farms = []
for bk_idx, name, location, est in farms_data:
    f = Farm.objects.create(
        name=name, location=location,
        established_date=est,
        beekeeper=beekeepers[bk_idx]
    )
    farms.append(f)
    print(f"  {name}")

# ── Hives (5–8 per farm, Uganda-relevant types) ────────────────────────────
print("\nSeeding hives...")
hive_types   = ['langstroth', 'langstroth', 'top_bar', 'top_bar', 'log_hive', 'kenya_top']
queen_states = ['mated', 'mated', 'mated', 'new', 'replaced']
statuses     = ['active'] * 7 + ['inactive']

all_hives = []
for farm in farms:
    prefix = ''.join(w[0] for w in farm.name.split()[:2]).upper()
    for i in range(1, random.randint(5, 9)):
        hive = Hive.objects.create(
            hive_number  = f"{prefix}-{i:02d}",
            hive_type    = random.choice(hive_types),
            install_date = farm.established_date + timedelta(days=random.randint(0, 60)),
            queen_status = random.choice(queen_states),
            status       = random.choice(statuses),
            farm         = farm,
        )
        all_hives.append(hive)
print(f"  Created {len(all_hives)} hives across {len(farms)} farms")

# ── Harvests (2024–2025, season-realistic yields) ──────────────────────────
print("\nSeeding harvests...")
active_hives = [h for h in all_hives if h.status == 'active']

# Yield ranges per Uganda season
YIELD_RANGES = {
    'Long Rains':  (18, 35),   # Best season — dense floral bloom
    'Long Dry':    (10, 22),   # Moderate
    'Short Rains': (14, 28),   # Good second flow
    'Short Dry':   (4,  12),   # Lean season
}

harvest_count = 0
for year in [2024, 2025]:
    for season_name, start_m, end_m in season_defs:
        lo, hi = YIELD_RANGES[season_name]
        # Generate harvest dates spread through the season months
        months = []
        m = start_m
        while True:
            months.append(m)
            if m == end_m:
                break
            m = m % 12 + 1

        for _ in range(random.randint(14, 22)):
            month = random.choice(months)
            h_year = year
            if season_name == 'Short Dry' and month in (1, 2):
                h_year = year + 1
            if h_year > 2025:
                continue
            h_date = date(h_year, month, random.randint(1, 28))
            hive   = random.choice(active_hives)
            Harvest.objects.create(
                harvest_date = h_date,
                yield_kg     = round(random.uniform(lo, hi), 2),
                notes        = random.choice([
                    '', '', '',
                    'Strong colony, full frames.',
                    'Good nectar flow from Eucalyptus.',
                    'Queen active, brood pattern excellent.',
                    'Harvested early morning.',
                    'Moisture content checked before storage.',
                    'Bees very calm during harvest.',
                ]),
                hive = hive,
                # season auto-assigned in Harvest.save()
            )
            harvest_count += 1

from django.db.models import Sum
total = Harvest.objects.aggregate(t=Sum('yield_kg'))['t'] or 0
print(f"  Created {harvest_count} harvests")

print("\n=== SEED COMPLETE ===")
print(f"  Beekeepers : {Beekeeper.objects.count()}")
print(f"  Farms      : {Farm.objects.count()}")
print(f"  Hives      : {Hive.objects.count()} ({Hive.objects.filter(status='active').count()} active)")
print(f"  Seasons    : {Season.objects.count()} (across {Season.objects.values('year').distinct().count()} years)")
print(f"  Harvests   : {Harvest.objects.count()}")
print(f"  Total yield: {round(total, 2)} kg")
print()
print("Demo logins:")
for bk in Beekeeper.objects.all():
    print(f"  {bk.email:40s} [{bk.role}]")
