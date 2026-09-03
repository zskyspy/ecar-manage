from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .mixins import OwnerRequiredMixin, TechnicianRequiredMixin

from .filters import JobFilter
from .models import Department, Job, UserProfile
from .permissions import IsOwner, IsTechnician
from .serializers import (
    CustomTokenObtainPairSerializer,
    JobAssignSerializer,
    JobSerializer,
    StatusUpdateSerializer,
    UserSerializer,
)




def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1;")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "app": "ECAR Space", "database": "connected"})


def home(request):
    """Root route: redirect authenticated users to their portal, or guests to login."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


class CustomTokenObtainPairView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer


class CurrentUserView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OwnerOnlyTestView(APIView):
    permission_classes = (IsAuthenticated, IsOwner)

    def get(self, request):
        return Response(
            {"message": f"Hello Owner {request.user.username}, access granted.", "role": request.user.profile.role},
            status=status.HTTP_200_OK,
        )


class TechnicianOnlyTestView(APIView):
    permission_classes = (IsAuthenticated, IsTechnician)

    def get(self, request):
        return Response(
            {"message": f"Hello Technician {request.user.username}, access granted.", "role": request.user.profile.role},
            status=status.HTTP_200_OK,
        )


class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    filterset_class = JobFilter
    search_fields = ["customer_name", "license_plate", "vehicle_make", "vehicle_model", "vin"]
    ordering_fields = ["created_at", "updated_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Job.objects.none()

        # Owners and superusers can view all jobs
        if getattr(user, "is_superuser", False) or (
            hasattr(user, "profile") and user.profile.is_owner
        ):
            return Job.objects.all().select_related("assigned_technician", "created_by")

        # Technicians can only view jobs assigned to them within their department
        if hasattr(user, "profile") and user.profile.is_technician:
            qs = Job.objects.filter(assigned_technician=user)
            if user.profile.department:
                qs = qs.filter(department=user.profile.department)
            return qs.select_related("assigned_technician", "created_by")

        return Job.objects.none()

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsOwner],
    )
    def assign(self, request, pk=None):
        job = self.get_object()
        serializer = JobAssignSerializer(data=request.data, context={"job": job})
        serializer.is_valid(raise_exception=True)
        tech_id = serializer.validated_data.get("technician_id")
        if tech_id is None:
            job.assigned_technician = None
        else:
            job.assigned_technician_id = tech_id
        job.save()
        return Response(JobSerializer(job).data, status=status.HTTP_200_OK)


    @action(
        detail=True,
        methods=["get", "post"],
        url_path="status-updates",
        permission_classes=[IsAuthenticated],
    )
    def status_updates(self, request, pk=None):
        job = self.get_object()

        if request.method == "GET":
            updates = job.status_updates.all().select_related("technician")
            serializer = StatusUpdateSerializer(updates, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # POST: Must be the assigned technician
        if job.assigned_technician != request.user:
            return Response(
                {"detail": "Only the assigned technician can post status updates for this job."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = StatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_update = serializer.save(job=job, technician=request.user)

        # Update parent Job status
        job.status = status_update.status
        job.save(update_fields=["status", "updated_at"])

        return Response(StatusUpdateSerializer(status_update).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Template-based frontend views (Step 10)
# ---------------------------------------------------------------------------

class DashboardRedirectView(LoginRequiredMixin, View):
    """
    After login, redirect the user to the role-appropriate dashboard.
    Unauthenticated users are sent to /login/ by LoginRequiredMixin.
    """

    def get(self, request, *args, **kwargs):
        user = request.user
        if hasattr(user, "profile") and user.profile.is_technician:
            return redirect("tech_dashboard")
        # Owners, superusers, and any other authenticated users go to owner dashboard
        return redirect("owner_dashboard")


class OwnerDashboardView(OwnerRequiredMixin, View):
    """
    Owner operations portal:
    - High-level workshop analytics across BOTH departments (Electronic & Mechanical)
    - Department-specific breakdowns (jobs by status, active technicians)
    - Cross-department job feed with filtering by department, status, technician, and plate
    """

    template_name = "jobs/owner_dashboard.html"

    def get(self, request):
        from django.contrib.auth.models import User as DjangoUser

        all_jobs = Job.objects.select_related("assigned_technician", "created_by").order_by("-created_at")

        # Cross-department Analytics
        total_jobs = all_jobs.count()
        in_progress = all_jobs.filter(status=Job.Status.IN_PROGRESS).count()
        waiting_parts = all_jobs.filter(status=Job.Status.WAITING_PARTS).count()
        completed = all_jobs.filter(status=Job.Status.COMPLETED).count()
        pending = all_jobs.filter(status=Job.Status.PENDING).count()
        cancelled = all_jobs.filter(status=Job.Status.CANCELLED).count()

        # Electronic department breakdown
        elec_jobs = all_jobs.filter(department=Department.ELECTRONIC)
        elec_total = elec_jobs.count()
        elec_in_progress = elec_jobs.filter(status=Job.Status.IN_PROGRESS).count()
        elec_waiting_parts = elec_jobs.filter(status=Job.Status.WAITING_PARTS).count()
        elec_completed = elec_jobs.filter(status=Job.Status.COMPLETED).count()
        elec_techs_count = UserProfile.objects.filter(
            role=UserProfile.Role.TECHNICIAN, department=Department.ELECTRONIC
        ).count()

        # Mechanical department breakdown
        mech_jobs = all_jobs.filter(department=Department.MECHANICAL)
        mech_total = mech_jobs.count()
        mech_in_progress = mech_jobs.filter(status=Job.Status.IN_PROGRESS).count()
        mech_waiting_parts = mech_jobs.filter(status=Job.Status.WAITING_PARTS).count()
        mech_completed = mech_jobs.filter(status=Job.Status.COMPLETED).count()
        mech_techs_count = UserProfile.objects.filter(
            role=UserProfile.Role.TECHNICIAN, department=Department.MECHANICAL
        ).count()

        total_techs = elec_techs_count + mech_techs_count

        # Filtering for All Jobs feed
        qs = all_jobs
        dept_filter = request.GET.get("department", "").strip().lower()
        status_filter = request.GET.get("status", "").strip()
        tech_filter = request.GET.get("technician", "").strip()
        plate_filter = request.GET.get("plate", "").strip()

        if dept_filter in [Department.ELECTRONIC, Department.MECHANICAL]:
            qs = qs.filter(department=dept_filter)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if tech_filter == "unassigned":
            qs = qs.filter(assigned_technician__isnull=True)
        elif tech_filter:
            qs = qs.filter(assigned_technician__username=tech_filter)
        if plate_filter:
            qs = qs.filter(license_plate__icontains=plate_filter)

        # All technicians for dropdown
        technicians = (
            DjangoUser.objects.filter(profile__role=UserProfile.Role.TECHNICIAN)
            .select_related("profile")
            .order_by("profile__department", "username")
        )

        return render(request, self.template_name, {
            "jobs": qs,
            "total_jobs": total_jobs,
            "in_progress": in_progress,
            "waiting_parts": waiting_parts,
            "completed": completed,
            "pending": pending,
            "cancelled": cancelled,
            "total_techs": total_techs,

            "elec_total": elec_total,
            "elec_in_progress": elec_in_progress,
            "elec_waiting_parts": elec_waiting_parts,
            "elec_completed": elec_completed,
            "elec_techs_count": elec_techs_count,

            "mech_total": mech_total,
            "mech_in_progress": mech_in_progress,
            "mech_waiting_parts": mech_waiting_parts,
            "mech_completed": mech_completed,
            "mech_techs_count": mech_techs_count,

            "technicians": technicians,
            "selected_department": dept_filter,
            "selected_status": status_filter,
            "selected_tech": tech_filter,
            "plate_query": plate_filter,
            "status_choices": Job.Status.choices,
        })



class TechnicianDashboardView(TechnicianRequiredMixin, TemplateView):
    """Technician bay view: lists only jobs assigned to the technician in their department."""

    template_name = "jobs/tech_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        dept = getattr(user.profile, "department", None)
        qs = Job.objects.filter(assigned_technician=user)
        if dept:
            qs = qs.filter(department=dept)
        ctx["jobs"] = qs.prefetch_related("status_updates").order_by("-created_at")
        ctx["department"] = dept
        ctx["department_display"] = user.profile.get_department_display() if dept else "General"
        return ctx


# ---------------------------------------------------------------------------
# Two-Department Owner Views (Electronic & Mechanical)
# ---------------------------------------------------------------------------

class DepartmentJobListView(OwnerRequiredMixin, View):
    """Filterable list of jobs within a specific department (electronic or mechanical)."""

    template_name = "jobs/job_list.html"

    def get(self, request, department="electronic"):
        from django.contrib.auth.models import User as DjangoUser
        from .models import Department, UserProfile

        if department not in (Department.ELECTRONIC, Department.MECHANICAL):
            return redirect("owner_department_jobs", department=Department.ELECTRONIC)

        dept_display = "Electronic Repair" if department == Department.ELECTRONIC else "Mechanical Repair"

        qs = (
            Job.objects.filter(department=department)
            .select_related("assigned_technician", "created_by")
            .order_by("-created_at")
        )

        # Filters within this department
        status_filter = request.GET.get("status", "")
        tech_filter = request.GET.get("technician", "")
        plate_filter = request.GET.get("plate", "").strip()

        if status_filter:
            qs = qs.filter(status=status_filter)
        if tech_filter == "unassigned":
            qs = qs.filter(assigned_technician__isnull=True)
        elif tech_filter:
            qs = qs.filter(assigned_technician__username=tech_filter)
        if plate_filter:
            qs = qs.filter(license_plate__icontains=plate_filter)

        # Only technicians belonging to this department
        tech_ids = UserProfile.objects.filter(
            role=UserProfile.Role.TECHNICIAN,
            department=department,
        ).values_list("user_id", flat=True)
        technicians = DjangoUser.objects.filter(id__in=tech_ids).order_by("username")

        return render(request, self.template_name, {
            "jobs": qs,
            "department": department,
            "department_display": dept_display,
            "total": Job.objects.filter(department=department).count(),
            "in_progress": Job.objects.filter(department=department, status=Job.Status.IN_PROGRESS).count(),
            "waiting_parts": Job.objects.filter(department=department, status=Job.Status.WAITING_PARTS).count(),
            "completed": Job.objects.filter(department=department, status=Job.Status.COMPLETED).count(),
            "status_choices": Job.Status.choices,
            "technicians": technicians,
            "current_status": status_filter,
            "current_tech": tech_filter,
            "current_plate": plate_filter,
        })


class DepartmentJobCreateView(OwnerRequiredMixin, View):
    """Intake a new repair job for a specific department."""

    template_name = "jobs/job_create.html"

    def get(self, request, department="electronic"):
        from .forms import JobCreateForm
        from .models import Department
        if department not in (Department.ELECTRONIC, Department.MECHANICAL):
            return redirect("owner_department_job_create", department=Department.ELECTRONIC)
        dept_display = "Electronic Repair" if department == Department.ELECTRONIC else "Mechanical Repair"
        return render(request, self.template_name, {
            "form": JobCreateForm(department=department),
            "department": department,
            "department_display": dept_display,
        })

    def post(self, request, department="electronic"):
        from .forms import JobCreateForm
        from .models import Department
        if department not in (Department.ELECTRONIC, Department.MECHANICAL):
            department = Department.ELECTRONIC
        form = JobCreateForm(request.POST, department=department)
        if form.is_valid():
            job = form.save(commit=False)
            job.department = department
            job.created_by = request.user
            job.save()
            if job.assigned_technician:
                messages.success(
                    request,
                    f"Job #{job.id} registered under {job.get_department_display()} and assigned to {job.assigned_technician.username}.",
                )
            else:
                messages.success(request, f"Job #{job.id} registered under {job.get_department_display()}.")
            return redirect("owner_job_detail", pk=job.pk)

        dept_display = "Electronic Repair" if department == Department.ELECTRONIC else "Mechanical Repair"
        return render(request, self.template_name, {
            "form": form,
            "department": department,
            "department_display": dept_display,
        })


class OwnerJobDetailView(OwnerRequiredMixin, View):
    """Job detail page: info, assign technician form, status history timeline."""

    template_name = "jobs/job_detail.html"

    def get(self, request, pk):
        from .forms import AssignTechnicianForm
        job = get_object_or_404(
            Job.objects.select_related("assigned_technician", "created_by")
            .prefetch_related("status_updates__technician"),
            pk=pk,
        )
        assign_form = AssignTechnicianForm(
            initial={"technician": job.assigned_technician},
            department=job.department,
        )
        return render(request, self.template_name, {
            "job": job,
            "assign_form": assign_form,
        })


class OwnerJobEditView(OwnerRequiredMixin, View):
    """Edit job fields (customer info, vehicle info, description, status)."""

    template_name = "jobs/job_edit.html"

    def get(self, request, pk):
        from .forms import JobEditForm
        job = get_object_or_404(Job, pk=pk)
        return render(request, self.template_name, {
            "form": JobEditForm(instance=job),
            "job": job,
        })

    def post(self, request, pk):
        from .forms import JobEditForm
        job = get_object_or_404(Job, pk=pk)
        form = JobEditForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, f"Job #{job.id} updated successfully.")
            return redirect("owner_job_detail", pk=job.pk)
        return render(request, self.template_name, {"form": form, "job": job})


class OwnerAssignTechnicianView(OwnerRequiredMixin, View):
    """POST-only: assign or unassign a technician to/from a job."""

    def post(self, request, pk):
        from .forms import AssignTechnicianForm
        job = get_object_or_404(Job, pk=pk)
        form = AssignTechnicianForm(request.POST, department=job.department)
        if form.is_valid():
            tech = form.cleaned_data["technician"]
            job.assigned_technician = tech
            job.save(update_fields=["assigned_technician", "updated_at"])
            name = tech.username if tech else "None"
            messages.success(request, f"Technician updated to: {name}.")
        else:
            err_msg = form.errors.get("technician", ["Invalid technician selection."])[0]
            messages.error(request, err_msg)
        return redirect("owner_job_detail", pk=job.pk)


# ---------------------------------------------------------------------------
# Technician Frontend Views (Strict Department Isolation)
# ---------------------------------------------------------------------------

class TechJobDetailView(TechnicianRequiredMixin, View):
    """Job detail page for assigned technician: view details + post status updates."""

    template_name = "jobs/tech_job_detail.html"

    def get(self, request, pk):
        from .forms import StatusUpdateForm
        dept = request.user.profile.department
        qs = Job.objects.filter(assigned_technician=request.user)
        if dept:
            qs = qs.filter(department=dept)
        job = get_object_or_404(
            qs.select_related("assigned_technician", "created_by")
            .prefetch_related("status_updates__technician"),
            pk=pk,
        )
        form = StatusUpdateForm(initial={"status": job.status})
        return render(request, self.template_name, {
            "job": job,
            "form": form,
        })


class TechPostStatusUpdateView(TechnicianRequiredMixin, View):
    """POST-only: Technician posts a new status update and syncs parent Job.status."""

    def post(self, request, pk):
        from .forms import StatusUpdateForm
        from .models import StatusUpdate
        dept = request.user.profile.department
        qs = Job.objects.filter(assigned_technician=request.user)
        if dept:
            qs = qs.filter(department=dept)
        job = get_object_or_404(qs, pk=pk)
        form = StatusUpdateForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data["status"]
            note = form.cleaned_data.get("note", "")

            StatusUpdate.objects.create(
                job=job,
                status=new_status,
                note=note,
                technician=request.user,
            )

            job.status = new_status
            job.save(update_fields=["status", "updated_at"])

            messages.success(request, f"Status updated to {job.get_status_display()}.")
            return redirect("tech_job_detail", pk=job.pk)

        return render(request, "jobs/tech_job_detail.html", {
            "job": job,
            "form": form,
        })


# ---------------------------------------------------------------------------
# Owner Settings & Technician Management Views
# ---------------------------------------------------------------------------

class OwnerSettingsView(OwnerRequiredMixin, View):
    """Owner Settings Dashboard: Profile settings & Technician Roster."""

    template_name = "jobs/owner_settings.html"

    def get(self, request):
        from django.contrib.auth.models import User as DjangoUser
        from django.db.models import Count
        from .forms import OwnerProfileForm

        profile_form = OwnerProfileForm(initial={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "email": request.user.email,
            "phone_number": getattr(request.user.profile, "phone_number", ""),
        })
        password_form = PasswordChangeForm(request.user)

        technicians = (
            DjangoUser.objects.filter(profile__role=UserProfile.Role.TECHNICIAN)
            .select_related("profile")
            .annotate(active_jobs_count=Count("assigned_jobs"))
            .order_by("profile__department", "username")
        )

        return render(request, self.template_name, {
            "profile_form": profile_form,
            "password_form": password_form,
            "technicians": technicians,
        })

    def post(self, request):
        from .forms import OwnerProfileForm

        form = OwnerProfileForm(request.POST)
        if form.is_valid():
            request.user.first_name = form.cleaned_data["first_name"]
            request.user.last_name = form.cleaned_data["last_name"]
            request.user.email = form.cleaned_data["email"]
            request.user.save()

            profile = request.user.profile
            profile.phone_number = form.cleaned_data["phone_number"]
            profile.save()

            messages.success(request, "Owner profile details updated successfully.")
            return redirect("owner_settings")

        return render(request, self.template_name, {
            "profile_form": form,
            "password_form": PasswordChangeForm(request.user),
        })


class OwnerTechniciansView(OwnerRequiredMixin, View):
    """
    Dedicated owner section to view, add, edit, and remove workshop technicians.
    """

    template_name = "jobs/owner_technicians.html"

    def get(self, request):
        from django.contrib.auth.models import User as DjangoUser
        from django.db.models import Count

        base_qs = (
            DjangoUser.objects.filter(profile__role=UserProfile.Role.TECHNICIAN)
            .select_related("profile")
            .annotate(active_jobs_count=Count("assigned_jobs"))
            .order_by("username")
        )

        electronic_techs = base_qs.filter(profile__department=Department.ELECTRONIC)
        mechanical_techs = base_qs.filter(profile__department=Department.MECHANICAL)

        elec_count = electronic_techs.count()
        mech_count = mechanical_techs.count()

        return render(request, self.template_name, {
            "electronic_techs": electronic_techs,
            "mechanical_techs": mechanical_techs,
            "total_techs": elec_count + mech_count,
            "elec_count": elec_count,
            "mech_count": mech_count,
        })


class OwnerPasswordChangeView(OwnerRequiredMixin, View):
    """POST-only: Update owner password securely."""

    def post(self, request):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been changed successfully.")
            return redirect("owner_settings")

        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.capitalize()}: {error}")
        return redirect("owner_settings")


class OwnerAddTechnicianView(OwnerRequiredMixin, View):
    """Onboard a new technician into Electronic or Mechanical department."""

    template_name = "jobs/technician_add.html"

    def get(self, request):
        from .forms import TechnicianCreateForm
        return render(request, self.template_name, {
            "form": TechnicianCreateForm(),
        })

    def post(self, request):
        from django.contrib.auth.models import User as DjangoUser
        from .forms import TechnicianCreateForm

        form = TechnicianCreateForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            email = form.cleaned_data.get("email", "")
            phone = form.cleaned_data.get("phone_number", "")
            department = form.cleaned_data["department"]
            password = form.cleaned_data["password"]

            user = DjangoUser.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            user.profile.role = UserProfile.Role.TECHNICIAN
            user.profile.department = department
            user.profile.phone_number = phone
            user.profile.save()

            messages.success(
                request,
                f"Technician '{user.username}' successfully registered to {user.profile.get_department_display()}.",
            )
            return redirect("owner_technicians")

        return render(request, self.template_name, {"form": form})


class OwnerDeleteTechnicianView(OwnerRequiredMixin, View):
    """POST-only: Remove a technician and safely unassign their jobs."""

    def post(self, request, pk):
        from django.contrib.auth.models import User as DjangoUser
        tech = get_object_or_404(
            DjangoUser.objects.filter(profile__role=UserProfile.Role.TECHNICIAN),
            pk=pk,
        )
        tech_name = tech.username
        # Safely unassign active jobs
        Job.objects.filter(assigned_technician=tech).update(assigned_technician=None)
        tech.delete()
        messages.success(request, f"Technician '{tech_name}' removed and active jobs unassigned.")
        return redirect("owner_technicians")


class OwnerEditTechnicianView(OwnerRequiredMixin, View):
    """Edit an existing technician's details and department assignment."""

    template_name = "jobs/technician_edit.html"

    def get(self, request, pk):
        from django.contrib.auth.models import User as DjangoUser
        from .forms import TechnicianEditForm

        tech = get_object_or_404(
            DjangoUser.objects.filter(profile__role=UserProfile.Role.TECHNICIAN),
            pk=pk,
        )
        form = TechnicianEditForm(initial={
            "first_name": tech.first_name,
            "last_name": tech.last_name,
            "email": tech.email,
            "phone_number": getattr(tech.profile, "phone_number", ""),
            "department": tech.profile.department,
        })
        active_jobs_count = tech.assigned_jobs.count()
        return render(request, self.template_name, {
            "tech": tech,
            "form": form,
            "active_jobs_count": active_jobs_count,
        })

    def post(self, request, pk):
        from django.contrib.auth.models import User as DjangoUser
        from .forms import TechnicianEditForm

        tech = get_object_or_404(
            DjangoUser.objects.filter(profile__role=UserProfile.Role.TECHNICIAN),
            pk=pk,
        )
        form = TechnicianEditForm(request.POST)
        if form.is_valid():
            tech.first_name = form.cleaned_data["first_name"]
            tech.last_name = form.cleaned_data["last_name"]
            tech.email = form.cleaned_data["email"]
            tech.save()

            old_dept = tech.profile.department
            new_dept = form.cleaned_data["department"]
            unassigned_count = 0

            if old_dept != new_dept:
                # If changing departments, unassign active jobs from previous department to prevent overlap
                unassigned_count = Job.objects.filter(assigned_technician=tech).update(assigned_technician=None)
                tech.profile.department = new_dept

            tech.profile.phone_number = form.cleaned_data["phone_number"]
            tech.profile.save()

            if old_dept != new_dept:
                msg = f"Technician '{tech.username}' transferred to {tech.profile.get_department_display()}."
                if unassigned_count > 0:
                    msg += f" {unassigned_count} active job(s) from former department were unassigned."
                messages.success(request, msg)
            else:
                messages.success(request, f"Technician '{tech.username}' details updated successfully.")

            return redirect("owner_technicians")


        active_jobs_count = tech.assigned_jobs.count()
        return render(request, self.template_name, {
            "tech": tech,
            "form": form,
            "active_jobs_count": active_jobs_count,
        })


