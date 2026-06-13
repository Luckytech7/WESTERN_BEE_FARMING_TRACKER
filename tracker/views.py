"""
views.py
========
MVC Controller layer.

Security:
  - All writes/deletes blocked for 'viewer' role via RBACMixin
  - Beekeeper role sees only their own farms/hives/harvests
  - Input validation via DRF serializers (type coercion, range checks, FK checks)
  - Passwords hashed with PBKDF2 (Django default), never returned in responses

N+1 Prevention:
  - All querysets use select_related() for FK traversal
  - Aggregate queries use a single JOIN+GROUP BY, not Python loops
"""
from django.db.models import Sum, Count, Avg, Max
from django.db.models.functions import ExtractYear
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from rest_framework.parsers import JSONParser
from rest_framework.decorators import api_view, action, parser_classes
import json

from rest_framework import viewsets, status
from rest_framework.response import Response

from .models import Beekeeper, Farm, Hive, Season, Harvest
from .serializers import (
    BeekeeperSerializer, FarmSerializer,
    HiveSerializer, SeasonSerializer, HarvestSerializer
)
from .permissions import (
    RBACMixin, get_session_role, get_session_beekeeper_id,
    has_permission, ROLE_ADMIN, ROLE_BEEKEEPER, ROLE_VIEWER
)


# ── Page view ─────────────────────────────────────────────────────────────────

def index(request):
    return render(request, 'index.html')


# ── Auth ──────────────────────────────────────────────────────────────────────

