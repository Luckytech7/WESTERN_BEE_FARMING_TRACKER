from django.contrib import admin
from django.urls import path, include
from tracker.views import index, admin_panel, setup_view

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('api/', include('tracker.urls')),
    path('admin/', admin_panel, name='admin-panel'),
    path('setup/', setup_view, name='setup'),
    path('', index, name='index'),
]
