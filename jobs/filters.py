import django_filters
from .models import Job


class JobFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Job.Status.choices)
    license_plate = django_filters.CharFilter(lookup_expr="icontains")
    vehicle_make = django_filters.CharFilter(lookup_expr="icontains")
    vehicle_model = django_filters.CharFilter(lookup_expr="icontains")
    assigned_technician = django_filters.NumberFilter(field_name="assigned_technician__id")
    assigned_technician_username = django_filters.CharFilter(
        field_name="assigned_technician__username", lookup_expr="iexact"
    )

    class Meta:
        model = Job
        fields = [
            "status",
            "license_plate",
            "vehicle_make",
            "vehicle_model",
            "assigned_technician",
            "assigned_technician_username",
        ]
