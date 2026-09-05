/**
 * ECAR Space - Universal Push & Notification Client
 * Supports standard Web Push (Chrome, Firefox, Edge, Safari)
 * AND provides seamless fallback for Huawei Browser & HMS devices.
 */

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

function getCsrfToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    return cookieValue || '';
}

// Gentle audio alert chime for workshops using Web Audio API (zero external files)
function playWorkshopAlertChime() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.type = 'sine';
        osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
        osc.frequency.setValueAtTime(880, ctx.currentTime + 0.12); // A5

        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);

        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.35);
    } catch (e) {
        // AudioContext may require user interaction first
    }
}

async function enablePushNotifications() {
    // 1. Check if browser supports Notification API
    if ('Notification' in window) {
        try {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                updatePushUIStatus(false, 'Permission Denied');
                return false;
            }
        } catch (e) {
            console.warn('Notification permission request error:', e);
        }
    }

    let webPushRegistered = false;

    // 2. If PushManager is supported (Standard Android/iOS/Desktop)
    if ('serviceWorker' in navigator && 'PushManager' in window) {
        try {
            const registration = await navigator.serviceWorker.register('/serviceworker.js');
            await navigator.serviceWorker.ready;

            const keyRes = await fetch('/api/notifications/vapid-key/');
            if (keyRes.ok) {
                const keyData = await keyRes.json();
                const vapidPublicKey = keyData.public_key;

                if (vapidPublicKey) {
                    let subscription = await registration.pushManager.getSubscription();
                    if (!subscription) {
                        subscription = await registration.pushManager.subscribe({
                            userVisibleOnly: true,
                            applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
                        });
                    }

                    if (subscription) {
                        const subJson = subscription.toJSON();
                        await fetch('/api/notifications/subscribe/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': getCsrfToken()
                            },
                            body: JSON.stringify({
                                endpoint: subJson.endpoint,
                                keys: subJson.keys
                            })
                        });
                        webPushRegistered = true;
                    }
                }
            }
        } catch (err) {
            console.warn('PushManager registration failed (fallback to real-time alerts):', err);
        }
    }

    // Mark active in localStorage so Huawei/other browsers remember it's enabled
    localStorage.setItem('ecar_notifications_enabled', 'true');

    // 3. Update UI & dismiss modal
    if (webPushRegistered) {
        updatePushUIStatus(true, 'Active & Listening');
    } else {
        // Huawei Browser or browser without Google Play Services PushManager
        updatePushUIStatus(true, 'Active (In-App & Alerts)');
    }

    const modalEl = document.getElementById('pushPromptModal');
    if (modalEl) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
    }

    // Play confirmation chime
    playWorkshopAlertChime();
    return true;
}

async function testPushNotification() {
    try {
        const res = await fetch('/api/notifications/test/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            }
        });
        if (res.ok) {
            playWorkshopAlertChime();
            const btn = document.getElementById('btnTestPush');
            if (btn) {
                const original = btn.innerHTML;
                btn.innerHTML = '<i class="bi bi-check-circle me-1"></i> Sent!';
                setTimeout(() => { btn.innerHTML = original; }, 2500);
            }
            // Trigger local poll immediately to show notification
            setTimeout(pollUnreadNotifications, 500);
        }
    } catch (e) {
        console.error('Test push error:', e);
    }
}

function updatePushUIStatus(enabled, text) {
    const badge = document.getElementById('pushStatusBadge');
    const toggleBtn = document.getElementById('btnTogglePush');
    const testBtn = document.getElementById('btnTestPush');

    if (badge) {
        if (enabled) {
            badge.className = 'badge bg-success-subtle text-success border border-success-subtle px-2 py-1';
            badge.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> ' + (text || 'Active & Listening');
        } else {
            badge.className = 'badge bg-secondary-subtle text-secondary border px-2 py-1';
            badge.innerHTML = '<i class="bi bi-bell-slash me-1"></i> ' + (text || 'Disabled');
        }
    }

    if (toggleBtn) {
        if (enabled) {
            toggleBtn.className = 'btn btn-outline-secondary btn-sm';
            toggleBtn.innerHTML = '<i class="bi bi-bell-fill text-success me-1"></i> Notifications Enabled';
            toggleBtn.disabled = true;
        } else {
            toggleBtn.className = 'btn btn-ecar-primary btn-sm';
            toggleBtn.innerHTML = '<i class="bi bi-bell me-1"></i> Enable Push Notifications';
            toggleBtn.disabled = false;
        }
    }

    if (testBtn) {
        testBtn.style.display = enabled ? 'inline-flex' : 'none';
    }
}

