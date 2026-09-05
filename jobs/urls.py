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

    # ---- Owner Settings (Profile & Password) ----
    path("owner/settings/", views.OwnerSettingsView.as_view(), name="owner_settings"),
    path("owner/settings/password/", views.OwnerPasswordChangeView.as_view(), name="owner_password_change"),

    # ---- Owner Technician Management (Sidebar Section) ----
    path("owner/technicians/", views.OwnerTechniciansView.as_view(), name="owner_technicians"),
    path("owner/technicians/add/", views.OwnerAddTechnicianView.as_view(), name="owner_technician_add"),
    path("owner/technicians/<int:pk>/edit/", views.OwnerEditTechnicianView.as_view(), name="owner_technician_edit"),
    path("owner/technicians/<int:pk>/delete/", views.OwnerDeleteTechnicianView.as_view(), name="owner_technician_delete"),

    # Aliases for backwards compatibility
    path("owner/settings/technicians/add/", views.OwnerAddTechnicianView.as_view()),
    path("owner/settings/technicians/<int:pk>/edit/", views.OwnerEditTechnicianView.as_view()),
    path("owner/settings/technicians/<int:pk>/delete/", views.OwnerDeleteTechnicianView.as_view()),

    # ---- Owner Job Details & Actions ----
    path("owner/jobs/", views.OwnerDashboardView.as_view(), name="owner_job_list"),
    path("owner/jobs/<int:pk>/", views.OwnerJobDetailView.as_view(), name="owner_job_detail"),
    path("owner/jobs/<int:pk>/edit/", views.OwnerJobEditView.as_view(), name="owner_job_edit"),
    path("owner/jobs/<int:pk>/assign/", views.OwnerAssignTechnicianView.as_view(), name="owner_job_assign"),

    # ---- Owner Two-Department Portals ----
    path("owner/<str:department>/", views.DepartmentJobListView.as_view(), name="owner_department_jobs"),
    path("owner/<str:department>/create/", views.DepartmentJobCreateView.as_view(), name="owner_department_job_create"),

    # ---- Technician Bay Management (Step 12) ----
    path("tech/jobs/<int:pk>/", views.TechJobDetailView.as_view(), name="tech_job_detail"),
    path("tech/jobs/<int:pk>/update/", views.TechPostStatusUpdateView.as_view(), name="tech_job_status_update"),

    # ---- Technician Settings ----
    path("tech/settings/", views.TechnicianSettingsView.as_view(), name="tech_settings"),
    path("tech/settings/password/", views.TechnicianPasswordChangeView.as_view(), name="tech_password_change"),

    # ---- Core Job CRUD API ----
    path("api/", include(router.urls)),

    # ---- Auth API endpoints ----
    path("api/token/", views.CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/me/", views.CurrentUserView.as_view(), name="current_user"),
    path("api/auth/test-owner/", views.OwnerOnlyTestView.as_view(), name="test_owner_role"),
    # ---- Push Notification Endpoints ----
    path("serviceworker.js", views.TemplateView.as_view(template_name="serviceworker.js", content_type="application/javascript"), name="serviceworker"),
    path("api/notifications/vapid-key/", views.VapidPublicKeyView.as_view(), name="vapid_public_key"),
    path("api/notifications/subscribe/", views.PushSubscribeView.as_view(), name="push_subscribe"),
    path("api/notifications/status/", views.PushStatusView.as_view(), name="push_status"),
    path("api/notifications/test/", views.PushTestNotificationView.as_view(), name="push_test"),
    path("api/notifications/unread/", views.UnreadNotificationsView.as_view(), name="unread_notifications"),
]



