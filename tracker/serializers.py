from rest_framework import serializers
from .models import Beekeeper, Farm, Hive, Season, Harvest


class BeekeeperSerializer(serializers.ModelSerializer):
    farm_count    = serializers.IntegerField(source='farms.count', read_only=True)
    password_hash = serializers.CharField(write_only=True, required=False)

    class Meta:
        model  = Beekeeper
        fields = ['id', 'name', 'email', 'role', 'password_hash', 'created_at', 'farm_count']
        read_only_fields = ['created_at']

    def validate_email(self, v): return v.strip().lower()
    def validate_name(self, v):
        v = v.strip()
        if len(v) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters.")
        return v

    def create(self, validated_data):
        raw_password = validated_data.pop('password_hash', None)
        instance = Beekeeper(**validated_data)
        if raw_password:
            instance.set_password(raw_password)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        raw_password = validated_data.pop('password_hash', None)
        instance = super().update(instance, validated_data)
        if raw_password:
            instance.set_password(raw_password)
            instance.save(update_fields=['password_hash'])
        return instance


class FarmSerializer(serializers.ModelSerializer):
    beekeeper_name    = serializers.CharField(source='beekeeper.name', read_only=True)
    active_hive_count = serializers.SerializerMethodField()

    class Meta:
        model  = Farm
        fields = ['id', 'name', 'location', 'established_date',
                  'beekeeper', 'beekeeper_name', 'active_hive_count']

    def get_active_hive_count(self, obj):
        return obj.hives.filter(status='active').count()


class HiveSerializer(serializers.ModelSerializer):
    farm_name = serializers.CharField(source='farm.name', read_only=True)

    class Meta:
        model  = Hive
        fields = ['id', 'hive_number', 'hive_type', 'install_date',
                  'queen_status', 'status', 'farm', 'farm_name']

    def validate_hive_number(self, v): return v.strip().upper()


class SeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Season
        fields = ['id', 'name', 'year', 'start_month', 'end_month']

    def validate(self, data):
        if data.get('start_month') and not (1 <= data['start_month'] <= 12):
            raise serializers.ValidationError("start_month must be 1–12.")
        if data.get('end_month') and not (1 <= data['end_month'] <= 12):
            raise serializers.ValidationError("end_month must be 1–12.")
        return data


class HarvestSerializer(serializers.ModelSerializer):
    hive_number = serializers.CharField(source='hive.hive_number', read_only=True)
    farm_name   = serializers.CharField(source='hive.farm.name',   read_only=True)
    farm_id     = serializers.IntegerField(source='hive.farm.id',  read_only=True)
    season_name = serializers.SerializerMethodField()

    class Meta:
        model  = Harvest
        fields = ['id', 'harvest_date', 'yield_kg', 'notes',
                  'hive', 'hive_number', 'farm_id', 'farm_name',
                  'season', 'season_name']
        read_only_fields = ['season']

    def get_season_name(self, obj):
        if obj.season:
            return f"{obj.season.name} {obj.season.year}"
        return None

    def validate_yield_kg(self, v):
        if v <= 0:
            raise serializers.ValidationError("Yield must be greater than 0 kg.")
        if v > 500:
            raise serializers.ValidationError("Yield cannot exceed 500 kg.")
        return round(v, 3)

    def validate_notes(self, v):
        v = v.strip()
        if len(v) > 1000:
            raise serializers.ValidationError("Notes cannot exceed 1000 characters.")
        return v
