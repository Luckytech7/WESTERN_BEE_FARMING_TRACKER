from django.contrib import admin
from django.urls import path, include
from tracker.views import index

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('tracker.urls')),
    path('', index, name='index'),
]
