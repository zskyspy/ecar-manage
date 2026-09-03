from django.http import HttpResponse, JsonResponse
from django.db import connection


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1;")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "app": "GarageFlow", "database": "connected"})


def home(request):
    return HttpResponse("GarageFlow is running.")
