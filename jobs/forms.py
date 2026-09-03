from django import forms
from django.contrib.auth.models import User

from .models import Job, UserProfile


class JobCreateForm(forms.ModelForm):
    """Form for creating a new repair job."""

    class Meta:
        model = Job
        fields = [
            "customer_name",
            "customer_phone",
            "license_plate",
            "vehicle_make",
            "vehicle_model",
            "description",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "customer_name": "Customer Name",
            "customer_phone": "Customer Phone",
            "license_plate": "License Plate",
            "vehicle_make": "Vehicle Make",
            "vehicle_model": "Vehicle Model",
            "description": "Work Required / Issue Description",
        }


class JobEditForm(forms.ModelForm):
    """Form for editing an existing job (owner can also manually change status)."""

    class Meta:
        model = Job
        fields = [
            "customer_name",
            "customer_phone",
            "license_plate",
            "vehicle_make",
            "vehicle_model",
            "description",
            "status",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "customer_name": "Customer Name",
            "customer_phone": "Customer Phone",
            "license_plate": "License Plate",
            "vehicle_make": "Vehicle Make",
            "vehicle_model": "Vehicle Model",
            "description": "Work Required / Issue Description",
            "status": "Job Status",
        }


class AssignTechnicianForm(forms.Form):
    """Form for assigning or unassigning a technician to a job."""

    technician = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="— Unassign Technician —",
        label="Assign Technician",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show users with the technician role
        technician_ids = UserProfile.objects.filter(
            role=UserProfile.Role.TECHNICIAN
        ).values_list("user_id", flat=True)
        self.fields["technician"].queryset = User.objects.filter(
            id__in=technician_ids
        ).order_by("username")
        self.fields["technician"].label_from_instance = lambda u: u.username
