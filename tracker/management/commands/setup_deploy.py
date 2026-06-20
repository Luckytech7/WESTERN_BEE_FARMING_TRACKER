"""
Management command that runs once at deploy time to:
  1. Create a Django superuser (if none exists)
  2. Seed all application data (idempotent — clears then repopulates)
"""
import os, random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

User = get_user_model()


class Command(BaseCommand):
    help = "Create superuser and seed demo data for deployment"

    def handle(self, *args, **options):
        self._create_superuser()
        self._seed_data()

    # ── Superuser ──────────────────────────────────────────────────────────────
    def _create_superuser(self):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        email    = os.environ.get("DJANGO_SUPERUSER_EMAIL",    "admin@beetracker.ug")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "Admin1234!")

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"  Superuser '{username}' already exists — skipping.")
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(
            f"  Superuser created: {username} / {password}"
        ))

    # ── Seed data ──────────────────────────────────────────────────────────────
    def _seed_data(self):
        from tracker.models import Beekeeper, Farm, Hive, Season, Harvest

        self.stdout.write("Clearing existing data...")
        Harvest.objects.all().delete()
        Hive.objects.all().delete()
        Farm.objects.all().delete()
        Beekeeper.objects.all().delete()
        Season.objects.all().delete()

        random.seed(42)

        # ── Seasons ────────────────────────────────────────────────────────────
        self.stdout.write("Seeding seasons...")
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

        # ── Beekeepers ─────────────────────────────────────────────────────────
        self.stdout.write("Seeding beekeepers...")
        beekeepers_data = [
            ('Asiimwe Robert',     'asiimwe@rwenzoriapiary.ug',   'Pass1234!', 'admin'),
            ('Birungi Immaculate', 'birungi@kasesehives.ug',      'Honey#99',  'beekeeper'),
            ('Tumwebaze Gerald',   'tumwebaze@fortportalbees.ug', 'Miel@2024', 'beekeeper'),
            ('Nakamya Prossy',     'nakamya@kibaleforest.ug',     'Bees@2025', 'beekeeper'),
            ('Byaruhanga Moses',   'byaruhanga@mbararahive.ug',   'Hive#2024', 'farm_user'),
            ('Atuhaire Grace',     'atuhaire@busongora.ug',       'Farm@2025', 'farm_user'),
        ]
        beekeepers = []
        for name, email, pw, role in beekeepers_data:
            bk = Beekeeper.objects.create(
                name=name, email=email,
                password_hash=make_password(pw),
                role=role,
            )
            beekeepers.append(bk)

        # ── Farms ──────────────────────────────────────────────────────────────
        self.stdout.write("Seeding farms...")
        farms_data = [
            (0, 'Rwenzori Highland Apiary',  'Kasese, Rwenzori Mountains',  date(2018, 3, 10)),
            (0, 'Bukonzo Valley Hives',      'Bukonzo, Kasese District',    date(2020, 6, 1)),
            (1, 'Fort Portal Forest Apiary', 'Fort Portal, Tooro Kingdom',  date(2019, 1, 15)),
            (1, 'Kibale Canopy Hives',       'Kibale Forest, Kamwenge',     date(2021, 4, 20)),
            (2, 'Hoima Savannah Apiary',     'Hoima, Bunyoro Kingdom',      date(2017, 9, 5)),
            (2, 'Masindi Bush Farm',         'Masindi, Bunyoro',            date(2022, 2, 28)),
            (3, 'Kabale Highlands Hives',    'Kabale, Kigezi Highlands',    date(2019, 7, 12)),
            (3, 'Kisoro Gorilla Apiary',     'Kisoro, Virunga Foothills',   date(2023, 1, 5)),
        ]
        farms = []
        for bk_idx, name, location, est in farms_data:
            farms.append(Farm.objects.create(
                name=name, location=location,
                established_date=est,
                beekeeper=beekeepers[bk_idx],
            ))

        # ── Hives ──────────────────────────────────────────────────────────────
        self.stdout.write("Seeding hives...")
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

        # ── Harvests ───────────────────────────────────────────────────────────
        self.stdout.write("Seeding harvests...")
        active_hives = [h for h in all_hives if h.status == 'active']
        YIELD_RANGES = {
            'Long Rains':  (18, 35),
            'Long Dry':    (10, 22),
            'Short Rains': (14, 28),
            'Short Dry':   (4,  12),
        }
        harvest_count = 0
        for year in [2024, 2025]:
            for season_name, start_m, end_m in season_defs:
                lo, hi = YIELD_RANGES[season_name]
                months, m = [], start_m
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
                    Harvest.objects.create(
                        harvest_date = date(h_year, month, random.randint(1, 28)),
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
                        hive=random.choice(active_hives),
                    )
                    harvest_count += 1

        from django.db.models import Sum
        total = Harvest.objects.aggregate(t=Sum('yield_kg'))['t'] or 0
        self.stdout.write(self.style.SUCCESS(
            f"\n=== SEED COMPLETE ===\n"
            f"  Beekeepers : {Beekeeper.objects.count()}\n"
            f"  Farms      : {Farm.objects.count()}\n"
            f"  Hives      : {Hive.objects.count()} ({Hive.objects.filter(status='active').count()} active)\n"
            f"  Seasons    : {Season.objects.count()}\n"
            f"  Harvests   : {harvest_count} ({round(total, 2)} kg total)\n"
        ))
