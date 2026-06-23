# 🍯 Western Bee Farming Tracker

A complete, data-driven MVC web application for tracking apiculture production and mapping seasonal honey yields.

**Stack:** Django 4.x · Django REST Framework · SQLite (PostgreSQL-ready) · Chart.js · Vanilla JS

---

## Database Schema

```
BEEKEEPER (1) ──owns──► (M) FARM (1) ──contains──► (M) HIVE
                                                          │
                                                       produces
                                                          │
SEASON (1) ──categorises──────────────────────────► (M) HARVEST
```

### Indexes (migration 0002_add_db_indexes)

| Index Name | Table | Fields | Purpose |
|---|---|---|---|
| `beekeeper_email_idx` | Beekeeper | email | Login lookup |
| `farm_beekeeper_idx` | Farm | beekeeper_id | RBAC filter |
| `hive_farm_idx` | Hive | farm_id | Farm→hive joins |
| `hive_status_idx` | Hive | status | Active hive filter |
| `hive_farm_status_idx` | Hive | farm_id, status | Composite: most common query |
| `harvest_hive_idx` | Harvest | hive_id | Hive→harvest joins |
| `harvest_season_idx` | Harvest | season_id | Season group-by |
| `harvest_date_idx` | Harvest | harvest_date | Date range filters |
| `harvest_date_season_idx` | Harvest | harvest_date, season | Composite: analytics query |

### N+1 Prevention
Every ViewSet queryset uses `select_related()` to resolve FK chains in a single SQL JOIN:
```python
# HarvestViewSet — resolves hive → farm → beekeeper + season in ONE query
Harvest.objects.select_related('hive', 'hive__farm', 'hive__farm__beekeeper', 'season')
```

---

## Security Architecture

### Role-Based Access Control (RBAC)

| Role | Read | Write | Delete | Data Scope |
|---|---|---|---|---|
| `admin` | ✅ | ✅ | ✅ | All beekeepers |
| `beekeeper` | ✅ | ✅ | ✅ | Own farms/hives/harvests only |
| `viewer` | ✅ | ❌ 403 | ❌ 403 | All (read-only) |

Role assignment:
- Email ending in `@admin.bee` → `admin`
- Any valid beekeeper email → `beekeeper`
- Unauthenticated session → `viewer`

### Password Security
```python
# Passwords stored with Django's PBKDF2-SHA256 hasher (bcrypt-compatible)
from django.contrib.auth.hashers import make_password, check_password
beekeeper.password_hash = make_password("raw_password")  # hashed, never plain
```

### Input Sanitization (serializers.py)
- Email: lowercased, trimmed, format-validated
- yield_kg: range check 0 < x ≤ 500, rounded to 3dp
- notes: trimmed, max 1000 chars
- password_hash: `write_only=True` — never returned in GET responses
- FK fields: DRF `PrimaryKeyRelatedField` validates existence before saving

### CSRF Protection
All POST requests from the frontend include the Django CSRF token:
```javascript
headers: { 'X-CSRFToken': getCookie('csrftoken') }
```

---

## Analytics Endpoints

### `GET /api/yields/?farm_id=&year=`
Single aggregate query — no Python loops:
```sql
SELECT season.name, SUM(yield_kg), COUNT(id), AVG(yield_kg)
FROM tracker_harvest
LEFT JOIN tracker_season ON season_id = season.id
WHERE [filters]
GROUP BY season.name, season.start_month
ORDER BY season.start_month
```
Uses `harvest_date_season_idx` composite index.

**Response:**
```json
{
  "filters": { "farm_id": "1", "year": "2025" },
  "yields_by_season": {
    "Spring": { "total_kg": 45.2,  "harvests": 6, "avg_kg": 7.5 },
    "Summer": { "total_kg": 128.7, "harvests": 9, "avg_kg": 14.3 },
    "Fall":   { "total_kg": 23.0,  "harvests": 5, "avg_kg": 4.6 },
    "Winter": { "total_kg": 5.1,   "harvests": 2, "avg_kg": 2.55 }
  },
  "available_years": [2024, 2025]
}
```

