from django.db import models
from django.contrib.auth.hashers import make_password, check_password


class Beekeeper(models.Model):
    ROLE_CHOICES = [
        ('admin',      'Admin'),
        ('beekeeper',  'Beekeeper'),
        ('farm_user',  'Farm User'),
        ('viewer',     'Viewer'),
    ]

    name          = models.CharField(max_length=200)
    email         = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    role          = models.CharField(max_length=20, choices=ROLE_CHOICES, default='beekeeper')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        indexes  = [models.Index(fields=['email'], name='beekeeper_email_idx')]

    def __str__(self):
        return f"{self.name} ({self.role})"

    def set_password(self, raw):
        self.password_hash = make_password(raw)

    def check_password(self, raw):
        return check_password(raw, self.password_hash)


class Farm(models.Model):
    name             = models.CharField(max_length=200)
    location         = models.CharField(max_length=300)
    established_date = models.DateField()
    beekeeper        = models.ForeignKey(
        Beekeeper, on_delete=models.CASCADE, related_name='farms'
    )

    class Meta:
        ordering = ['name']
        indexes  = [models.Index(fields=['beekeeper'], name='farm_beekeeper_idx')]

    def __str__(self):
        return f"{self.name} – {self.location}"


class Hive(models.Model):
    HIVE_TYPE_CHOICES = [
        ('langstroth', 'Langstroth'),
        ('top_bar',    'Top-bar'),
        ('log_hive',   'Log Hive'),
        ('kenya_top',  'Kenya Top-bar'),
    ]
    QUEEN_STATUS_CHOICES = [
        ('mated',     'Mated'),
        ('new',       'New'),
        ('replaced',  'Replaced'),
        ('queenless', 'Queenless'),
    ]
    STATUS_CHOICES = [
        ('active',   'Active'),
        ('inactive', 'Inactive'),
    ]

    hive_number  = models.CharField(max_length=50)
    hive_type    = models.CharField(max_length=50, choices=HIVE_TYPE_CHOICES, default='langstroth')
    install_date = models.DateField()
    queen_status = models.CharField(max_length=50, choices=QUEEN_STATUS_CHOICES, default='mated')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    farm         = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='hives')

    class Meta:
        ordering       = ['farm', 'hive_number']
        unique_together = [['farm', 'hive_number']]
        indexes = [
            models.Index(fields=['farm'],          name='hive_farm_idx'),
            models.Index(fields=['status'],        name='hive_status_idx'),
            models.Index(fields=['farm', 'status'], name='hive_farm_status_idx'),
        ]

    def __str__(self):
        return f"Hive {self.hive_number} @ {self.farm.name}"


class Season(models.Model):
    """
    Season is now scoped per year.
    e.g.  name='Dry Season', year=2025, start_month=12, end_month=2
    Multiple seasons can exist for the same year.
    """
    name        = models.CharField(max_length=50)
    year        = models.IntegerField()
    start_month = models.IntegerField()   # 1–12
    end_month   = models.IntegerField()   # 1–12

    class Meta:
        ordering        = ['year', 'start_month']
        unique_together = [['name', 'year']]

    def __str__(self):
        return f"{self.name} {self.year}"

    @classmethod
    def get_for_date(cls, date):
        """Return the Season for a given date, matching year and month range."""
        month = date.month
        year  = date.year
        for season in cls.objects.filter(year=year):
            if season.start_month <= season.end_month:
                if season.start_month <= month <= season.end_month:
                    return season
            else:
                # Wraps year boundary (e.g. Dec–Feb)
                if month >= season.start_month or month <= season.end_month:
                    return season
        # Fallback: try adjacent year for wrap-around seasons
        for season in cls.objects.filter(year=year - 1):
            if season.start_month > season.end_month:
                if month <= season.end_month:
                    return season
        return None


class Harvest(models.Model):
    harvest_date = models.DateField()
    yield_kg     = models.FloatField()
    notes        = models.TextField(blank=True, default='')
    hive         = models.ForeignKey(Hive, on_delete=models.CASCADE, related_name='harvests')
    season       = models.ForeignKey(
        Season, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='harvests'
    )

    class Meta:
        ordering = ['-harvest_date']
        indexes  = [
            models.Index(fields=['hive'],                    name='harvest_hive_idx'),
            models.Index(fields=['season'],                  name='harvest_season_idx'),
            models.Index(fields=['harvest_date'],            name='harvest_date_idx'),
            models.Index(fields=['harvest_date', 'season'],  name='harvest_date_season_idx'),
        ]

    def __str__(self):
        return f"{self.yield_kg}kg from {self.hive} on {self.harvest_date}"

    def save(self, *args, **kwargs):
        if self.harvest_date and self.season is None:
            self.season = Season.get_for_date(self.harvest_date)
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create',          'Create'),
        ('update',          'Update'),
        ('delete',          'Delete'),
        ('login',           'Login'),
        ('logout',          'Logout'),
        ('export',          'Export'),
        ('password_change', 'Password Change'),
    ]

    timestamp   = models.DateTimeField(auto_now_add=True)
    actor_name  = models.CharField(max_length=200, blank=True, default='')
    actor_role  = models.CharField(max_length=20,  blank=True, default='')
    action      = models.CharField(max_length=20,  choices=ACTION_CHOICES)
    resource    = models.CharField(max_length=50,  blank=True, default='')
    resource_id = models.CharField(max_length=50,  blank=True, default='')
    detail      = models.TextField(blank=True, default='')
    ip_address  = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes  = [
            models.Index(fields=['-timestamp'],       name='audit_ts_idx'),
            models.Index(fields=['action'],            name='audit_action_idx'),
            models.Index(fields=['actor_name'],        name='audit_actor_idx'),
        ]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.actor_name}: {self.action} {self.resource}"
