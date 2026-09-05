from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Department(models.TextChoices):
    ELECTRONIC = "electronic", "Electronic Repair"
    MECHANICAL = "mechanical", "Mechanical Repair"


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
    department = models.CharField(
        max_length=20,
        choices=Department.choices,
        null=True,
        blank=True,
        db_index=True,
        help_text="Department assigned to technician (Electronic or Mechanical). Owners oversee both.",
    )
    phone_number = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        dept = f" - {self.get_department_display()}" if self.department else ""
        return f"{self.user.username} ({self.get_role_display()}{dept})"

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER

    @property
    def is_technician(self):
        return self.role == self.Role.TECHNICIAN

    @property
    def is_electronic(self):
        return self.department == Department.ELECTRONIC

    @property
    def is_mechanical(self):
        return self.department == Department.MECHANICAL



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
    department = models.CharField(
        max_length=20,
        choices=Department.choices,
        default=Department.MECHANICAL,
        db_index=True,
        help_text="Department handling this repair (Electronic or Mechanical)",
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


class StatusUpdate(models.Model):
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="status_updates",
    )
    status = models.CharField(
        max_length=30,
        choices=Job.Status.choices,
    )
    note = models.TextField(blank=True)
    technician = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="status_updates",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Status Update"
        verbose_name_plural = "Status Updates"

    def __str__(self):
        return f"Job #{self.job_id} -> {self.get_status_display()} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class Notification(models.Model):
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    target_url = models.CharField(max_length=255, default="/")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"


class PushSubscription(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Push Subscription"
        verbose_name_plural = "Push Subscriptions"

    def __str__(self):
        return f"PushSubscription for {self.user.username} ({self.created_at.strftime('%Y-%m-%d')})"


