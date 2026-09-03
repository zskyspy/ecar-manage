from django import forms
from django.contrib.auth.models import User

from .models import Department, Job, UserProfile


class JobCreateForm(forms.ModelForm):
    """Form for creating a new repair job within a specific department."""

    class Meta:
        model = Job
        fields = [
            "customer_name",
            "customer_phone",
            "license_plate",
            "vehicle_make",
            "vehicle_model",
            "description",
            "department",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "department": forms.HiddenInput(),
        }
        labels = {
            "customer_name": "Customer Name",
            "customer_phone": "Customer Phone",
            "license_plate": "License Plate",
            "vehicle_make": "Vehicle Make",
            "vehicle_model": "Vehicle Model",
            "description": "Work Required / Issue Description",
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if "department" in self.fields:
            self.fields["department"].required = False
            if department:
                self.fields["department"].initial = department


class JobEditForm(forms.ModelForm):
    """Form for editing an existing job (owner can change status or department)."""

    class Meta:
        model = Job
        fields = [
            "customer_name",
            "customer_phone",
            "license_plate",
            "vehicle_make",
            "vehicle_model",
            "description",
            "department",
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
            "department": "Department",
            "status": "Job Status",
        }


class AssignTechnicianForm(forms.Form):
    """
    Form for assigning a technician to a job.
    Strictly filters the pool to technicians belonging to the job's department.
    """

    technician = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="— Unassign Technician —",
        label="Assign Technician",
    )

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.department = department

        # Pool restricted strictly to technicians in this job's department
        tech_profiles = UserProfile.objects.filter(role=UserProfile.Role.TECHNICIAN)
        if department:
            tech_profiles = tech_profiles.filter(department=department)

        technician_ids = tech_profiles.values_list("user_id", flat=True)
        self.fields["technician"].queryset = User.objects.filter(
            id__in=technician_ids
        ).order_by("username")
        self.fields["technician"].label_from_instance = lambda u: u.username

    def clean_technician(self):
        tech = self.cleaned_data.get("technician")
        if tech and self.department:
            if hasattr(tech, "profile") and tech.profile.department != self.department:
                raise forms.ValidationError(
                    f"Technician {tech.username} does not belong to the {self.department} department."
                )
        return tech


class StatusUpdateForm(forms.Form):
    """Form for a technician to post a status update on their assigned job."""

    status = forms.ChoiceField(
        choices=Job.Status.choices,
        label="New Status",
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Add a note (optional)…"}),
        label="Note / Comment",
    )


class OwnerProfileForm(forms.Form):
    """Form for owner to edit personal info."""

    first_name = forms.CharField(max_length=60, required=False, label="First Name")
    last_name = forms.CharField(max_length=60, required=False, label="Last Name")
    email = forms.EmailField(required=False, label="Email Address")
    phone_number = forms.CharField(max_length=30, required=False, label="Phone Number")


class TechnicianCreateForm(forms.Form):
    """Form for owner to onboard a new technician into a specific department."""

    username = forms.CharField(max_length=150, label="Username")
    email = forms.EmailField(required=False, label="Email Address")
    phone_number = forms.CharField(max_length=30, required=False, label="Phone Number")
    department = forms.ChoiceField(
        choices=Department.choices,
        label="Service Department",
        help_text="Choose whether this technician operates in Electronic Repair or Mechanical Repair.",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(),
        label="Temporary Password",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(),
        label="Confirm Password",
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(f"Username '{username}' is already in use.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")
        if pwd and confirm and pwd != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data

