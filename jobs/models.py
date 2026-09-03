from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        TECHNICIAN = "technician", "Technician"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.TECHNICIAN,
    )
    phone_number = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER

    @property
    def is_technician(self):
        return self.role == self.Role.TECHNICIAN


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    """
    Ensure every User has an associated UserProfile.
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)
    else:
        if hasattr(instance, "profile"):
            instance.profile.save()
        else:
            UserProfile.objects.get_or_create(user=instance)


class Job(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        WAITING_PARTS = "waiting_parts", "Waiting for Parts"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=30, blank=True)
    vehicle_make = models.CharField(max_length=60)
    vehicle_model = models.CharField(max_length=60)
    vehicle_year = models.PositiveIntegerField(null=True, blank=True)
    license_plate = models.CharField(max_length=20, db_index=True)
    vin = models.CharField(max_length=30, blank=True)
    description = models.TextField(help_text="Issue or requested work")
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    assigned_technician = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_jobs",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Job"
        verbose_name_plural = "Jobs"

    def __str__(self):
        return f"Job #{self.id} - {self.vehicle_make} {self.vehicle_model} ({self.license_plate})"

