from django.contrib import admin
from .models import Beekeeper, Farm, Hive, Season, Harvest


@admin.register(Beekeeper)
class BeekeeperAdmin(admin.ModelAdmin):
    list_display  = ['name', 'email', 'role', 'created_at']
    list_filter   = ['role']
    search_fields = ['name', 'email']
    readonly_fields = ['created_at']


class HiveInline(admin.TabularInline):
    model  = Hive
    extra  = 0
    fields = ['hive_number', 'hive_type', 'status', 'queen_status', 'install_date']


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display  = ['name', 'location', 'beekeeper', 'established_date']
    list_filter   = ['beekeeper']
    search_fields = ['name', 'location']
    inlines       = [HiveInline]


@admin.register(Hive)
class HiveAdmin(admin.ModelAdmin):
    list_display  = ['hive_number', 'farm', 'hive_type', 'status', 'queen_status']
    list_filter   = ['status', 'hive_type', 'farm']
    search_fields = ['hive_number', 'farm__name']


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ['name', 'year', 'start_month', 'end_month']
    list_filter  = ['year', 'name']


@admin.register(Harvest)
class HarvestAdmin(admin.ModelAdmin):
    list_display   = ['harvest_date', 'hive', 'yield_kg', 'season']
    list_filter    = ['season', 'hive__farm']
    search_fields  = ['hive__hive_number', 'hive__farm__name']
    readonly_fields= ['season']
    date_hierarchy = 'harvest_date'
