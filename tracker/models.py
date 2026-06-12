from django.db import models
from django.contrib.auth.hashers import make_password, check_password


class Beekeeper(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['email'], name='beekeeper_email_idx'),
        ]

    def __str__(self):
        return self.name

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password_hash)

    @property
    def farm_count(self):
        return self.farms.count()


class Farm(models.Model):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=300)
    established_date = models.DateField()
    beekeeper = models.ForeignKey(
        Beekeeper, on_delete=models.CASCADE, related_name='farms'
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['beekeeper'], name='farm_beekeeper_idx'),
        ]

    def __str__(self):
        return f"{self.name} – {self.location}"


class Hive(models.Model):
    HIVE_TYPE_CHOICES = [
        ('langstroth', 'Langstroth'),
        ('top_bar', 'Top-bar'),
        ('warre', 'Warré'),
        ('flow', 'Flow Hive'),
    ]
    QUEEN_STATUS_CHOICES = [
        ('mated', 'Mated'),
        ('new', 'New'),
        ('replaced', 'Replaced'),
        ('queenless', 'Queenless'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    hive_number = models.CharField(max_length=50)
    hive_type = models.CharField(max_length=50, choices=HIVE_TYPE_CHOICES, default='langstroth')
    install_date = models.DateField()
    queen_status = models.CharField(max_length=50, choices=QUEEN_STATUS_CHOICES, default='mated')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='hives')

    class Meta:
        ordering = ['farm', 'hive_number']
        unique_together = [['farm', 'hive_number']]
        indexes = [
            models.Index(fields=['farm'], name='hive_farm_idx'),
            models.Index(fields=['status'], name='hive_status_idx'),
            # Composite: most common filter is farm+status
            models.Index(fields=['farm', 'status'], name='hive_farm_status_idx'),
        ]

    def __str__(self):
        return f"Hive {self.hive_number} @ {self.farm.name}"


class Season(models.Model):
    name = models.CharField(max_length=50, unique=True)
    start_month = models.IntegerField()
    end_month = models.IntegerField()

    class Meta:
        ordering = ['start_month']

    def __str__(self):
        return self.name

    @classmethod
    def get_for_month(cls, month: int):
        for season in cls.objects.all():
            if season.start_month <= season.end_month:
                if season.start_month <= month <= season.end_month:
                    return season
            else:
                if month >= season.start_month or month <= season.end_month:
                    return season
        return None


class Harvest(models.Model):
    HONEY_TYPE_CHOICES = [
        ('wildflower', 'Wildflower'),
        ('clover', 'Clover'),
        ('acacia', 'Acacia'),
        ('manuka', 'Manuka'),
        ('buckwheat', 'Buckwheat'),
        ('other', 'Other'),
    ]

    harvest_date = models.DateField()
    yield_kg = models.FloatField()
    honey_type = models.CharField(max_length=50, choices=HONEY_TYPE_CHOICES, default='wildflower')
    notes = models.TextField(blank=True, default='')
    hive = models.ForeignKey(Hive, on_delete=models.CASCADE, related_name='harvests')
    season = models.ForeignKey(
        Season, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='harvests'
    )

    class Meta:
        ordering = ['-harvest_date']
        indexes = [
            models.Index(fields=['hive'], name='harvest_hive_idx'),
            models.Index(fields=['season'], name='harvest_season_idx'),
            models.Index(fields=['harvest_date'], name='harvest_date_idx'),
            # Composite for the most common analytics query: date + season
            models.Index(fields=['harvest_date', 'season'], name='harvest_date_season_idx'),
        ]

    def __str__(self):
        return f"{self.yield_kg}kg ({self.honey_type}) from {self.hive} on {self.harvest_date}"

    def save(self, *args, **kwargs):
        if self.harvest_date:
            self.season = Season.get_for_month(self.harvest_date.month)
        super().save(*args, **kwargs)
