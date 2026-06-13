from django.contrib import admin
from django.urls import path, include
from tracker.views import index, admin_panel

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('api/', include('tracker.urls')),
    path('admin/', admin_panel, name='admin-panel'),
    path('', index, name='index'),
]