// Display in-app floating banner on mobile screen if OS notification fails or on Huawei Browser
function showInAppAlertBanner(title, body, url) {
    playWorkshopAlertChime();
    let banner = document.getElementById('ecar-inapp-alert');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'ecar-inapp-alert';
        banner.style.cssText = `
            position: fixed;
            top: 16px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 99999;
            width: calc(100% - 32px);
            max-width: 420px;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-left: 4px solid #0284c7;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            padding: 12px 16px;
            cursor: pointer;
            transition: all 0.3s ease;
        `;
        document.body.appendChild(banner);
    }

    banner.innerHTML = `
        <div class="d-flex align-items-start justify-content-between gap-2">
            <div>
                <div class="fw-bold small text-dark mb-1"><i class="bi bi-bell-fill text-primary me-1"></i>${title}</div>
                <div class="text-secondary" style="font-size: 0.8rem;">${body}</div>
            </div>
            <button type="button" class="btn-close" style="font-size: 0.7rem;" onclick="event.stopPropagation(); this.closest('#ecar-inapp-alert').style.display='none';"></button>
        </div>
    `;
    banner.style.display = 'block';
    banner.onclick = function() {
        if (url) window.location.href = url;
    };

    setTimeout(() => {
        if (banner) banner.style.display = 'none';
    }, 7000);
}

// Real-Time Poller: Runs every 10s on active tabs (works 100% on Huawei Browser, iOS, Android, Desktop)
async function pollUnreadNotifications() {
    try {
        const res = await fetch('/api/notifications/unread/');
        if (res.ok) {
            const data = await res.json();
            if (data.notifications && data.notifications.length > 0) {
                data.notifications.forEach(notif => {
                    // Try native OS notification first
                    let shown = false;
                    if ('Notification' in window && Notification.permission === 'granted') {
                        try {
                            const n = new Notification(notif.title, {
                                body: notif.body,
                                icon: '/static/img/logo.jpg',
                                data: { url: notif.url }
                            });
                            n.onclick = function() {
                                window.location.href = notif.url;
                            };
                            shown = true;
                            playWorkshopAlertChime();
                        } catch (e) {
                            shown = false;
                        }
                    }

                    // Fallback to in-app banner (crucial for Huawei Browser or restricted webviews)
                    if (!shown) {
                        showInAppAlertBanner(notif.title, notif.body, notif.url);
                    }
                });
            }
        }
    } catch (e) {
        // Silently pass
    }
}

// ─── Notification Init (runs on page load AND after HTMX swaps) ───────────────
let _ecarPollInterval = null;

function initEcarNotifications() {
    const isRemembered = localStorage.getItem('ecar_notifications_enabled') === 'true';
    const isGranted = ('Notification' in window && Notification.permission === 'granted');

    if (isGranted || isRemembered) {
        updatePushUIStatus(true, 'Active & Listening');
    } else {
        updatePushUIStatus(false, 'Disabled');
        // Show sign-in prompt modal after brief delay
        setTimeout(function() {
            const modalEl = document.getElementById('pushPromptModal');
            if (modalEl) {
                // Dismiss any existing instance first to avoid duplicates
                let existing = bootstrap.Modal.getInstance(modalEl);
                if (existing) existing.dispose();
                const modal = new bootstrap.Modal(modalEl);
                modal.show();
            }
        }, 1200);
    }

    // Start polling only once — guard against HTMX firing multiple swaps
    if (!_ecarPollInterval) {
        _ecarPollInterval = setInterval(pollUnreadNotifications, 10000);
    }
}

// Fire on hard page load
document.addEventListener('DOMContentLoaded', initEcarNotifications);

// Fire after HTMX swaps (covers login redirect where DOMContentLoaded already fired)
document.addEventListener('htmx:load', function(evt) {
    // Only re-init if the push modal is now present in the swapped content
    if (document.getElementById('pushPromptModal')) {
        initEcarNotifications();
    }
});
