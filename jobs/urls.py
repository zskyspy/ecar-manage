from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register(r"jobs", views.JobViewSet, basename="job")

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    # Core Job CRUD API
    path("api/", include(router.urls)),
    # Auth endpoints
    path("api/token/", views.CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/me/", views.CurrentUserView.as_view(), name="current_user"),
    path("api/auth/test-owner/", views.OwnerOnlyTestView.as_view(), name="test_owner_role"),
    path("api/auth/test-technician/", views.TechnicianOnlyTestView.as_view(), name="test_technician_role"),
]


