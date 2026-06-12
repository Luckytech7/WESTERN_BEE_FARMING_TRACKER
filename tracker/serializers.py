"""
serializers.py — Input sanitization layer
==========================================
All user input passes through here before touching the DB.
  - Type coercion handled by DRF field types
  - Range validation on yield_kg
  - Email format enforced by EmailField
  - FK integrity checked by PrimaryKeyRelatedField
  - password_hash is write-only: never returned in GET responses
"""
from rest_framework import serializers
from .models import Beekeeper, Farm, Hive, Season, Harvest


class BeekeeperSerializer(serializers.ModelSerializer):
    farm_count = serializers.IntegerField(source='farms.count', read_only=True)
    # password_hash is write_only — never exposed in API responses
    password_hash = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Beekeeper
        fields = ['id', 'name', 'email', 'password_hash', 'created_at', 'farm_count']
        read_only_fields = ['created_at']

    def validate_email(self, value):
        """Normalise to lowercase and trim."""
        return value.strip().lower()

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters.")
        return value


class FarmSerializer(serializers.ModelSerializer):
    beekeeper_name   = serializers.CharField(source='beekeeper.name', read_only=True)
    active_hive_count = serializers.SerializerMethodField()

    class Meta:
        model = Farm
        fields = ['id', 'name', 'location', 'established_date',
                  'beekeeper', 'beekeeper_name', 'active_hive_count']

    def get_active_hive_count(self, obj):
        # Uses hive_farm_status_idx composite index
        return obj.hives.filter(status='active').count()


class HiveSerializer(serializers.ModelSerializer):
    farm_name = serializers.CharField(source='farm.name', read_only=True)

    class Meta:
        model = Hive
        fields = ['id', 'hive_number', 'hive_type', 'install_date',
                  'queen_status', 'status', 'farm', 'farm_name']

    def validate_hive_number(self, value):
        return value.strip().upper()


class SeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Season
        fields = ['id', 'name', 'start_month', 'end_month']


class HarvestSerializer(serializers.ModelSerializer):
    hive_number  = serializers.CharField(source='hive.hive_number', read_only=True)
    farm_name    = serializers.CharField(source='hive.farm.name',   read_only=True)
    farm_id      = serializers.IntegerField(source='hive.farm.id',  read_only=True)
    season_name  = serializers.CharField(source='season.name',      read_only=True)

    class Meta:
        model = Harvest
        fields = ['id', 'harvest_date', 'yield_kg', 'honey_type', 'notes',
                  'hive', 'hive_number', 'farm_id', 'farm_name',
                  'season', 'season_name']
        read_only_fields = ['season']

    def validate_yield_kg(self, value):
        """Range check — prevents junk data and absurd entries."""
        if value <= 0:
            raise serializers.ValidationError("Yield must be greater than 0 kg.")
        if value > 500:
            raise serializers.ValidationError("Yield cannot exceed 500 kg per harvest.")
        return round(value, 3)

    def validate_notes(self, value):
        """Trim whitespace, cap length to prevent oversized payloads."""
        value = value.strip()
        if len(value) > 1000:
            raise serializers.ValidationError("Notes cannot exceed 1000 characters.")
        return value