# ---------------------------------------------------------------------------
# Technician Self-Service Settings Views
# ---------------------------------------------------------------------------

class TechnicianSettingsView(TechnicianRequiredMixin, View):
    """Technician Settings: Update username, email, phone number."""

    template_name = "jobs/tech_settings.html"

    def get(self, request):
        from .forms import TechnicianProfileForm

        profile_form = TechnicianProfileForm(
            current_user=request.user,
            initial={
                "username": request.user.username,
                "email": request.user.email,
                "phone_number": getattr(request.user.profile, "phone_number", ""),
            },
        )
        password_form = PasswordChangeForm(request.user)

        return render(request, self.template_name, {
            "profile_form": profile_form,
            "password_form": password_form,
        })

    def post(self, request):
        from .forms import TechnicianProfileForm

        form = TechnicianProfileForm(request.POST, current_user=request.user)
        if form.is_valid():
            request.user.username = form.cleaned_data["username"]
            request.user.email = form.cleaned_data["email"]
            request.user.save()

            profile = request.user.profile
            profile.phone_number = form.cleaned_data["phone_number"]
            profile.save()

            messages.success(request, "Your profile details have been updated successfully.")
            return redirect("tech_settings")

        password_form = PasswordChangeForm(request.user)
        return render(request, self.template_name, {
            "profile_form": form,
            "password_form": password_form,
        })


class TechnicianPasswordChangeView(TechnicianRequiredMixin, View):
    """POST-only: Update technician password securely."""

    def post(self, request):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been changed successfully.")
            return redirect("tech_settings")

        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.capitalize()}: {error}")
        return redirect("tech_settings")











