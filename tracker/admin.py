from django.contrib import admin
from .models import Beekeeper, Farm, Hive, Season, Harvest


@admin.register(Beekeeper)
class BeekeeperAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'farm_count', 'created_at']
    search_fields = ['name', 'email']
    readonly_fields = ['created_at']

    def farm_count(self, obj):
        return obj.farms.count()
    farm_count.short_description = 'Farms'


class HiveInline(admin.TabularInline):
    model = Hive
    extra = 0
    fields = ['hive_number', 'hive_type', 'status', 'queen_status', 'install_date']


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'beekeeper', 'established_date', 'active_hive_count']
    list_filter = ['beekeeper']
    search_fields = ['name', 'location']
    inlines = [HiveInline]

    def active_hive_count(self, obj):
        return obj.hives.filter(status='active').count()
    active_hive_count.short_description = 'Active Hives'


class HarvestInline(admin.TabularInline):
    model = Harvest
    extra = 0
    fields = ['harvest_date', 'yield_kg', 'honey_type', 'season', 'notes']
    readonly_fields = ['season']


@admin.register(Hive)
class HiveAdmin(admin.ModelAdmin):
    list_display = ['hive_number', 'farm', 'hive_type', 'status', 'queen_status', 'install_date']
    list_filter = ['status', 'hive_type', 'farm', 'queen_status']
    search_fields = ['hive_number', 'farm__name']
    inlines = [HarvestInline]


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_month', 'end_month']


@admin.register(Harvest)
class HarvestAdmin(admin.ModelAdmin):
    list_display = ['harvest_date', 'hive', 'yield_kg', 'honey_type', 'season']
    list_filter = ['season', 'honey_type', 'hive__farm']
    search_fields = ['hive__hive_number', 'hive__farm__name']
    readonly_fields = ['season']
    date_hierarchy = 'harvest_date'
