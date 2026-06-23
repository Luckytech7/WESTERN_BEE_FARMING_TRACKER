import os, random
from datetime import date, timedelta
from django.db.models import Sum, Count, Avg, Max
from django.db.models.functions import ExtractYear
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from rest_framework.parsers import JSONParser
from rest_framework.decorators import api_view, action, parser_classes
from rest_framework import viewsets, status
from rest_framework.response import Response
import json

from .models import Beekeeper, Farm, Hive, Season, Harvest
from .serializers import (
    BeekeeperSerializer, FarmSerializer,
    HiveSerializer, SeasonSerializer, HarvestSerializer
)
from .permissions import (
    RBACMixin, get_session_role, get_session_beekeeper_id,
    has_permission, ROLE_ADMIN, ROLE_BEEKEEPER, ROLE_FARM_USER, ROLE_VIEWER
)
from . import exports as _exports
from .audit import log_action
from .models import AuditLog


# ── Audit mixin ───────────────────────────────────────────────────────────────

class AuditMixin:
    """Logs create / update / delete on any ModelViewSet."""

    def perform_create(self, serializer):
        instance = serializer.save()
        log_action(self.request, 'create',
                   resource=instance.__class__.__name__,
                   resource_id=instance.pk,
                   detail=str(instance))

    def perform_update(self, serializer):
        instance = serializer.save()
        log_action(self.request, 'update',
                   resource=instance.__class__.__name__,
                   resource_id=instance.pk,
                   detail=str(instance))

    def perform_destroy(self, instance):
        resource    = instance.__class__.__name__
        resource_id = instance.pk
        detail      = str(instance)
        instance.delete()
        log_action(self.request, 'delete',
                   resource=resource,
                   resource_id=resource_id,
                   detail=detail)


def index(request):
    return render(request, 'index.html')


def admin_panel(request):
    return render(request, 'admin_panel.html')


# ── Auth ──────────────────────────────────────────────────────────────────────

@csrf_exempt
def login_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    email    = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))

    if not email or not password:
        return JsonResponse({'error': 'Email and password are required.'}, status=400)
    if len(email) > 254 or len(password) > 128:
        return JsonResponse({'error': 'Invalid input length.'}, status=400)

    try:
        bk = Beekeeper.objects.get(email=email)
    except Beekeeper.DoesNotExist:
        return JsonResponse({'error': 'Invalid credentials.'}, status=401)

    if not bk.check_password(password):
        return JsonResponse({'error': 'Invalid credentials.'}, status=401)

    # Role comes from the DB record
    role = bk.role

    request.session['role']            = role
    request.session['beekeeper_id']    = bk.id
    request.session['beekeeper_name']  = bk.name
    request.session.modified           = True

    log_action(request, 'login', resource='Beekeeper', resource_id=bk.id,
               detail=f'{bk.name} ({role}) logged in')

    return JsonResponse({
        'message':        f'Welcome, {bk.name}!',
        'role':           role,
        'beekeeper_id':   bk.id,
        'beekeeper_name': bk.name,
    })


@api_view(['POST'])
def logout_view(request):
    log_action(request, 'logout', resource='Beekeeper',
               resource_id=request.session.get('beekeeper_id', ''),
               detail=f"{request.session.get('beekeeper_name', 'Unknown')} logged out")
    request.session.flush()
    return Response({'message': 'Logged out.'})


@api_view(['POST'])
def change_password(request):
    bk_id = get_session_beekeeper_id(request)
    if not bk_id:
        return Response({'error': 'Not authenticated.'}, status=401)

    current  = str(request.data.get('current_password', ''))
    new_pw   = str(request.data.get('new_password', ''))
    confirm  = str(request.data.get('confirm_password', ''))

    if not current or not new_pw or not confirm:
        return Response({'error': 'All fields are required.'}, status=400)
    if new_pw != confirm:
        return Response({'error': 'New passwords do not match.'}, status=400)
    if len(new_pw) < 6:
        return Response({'error': 'Password must be at least 6 characters.'}, status=400)

    try:
        bk = Beekeeper.objects.get(pk=bk_id)
    except Beekeeper.DoesNotExist:
        return Response({'error': 'Account not found.'}, status=404)

    if not bk.check_password(current):
        return Response({'error': 'Current password is incorrect.'}, status=400)

    bk.set_password(new_pw)
    bk.save(update_fields=['password_hash'])
    log_action(request, 'password_change', resource='Beekeeper', resource_id=bk.id,
               detail=f'{bk.name} changed their own password')
    return Response({'message': 'Password changed successfully.'})


