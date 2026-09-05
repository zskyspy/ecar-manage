"""
Notification & Web Push Service for ECAR Space.
Handles real-time alerts for technician assignments and job completions.
"""
import json
import logging
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import User
from .models import Notification, PushSubscription

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
VAPID_PRIVATE_KEY_PATH = str(BASE_DIR / "vapid_private.pem")
VAPID_PUBLIC_KEY_PATH = BASE_DIR / "vapid_public_key.txt"
VAPID_CLAIMS = {
    "sub": "mailto:admin@ecarspace.local"
}


def get_vapid_public_key() -> str:
    """Return the raw base64url-encoded VAPID public key for frontend subscription."""
    if VAPID_PUBLIC_KEY_PATH.exists():
        return VAPID_PUBLIC_KEY_PATH.read_text().strip()
    return ""


def send_push_notification(user, title: str, body: str, target_url: str = "/"):
    """
    1. Create a persistent Notification record in database.
    2. Attempt to send Web Push packets to all registered browser endpoints for this user.
    """
    # 1. Database record
    notif = Notification.objects.create(
        recipient=user,
        title=title,
        body=body,
        target_url=target_url,
    )

    # 2. Web Push dispatch
    subscriptions = PushSubscription.objects.filter(user=user)
    if not subscriptions.exists():
        return notif

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": target_url,
        "id": notif.id,
    })

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush is not installed; push delivery skipped.")
        return notif

    for sub in list(subscriptions):
        sub_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth,
            },
        }
        try:
            webpush(
                subscription_info=sub_info,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY_PATH,
                vapid_claims=VAPID_CLAIMS,
                ttl=86400,
            )
        except WebPushException as ex:
            logger.warning(f"WebPush failed for user {user.username}: {ex}")
            # If endpoint is invalid or expired (404/410), delete subscription
            if ex.response and ex.response.status_code in (404, 410):
                sub.delete()
        except Exception as ex:
            logger.error(f"Unexpected push error: {ex}")

    return notif


def notify_technician_assignment(job, technician):
    """Notify assigned technician when a car is assigned to their bay."""
    if not technician:
        return None

    title = f"🚗 Car Assigned to Your Bay"
    body = (
        f"Job #{job.id}: {job.vehicle_make} {job.vehicle_model} "
        f"({job.license_plate}) has been assigned to you."
    )
    target_url = f"/tech/jobs/{job.id}/"
    return send_push_notification(technician, title, body, target_url)


def notify_owner_job_completed(job, technician=None):
    """Notify all shop owners when a repair job is marked as completed."""
    owners = User.objects.filter(profile__role="owner")
    tech_name = technician.username if technician else "Technician"
    title = f"✅ Job #{job.id} Completed!"
    body = (
        f"{job.vehicle_make} {job.vehicle_model} ({job.license_plate}) "
        f"in {job.get_department_display()} has been marked completed by {tech_name}."
    )
    target_url = f"/owner/jobs/{job.id}/"

    notifications = []
    for owner in owners:
        notif = send_push_notification(owner, title, body, target_url)
        notifications.append(notif)
    return notifications
