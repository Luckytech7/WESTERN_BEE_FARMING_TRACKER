from django.db.models import Sum, Count, Avg, Max
from django.db.models.functions import ExtractYear
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
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

    return JsonResponse({
        'message':        f'Welcome, {bk.name}!',
        'role':           role,
        'beekeeper_id':   bk.id,
        'beekeeper_name': bk.name,
    })


@api_view(['POST'])
def logout_view(request):
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

class BeekeeperViewSet(RBACMixin, viewsets.ModelViewSet):
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
        return Response({'message': f'Password for {bk.name} has been reset.'})


class FarmViewSet(RBACMixin, viewsets.ModelViewSet):
    queryset         = Farm.objects.select_related('beekeeper').all()
    serializer_class = FarmSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        bk = self.request.query_params.get('beekeeper_id')
        if bk: qs = qs.filter(beekeeper_id=bk)
        return qs


class HiveViewSet(RBACMixin, viewsets.ModelViewSet):
    queryset         = Hive.objects.select_related('farm', 'farm__beekeeper').all()
    serializer_class = HiveSerializer

    def get_queryset(self):
        qs     = super().get_queryset()
        farm   = self.request.query_params.get('farm_id')
        hstatus= self.request.query_params.get('status')
        if farm:    qs = qs.filter(farm_id=farm)
        if hstatus: qs = qs.filter(status=hstatus)
        return qs


class SeasonViewSet(viewsets.ModelViewSet):
    queryset         = Season.objects.all()
    serializer_class = SeasonSerializer

    def get_queryset(self):
        qs   = super().get_queryset()
        year = self.request.query_params.get('year')
        if year: qs = qs.filter(year=year)
        return qs


class HarvestViewSet(RBACMixin, viewsets.ModelViewSet):
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