### `GET /api/dashboard/`
All 5 stats in a single DB round-trip. RBAC-scoped for beekeeper role.

---

## Local Setup

```bash
git clone https://github.com/YOUR_USERNAME/bee-farming-tracker.git
cd bee-farming-tracker

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env

python manage.py migrate          # applies schema + all 9 indexes
python seed_data.py               # 3 beekeepers, 6 farms, 37 hives, 64 harvests

python manage.py runserver
# → http://127.0.0.1:8000
```

### Demo Login Credentials

| Email | Password | Role |
| asiimwe@rwenzoriapiary.ug | Pass1234! | admin |
| birungi@kasesehives.ug | Honey#99 | beekeeper |
| tumwebaze@fortportalbees.ug | Miel@2024 | beekeeper |
| nakamya@kibaleforest.ug | Bees@2025 | beekeeper |
| byaruhanga@mbararahive.ug | Hive#2024 | farm_user |
| atuhaire@busongora.ug | Farm@2025 | farm_user |
> The db.sqlite3 is pre-seeded — no `seed_data.py` run needed if you download the ZIP.

---



## API Reference

| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| POST | `/api/auth/login/` | No | Log in, receive session |
| POST | `/api/auth/logout/` | Yes | Destroy session |
| GET | `/api/auth/whoami/` | No | Current role & permissions |
| GET | `/api/dashboard/` | Viewer+ | Summary stats |
| GET | `/api/yields/?farm_id=&year=` | Viewer+ | Seasonal aggregate |
| GET/POST | `/api/harvests/` | Viewer/Beekeeper+ | List/create harvests |
| GET/POST | `/api/hives/?farm_id=` | Viewer/Beekeeper+ | List/create hives |
| GET/POST | `/api/farms/` | Viewer/Beekeeper+ | List/create farms |
| GET | `/api/seasons/` | Viewer+ | Lookup table |

---

## Cloud Deployment (Render)

### 1. Build & Start commands
- **Build:** `pip install -r requirements.txt && python manage.py migrate && python seed_data.py`
- **Start:** `gunicorn config.wsgi:application`

### 2. Environment Variables (Render dashboard)
```
SECRET_KEY=<generate: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=False
ALLOWED_HOSTS=your-app.onrender.com
DB_ENGINE=django.db.backends.postgresql
DB_NAME=<Render PostgreSQL name>
DB_USER=<Render PostgreSQL user>
DB_PASSWORD=<Render PostgreSQL password>
DB_HOST=<Render PostgreSQL host>
DB_PORT=5432
```

### 3. Add Render PostgreSQL service
Create a free PostgreSQL database on Render and copy connection details above.

---

## MVC Architecture

```
HTTP Request
    │
    ▼
config/urls.py ──► tracker/urls.py (DRF Router)
                         │
                         ▼
                   views.py (Controller)
                   ├── RBACMixin.get_queryset()  ← enforces role scope
                   ├── select_related()          ← prevents N+1
                   └── aggregate/annotate()      ← analytics queries
                         │
                         ▼
                   models.py (Model) + DB indexes
                         │
                         ▼
                   serializers.py (Validation/Sanitization)
                         │
                         ▼
                   JSON Response ──► app.js ──► Chart.js (View)
```

---

## Seeded Data

| Entity | Count | Notes |
|---|---|---|

| Beekeepers | 6 | 1 admin, 3 beekeeper, 2 farm_user — Western Uganda |
| Farms | 8 | 2 per beekeeper, Uganda locations |
| Hives | ~50 | 5–8 per farm, mix of Langstroth/Top-bar/Log/Kenya types |
| Seasons | 12 | 4 seasons × 3 years (2024–2026) |
| Harvests | ~200 | Across 2024–2025, all 4 Uganda seasons |
| Total Yield | ~3,000 kg | Realistic seasonal distribution |