@csrf_exempt
def login_view(request):
    """
    POST /api/auth/login/
    Plain Django view — bypasses DRF parser to avoid Content-Type negotiation issues.
    Reads raw body and parses JSON directly, accepting any Content-Type.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)

    # Parse body regardless of Content-Type header
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

    role = ROLE_ADMIN if email.endswith('@admin.bee') else ROLE_BEEKEEPER

    request.session['role'] = role
    request.session['beekeeper_id'] = bk.id
    request.session['beekeeper_name'] = bk.name
    request.session.modified = True

    return JsonResponse({
        'message': f'Welcome, {bk.name}!',
        'role': role,
        'beekeeper_id': bk.id,
        'beekeeper_name': bk.name,
    })


@api_view(['POST'])
def logout_view(request):
    request.session.flush()
    return Response({'message': 'Logged out.'})


@api_view(['GET'])
def whoami(request):
    """Return current session role and identity."""
    return Response({
        'role': get_session_role(request),
        'beekeeper_id': get_session_beekeeper_id(request),
        'beekeeper_name': request.session.get('beekeeper_name'),
        'permissions': {
            'can_read':   has_permission(request, 'read'),
            'can_write':  has_permission(request, 'write'),
            'can_delete': has_permission(request, 'delete'),
        }
    })


# ── ViewSets ──────────────────────────────────────────────────────────────────

class BeekeeperViewSet(RBACMixin, viewsets.ModelViewSet):
    """
    N+1 prevention: farm_count is annotated at DB level via prefetch_related.
    Password is never returned (excluded from serializer fields).
    """
    queryset = Beekeeper.objects.prefetch_related('farms').all()
    serializer_class = BeekeeperSerializer

    @action(detail=True, methods=['get'])
    def farms(self, request, pk=None):
        beekeeper = self.get_object()
        # select_related prevents N+1 on beekeeper lookup per farm
        serializer = FarmSerializer(
            beekeeper.farms.select_related('beekeeper').all(), many=True
        )
        return Response(serializer.data)


class FarmViewSet(RBACMixin, viewsets.ModelViewSet):
    """
    select_related('beekeeper') prevents N+1 when serializer reads beekeeper.name.
    """
    queryset = Farm.objects.select_related('beekeeper').all()
    serializer_class = FarmSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        beekeeper_id = self.request.query_params.get('beekeeper_id')
        if beekeeper_id:
            qs = qs.filter(beekeeper_id=beekeeper_id)
        return qs


class HiveViewSet(RBACMixin, viewsets.ModelViewSet):
    """
    select_related('farm') prevents N+1 when serializer reads farm.name.
    Composite index hive_farm_status_idx used by farm+status filter.
    """
    queryset = Hive.objects.select_related('farm', 'farm__beekeeper').all()
    serializer_class = HiveSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        farm_id = self.request.query_params.get('farm_id')
        hive_status = self.request.query_params.get('status')
        if farm_id:
            qs = qs.filter(farm_id=farm_id)
        if hive_status:
            qs = qs.filter(status=hive_status)
        return qs


class SeasonViewSet(viewsets.ReadOnlyModelViewSet):
    """Seasons are a lookup table — read-only for all roles."""
    queryset = Season.objects.all()
    serializer_class = SeasonSerializer


class HarvestViewSet(RBACMixin, viewsets.ModelViewSet):
    """
    select_related('hive__farm', 'season') prevents N+1:
    - Without it: 1 query for harvests + N queries for hive + N for farm + N for season
    - With it: 1 JOIN query total
    """
    queryset = Harvest.objects.select_related(
        'hive', 'hive__farm', 'hive__farm__beekeeper', 'season'
    ).all()
    serializer_class = HarvestSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        farm_id    = self.request.query_params.get('farm_id')
        hive_id    = self.request.query_params.get('hive_id')
        year       = self.request.query_params.get('year')
        season_id  = self.request.query_params.get('season_id')
        honey_type = self.request.query_params.get('honey_type')
        if farm_id:    qs = qs.filter(hive__farm_id=farm_id)
        if hive_id:    qs = qs.filter(hive_id=hive_id)
        if year:       qs = qs.filter(harvest_date__year=year)
        if season_id:  qs = qs.filter(season_id=season_id)
        if honey_type: qs = qs.filter(honey_type=honey_type)
        return qs.order_by('-harvest_date')


# ── Analytics endpoints ───────────────────────────────────────────────────────

@api_view(['GET'])
def seasonal_yields(request):
    """
    GET /api/yields/?farm_id=&year=

    Single aggregation query — no Python loops over rows:
      SELECT season__name, SUM(yield_kg), COUNT(id), AVG(yield_kg)
      FROM harvest
      LEFT JOIN season ON ...
      WHERE [filters]
      GROUP BY season__name
      ORDER BY season__start_month

    Uses harvest_date_season_idx composite index for the WHERE+GROUP.
    """
    farm_id = request.query_params.get('farm_id')
    year    = request.query_params.get('year')

    qs = Harvest.objects.select_related('season')

    # RBAC: beekeeper sees only their own data
    bk_id = get_session_beekeeper_id(request)
    role  = get_session_role(request)
    if role == ROLE_BEEKEEPER and bk_id:
        qs = qs.filter(hive__farm__beekeeper_id=bk_id)

    if farm_id: qs = qs.filter(hive__farm_id=farm_id)
    if year:    qs = qs.filter(harvest_date__year=year)

    # ── Single GROUP BY query — no N+1 ──────────────────────────────────────
    grouped = (
        qs.values('season__name', 'season__start_month')
          .annotate(
              total_kg=Sum('yield_kg'),
              harvests=Count('id'),
              avg_kg=Avg('yield_kg'),
          )
          .order_by('season__start_month')
    )

    yields_by_season = {}
    for row in grouped:
        name = row['season__name'] or 'Unknown'
        yields_by_season[name] = {
            'total_kg':  round(row['total_kg']  or 0, 2),
            'harvests':  row['harvests'],
            'avg_kg':    round(row['avg_kg']    or 0, 2),
        }

    available_years = list(
        Harvest.objects
               .annotate(year=ExtractYear('harvest_date'))
               .values_list('year', flat=True)
               .distinct()
               .order_by('year')
    )

    return Response({
        'filters': {'farm_id': farm_id, 'year': year},
        'yields_by_season': yields_by_season,
        'available_years': available_years,
    })


@api_view(['GET'])
def dashboard_stats(request):
    """
    GET /api/dashboard/
    All aggregates computed in a single DB round-trip each.
    RBAC: beekeeper gets their own numbers only.
    """
    harvest_qs = Harvest.objects.all()
    hive_qs    = Hive.objects.all()
    farm_qs    = Farm.objects.all()

    bk_id = get_session_beekeeper_id(request)
    role  = get_session_role(request)
    if role == ROLE_BEEKEEPER and bk_id:
        farm_qs    = farm_qs.filter(beekeeper_id=bk_id)
        hive_qs    = hive_qs.filter(farm__beekeeper_id=bk_id)
        harvest_qs = harvest_qs.filter(hive__farm__beekeeper_id=bk_id)

    agg = harvest_qs.aggregate(
        total=Sum('yield_kg'),
        count=Count('id'),
        best=Max('yield_kg'),
    )

    return Response({
        'total_beekeepers':       Beekeeper.objects.count(),
        'total_farms':            farm_qs.count(),
        'total_active_hives':     hive_qs.filter(status='active').count(),
        'total_harvests':         agg['count'] or 0,
        'total_yield_kg':         round(agg['total'] or 0, 2),
        'best_single_harvest_kg': agg['best'] or 0,
        'current_role':           role,
    })