@api_view(['GET'])
def whoami(request):
    return Response({
        'role':           get_session_role(request),
        'beekeeper_id':   get_session_beekeeper_id(request),
        'beekeeper_name': request.session.get('beekeeper_name'),
        'permissions': {
            'can_read':   has_permission(request, 'read'),
            'can_write':  has_permission(request, 'write'),
            'can_delete': has_permission(request, 'delete'),
        }
    })


# ── ViewSets ──────────────────────────────────────────────────────────────────

class BeekeeperViewSet(AuditMixin, RBACMixin, viewsets.ModelViewSet):
    queryset          = Beekeeper.objects.prefetch_related('farms').all()
    serializer_class  = BeekeeperSerializer

    def create(self, request, *args, **kwargs):
        if get_session_role(request) != ROLE_ADMIN:
            return Response({'error': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if get_session_role(request) != ROLE_ADMIN:
            return Response({'error': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def farms(self, request, pk=None):
        serializer = FarmSerializer(
            self.get_object().farms.select_related('beekeeper').all(), many=True
        )
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='set_password')
    def set_password(self, request, pk=None):
        if get_session_role(request) != ROLE_ADMIN:
            return Response({'error': 'Admin only.'}, status=403)
        new_pw  = str(request.data.get('new_password', ''))
        confirm = str(request.data.get('confirm_password', ''))
        if not new_pw or not confirm:
            return Response({'error': 'Both fields are required.'}, status=400)
        if new_pw != confirm:
            return Response({'error': 'Passwords do not match.'}, status=400)
        if len(new_pw) < 6:
            return Response({'error': 'Password must be at least 6 characters.'}, status=400)
        bk = self.get_object()
        bk.set_password(new_pw)
        bk.save(update_fields=['password_hash'])
        log_action(request, 'password_change', resource='Beekeeper', resource_id=bk.id,
                   detail=f"Admin reset password for {bk.name}")
        return Response({'message': f'Password for {bk.name} has been reset.'})


class FarmViewSet(AuditMixin, RBACMixin, viewsets.ModelViewSet):
    queryset         = Farm.objects.select_related('beekeeper').all()
    serializer_class = FarmSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        bk = self.request.query_params.get('beekeeper_id')
        if bk: qs = qs.filter(beekeeper_id=bk)
        return qs


class HiveViewSet(AuditMixin, RBACMixin, viewsets.ModelViewSet):
    queryset         = Hive.objects.select_related('farm', 'farm__beekeeper').all()
    serializer_class = HiveSerializer

    def get_queryset(self):
        qs     = super().get_queryset()
        farm   = self.request.query_params.get('farm_id')
        hstatus= self.request.query_params.get('status')
        if farm:    qs = qs.filter(farm_id=farm)
        if hstatus: qs = qs.filter(status=hstatus)
        return qs


class SeasonViewSet(AuditMixin, viewsets.ModelViewSet):
    queryset         = Season.objects.all()
    serializer_class = SeasonSerializer

    def get_queryset(self):
        qs   = super().get_queryset()
        year = self.request.query_params.get('year')
        if year: qs = qs.filter(year=year)
        return qs


class HarvestViewSet(AuditMixin, RBACMixin, viewsets.ModelViewSet):
    queryset = Harvest.objects.select_related(
        'hive', 'hive__farm', 'hive__farm__beekeeper', 'season'
    ).all()
    serializer_class = HarvestSerializer

    def get_queryset(self):
        qs        = super().get_queryset()
        farm_id   = self.request.query_params.get('farm_id')
        hive_id   = self.request.query_params.get('hive_id')
        year      = self.request.query_params.get('year')
        season_id = self.request.query_params.get('season_id')
        if farm_id:   qs = qs.filter(hive__farm_id=farm_id)
        if hive_id:   qs = qs.filter(hive_id=hive_id)
        if year:      qs = qs.filter(harvest_date__year=year)
        if season_id: qs = qs.filter(season_id=season_id)
        return qs.order_by('-harvest_date')


# ── Analytics ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
def seasonal_yields(request):
    farm_id = request.query_params.get('farm_id')
    year    = request.query_params.get('year')

    qs = Harvest.objects.select_related('season')
    bk_id = get_session_beekeeper_id(request)
    role  = get_session_role(request)
    if role in (ROLE_BEEKEEPER, ROLE_FARM_USER) and bk_id:
        qs = qs.filter(hive__farm__beekeeper_id=bk_id)
    if farm_id: qs = qs.filter(hive__farm_id=farm_id)
    if year:    qs = qs.filter(harvest_date__year=year)

    grouped = (
        qs.values('season__name', 'season__year', 'season__start_month')
          .annotate(total_kg=Sum('yield_kg'), harvests=Count('id'), avg_kg=Avg('yield_kg'))
          .order_by('season__year', 'season__start_month')
    )

    yields_by_season = {}
    for row in grouped:
        key = f"{row['season__name']} {row['season__year']}" if row['season__name'] else 'Unknown'
        yields_by_season[key] = {
            'total_kg': round(row['total_kg'] or 0, 2),
            'harvests': row['harvests'],
            'avg_kg':   round(row['avg_kg']   or 0, 2),
        }

    available_years = list(
        Harvest.objects.annotate(yr=ExtractYear('harvest_date'))
               .values_list('yr', flat=True).distinct().order_by('yr')
    )

    return Response({
        'filters':          {'farm_id': farm_id, 'year': year},
        'yields_by_season': yields_by_season,
        'available_years':  available_years,
    })


@api_view(['GET'])
def dashboard_stats(request):
    harvest_qs = Harvest.objects.all()
    hive_qs    = Hive.objects.all()
    farm_qs    = Farm.objects.all()

    bk_id = get_session_beekeeper_id(request)
    role  = get_session_role(request)
    if role in (ROLE_BEEKEEPER, ROLE_FARM_USER) and bk_id:
        farm_qs    = farm_qs.filter(beekeeper_id=bk_id)
        hive_qs    = hive_qs.filter(farm__beekeeper_id=bk_id)
        harvest_qs = harvest_qs.filter(hive__farm__beekeeper_id=bk_id)

    agg = harvest_qs.aggregate(total=Sum('yield_kg'), count=Count('id'), best=Max('yield_kg'))
    return Response({
        'total_beekeepers':       Beekeeper.objects.count(),
        'total_farms':            farm_qs.count(),
        'total_active_hives':     hive_qs.filter(status='active').count(),
        'total_harvests':         agg['count'] or 0,
        'total_yield_kg':         round(agg['total'] or 0, 2),
        'best_single_harvest_kg': agg['best'] or 0,
        'current_role':           role,
    })


# ── Admin API endpoints ────────────────────────────────────────────────────────

@api_view(['GET'])
def admin_stats(request):
    """Extended stats for the admin panel."""
    if get_session_role(request) != ROLE_ADMIN:
        return Response({'error': 'Admin only.'}, status=403)

    seasons_by_year = {}
    for s in Season.objects.all():
        seasons_by_year.setdefault(s.year, []).append({
            'id': s.id, 'name': s.name,
            'start_month': s.start_month, 'end_month': s.end_month
        })

    return Response({
        'beekeepers_by_role': list(
            Beekeeper.objects.values('role').annotate(count=Count('id'))
        ),
        'harvests_per_farm': list(
            Harvest.objects.values('hive__farm__name')
                   .annotate(total=Sum('yield_kg'), count=Count('id'))
                   .order_by('-total')[:10]
        ),
        'seasons_by_year': seasons_by_year,
        'hives_by_type': list(
            Hive.objects.values('hive_type').annotate(count=Count('id'))
        ),
    })


# ── Export ────────────────────────────────────────────────────────────────────

VALID_RESOURCES = {'beekeepers', 'farms', 'hives', 'seasons', 'harvests'}
VALID_FORMATS   = {'xlsx', 'pdf'}


@api_view(['GET'])
def export_data(request):
    """
    GET /api/export/?resource=<name>&format=<xlsx|pdf>

    Optional filter params (same as the respective ViewSet):
      farm_id, hive_id, beekeeper_id, season_id, year, status, role
    """
    if not has_permission(request, 'read'):
        return Response({'error': 'Authentication required.'}, status=401)

    resource = request.query_params.get('resource', '').lower()
    # Use 'export_format' not 'format' — DRF hijacks ?format= for content negotiation
    fmt      = request.query_params.get('export_format', 'xlsx').lower()

    if resource not in VALID_RESOURCES:
        return Response(
            {'error': f"Invalid resource. Choose from: {', '.join(sorted(VALID_RESOURCES))}"},
            status=400,
        )
    if fmt not in VALID_FORMATS:
        return Response(
            {'error': "Invalid export_format. Choose 'xlsx' or 'pdf'."},
            status=400,
        )

    # Non-admin beekeepers can only export their own data
    bk_id = get_session_beekeeper_id(request)
    role  = get_session_role(request)
    params = dict(request.query_params)
    # Flatten single-value lists from QueryDict
    params = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in params.items()}
    # Remove control keys so they don't confuse filter functions
    params.pop('resource', None)
    params.pop('export_format', None)

    if role in (ROLE_BEEKEEPER, ROLE_FARM_USER) and bk_id:
        params.setdefault('beekeeper_id', str(bk_id))

    log_action(request, 'export', resource=resource.capitalize(),
               detail=f'Exported {resource} as {fmt.upper()}')

    if fmt == 'xlsx':
        return _exports.export_excel(resource, params)
    return _exports.export_pdf(resource, params)


# ── Audit Log ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
def audit_log_view(request):
    if get_session_role(request) != ROLE_ADMIN:
        return Response({'error': 'Admin only.'}, status=403)

    qs = AuditLog.objects.all()

    action_filter   = request.query_params.get('action')
    resource_filter = request.query_params.get('resource')
    actor_filter    = request.query_params.get('actor')
    date_from       = request.query_params.get('date_from')
    date_to         = request.query_params.get('date_to')

    if action_filter:   qs = qs.filter(action=action_filter)
    if resource_filter: qs = qs.filter(resource__iexact=resource_filter)
    if actor_filter:    qs = qs.filter(actor_name__icontains=actor_filter)
    if date_from:       qs = qs.filter(timestamp__date__gte=date_from)
    if date_to:         qs = qs.filter(timestamp__date__lte=date_to)

    page_size = min(int(request.query_params.get('page_size', 100)), 500)
    page      = max(int(request.query_params.get('page', 1)), 1)
    offset    = (page - 1) * page_size
    total     = qs.count()
    entries   = qs[offset: offset + page_size]

    return Response({
        'total': total,
        'page':  page,
        'page_size': page_size,
        'results': [
            {
                'id':          e.id,
                'timestamp':   e.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'actor_name':  e.actor_name,
                'actor_role':  e.actor_role,
                'action':      e.action,
                'resource':    e.resource,
                'resource_id': e.resource_id,
                'detail':      e.detail,
                'ip_address':  e.ip_address,
            }
            for e in entries
        ],
    })


# ── Deploy setup endpoint ─────────────────────────────────────────────────────
# Call once after each deploy: GET /api/setup/?token=<SETUP_SECRET>
# Set SETUP_SECRET in Vercel environment variables.

@csrf_exempt
def setup_view(request):
    secret = os.environ.get('SETUP_SECRET', '')
    if not secret:
        return JsonResponse({'error': 'SETUP_SECRET env var not configured.'}, status=503)
    if request.GET.get('token') != secret:
        return JsonResponse({'error': 'Forbidden.'}, status=403)

    log = []

    # ── Superuser ──────────────────────────────────────────────────────────────
    User = get_user_model()
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email    = os.environ.get('DJANGO_SUPERUSER_EMAIL',    'admin@beetracker.ug')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Admin1234!')
    if User.objects.filter(username=username).exists():
        log.append(f"Superuser '{username}' already exists — skipped.")
    else:
        User.objects.create_superuser(username=username, email=email, password=password)
        log.append(f"Superuser '{username}' created.")

    # ── Seed data ──────────────────────────────────────────────────────────────
    Harvest.objects.all().delete()
    Hive.objects.all().delete()
    Farm.objects.all().delete()
    Beekeeper.objects.all().delete()
    Season.objects.all().delete()

    random.seed(42)

    season_defs = [
        ('Long Rains',   3, 5),
        ('Long Dry',     6, 8),
        ('Short Rains',  9, 11),
        ('Short Dry',   12, 2),
    ]
    for year in [2024, 2025, 2026]:
        for name, start, end in season_defs:
            Season.objects.create(name=name, year=year, start_month=start, end_month=end)

    beekeepers_data = [
        ('Asiimwe Robert',     'asiimwe@rwenzoriapiary.ug',   'Pass1234!', 'admin'),
        ('Birungi Immaculate', 'birungi@kasesehives.ug',      'Honey#99',  'beekeeper'),
        ('Tumwebaze Gerald',   'tumwebaze@fortportalbees.ug', 'Miel@2024', 'beekeeper'),
        ('Nakamya Prossy',     'nakamya@kibaleforest.ug',     'Bees@2025', 'beekeeper'),
        ('Byaruhanga Moses',   'byaruhanga@mbararahive.ug',   'Hive#2024', 'farm_user'),
        ('Atuhaire Grace',     'atuhaire@busongora.ug',       'Farm@2025', 'farm_user'),
    ]
    beekeepers = []
    for name, email_bk, pw, role in beekeepers_data:
        beekeepers.append(Beekeeper.objects.create(
            name=name, email=email_bk,
            password_hash=make_password(pw), role=role,
        ))

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
            name=name, location=location, established_date=est,
            beekeeper=beekeepers[bk_idx],
        ))

    hive_types   = ['langstroth', 'langstroth', 'top_bar', 'top_bar', 'log_hive', 'kenya_top']
    queen_states = ['mated', 'mated', 'mated', 'new', 'replaced']
    statuses     = ['active'] * 7 + ['inactive']
    all_hives = []
    for farm in farms:
        prefix = ''.join(w[0] for w in farm.name.split()[:2]).upper()
        for i in range(1, random.randint(5, 9)):
            all_hives.append(Hive.objects.create(
                hive_number  = f"{prefix}-{i:02d}",
                hive_type    = random.choice(hive_types),
                install_date = farm.established_date + timedelta(days=random.randint(0, 60)),
                queen_status = random.choice(queen_states),
                status       = random.choice(statuses),
                farm         = farm,
            ))

    active_hives = [h for h in all_hives if h.status == 'active']
    YIELD_RANGES = {
        'Long Rains': (18, 35), 'Long Dry': (10, 22),
        'Short Rains': (14, 28), 'Short Dry': (4, 12),
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
                h_year = year + 1 if season_name == 'Short Dry' and month in (1, 2) else year
                if h_year > 2025:
                    continue
                Harvest.objects.create(
                    harvest_date = date(h_year, month, random.randint(1, 28)),
                    yield_kg     = round(random.uniform(lo, hi), 2),
                    notes        = '',
                    hive         = random.choice(active_hives),
                )
                harvest_count += 1

    total = Harvest.objects.aggregate(t=Sum('yield_kg'))['t'] or 0
    log.append(
        f"Seeded: {Beekeeper.objects.count()} beekeepers, {Farm.objects.count()} farms, "
        f"{Hive.objects.count()} hives, {Season.objects.count()} seasons, "
        f"{harvest_count} harvests ({round(total, 2)} kg)."
    )

    return JsonResponse({'ok': True, 'log': log})
