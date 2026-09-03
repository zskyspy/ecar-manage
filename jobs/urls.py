from django.contrib.auth import views as auth_views
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register(r"jobs", views.JobViewSet, basename="job")

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),

    # ---- Frontend Auth ----
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # ---- Frontend Dashboards ----
    path("dashboard/", views.DashboardRedirectView.as_view(), name="dashboard"),
    path("owner/", views.OwnerDashboardView.as_view(), name="owner_dashboard"),
    path("tech/", views.TechnicianDashboardView.as_view(), name="tech_dashboard"),

    # ---- Owner Two-Department Portals ----
    path("owner/jobs/", views.OwnerDashboardView.as_view(), name="owner_job_list"),
    path("owner/<str:department>/", views.DepartmentJobListView.as_view(), name="owner_department_jobs"),
    path("owner/<str:department>/create/", views.DepartmentJobCreateView.as_view(), name="owner_department_job_create"),
    path("owner/jobs/<int:pk>/", views.OwnerJobDetailView.as_view(), name="owner_job_detail"),
    path("owner/jobs/<int:pk>/edit/", views.OwnerJobEditView.as_view(), name="owner_job_edit"),
    path("owner/jobs/<int:pk>/assign/", views.OwnerAssignTechnicianView.as_view(), name="owner_job_assign"),

    # ---- Technician Bay Management (Step 12) ----
    path("tech/jobs/<int:pk>/", views.TechJobDetailView.as_view(), name="tech_job_detail"),
    path("tech/jobs/<int:pk>/update/", views.TechPostStatusUpdateView.as_view(), name="tech_job_status_update"),


    # ---- Core Job CRUD API ----
    path("api/", include(router.urls)),

    # ---- Auth API endpoints ----
    path("api/token/", views.CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/me/", views.CurrentUserView.as_view(), name="current_user"),
    path("api/auth/test-owner/", views.OwnerOnlyTestView.as_view(), name="test_owner_role"),
    path("api/auth/test-technician/", views.TechnicianOnlyTestView.as_view(), name="test_technician_role"),
]



