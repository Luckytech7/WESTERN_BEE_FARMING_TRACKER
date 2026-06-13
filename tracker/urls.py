from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'beekeepers', views.BeekeeperViewSet)
router.register(r'farms',      views.FarmViewSet)
router.register(r'hives',      views.HiveViewSet)
router.register(r'seasons',    views.SeasonViewSet)
router.register(r'harvests',   views.HarvestViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('yields/',       views.seasonal_yields,          name='seasonal-yields'),
    path('dashboard/',    views.dashboard_stats,           name='dashboard-stats'),
    path('auth/login/',   csrf_exempt(views.login_view),  name='auth-login'),
    path('auth/logout/',  views.logout_view,               name='auth-logout'),
    path('auth/whoami/',  views.whoami,                    name='auth-whoami'),
]