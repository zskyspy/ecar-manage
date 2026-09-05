# 🚗 ECAR Space — Workshop Management System

> High-performance automotive workshop management system engineered for **Electronic Repair** and **Mechanical Repair** facilities. Features role-based workflows, live job boards, real-time HTMX filtering, production-grade serving, and mobile-first responsive interfaces.

---

## ✨ Features

- 🏢 **Multi-Department Separation**: Complete isolation between **Electronic Repair** (`// Elect`) and **Mechanical Repair** (`// Mech`) workflows.
- 👥 **Role-Based Access Control**:
  - **Owner / Manager Dashboard**: Full workshop overview, revenue tracking, status updates, technician assignment, job intake, and staff management.
  - **Technician Bay**: Streamlined interface for technicians to view assigned vehicles, log diagnostic work, update repair statuses, and add notes.
- ⚡ **Seamless SPA-Style UX**: Powered by **HTMX** for instant search, live status filtering, and smooth navigation without full-page reloads.
- 📱 **Mobile & Tablet Optimized**:
  - Bottom navigation bar tailored for mobile screens.
  - Tap-to-call client phone shortcuts.
  - Auto-dismissing drawer navigation and touch-optimized touch targets.
- 🚀 **High-Performance Production Stack**:
  - **Waitress WSGI Server**: Multi-threaded request handling (8 threads).
  - **WhiteNoise**: Automated static asset compression and caching.
  - **PostgreSQL**: Robust relational database storage.
- 🌐 **Remote Access & Cloudflare Tunneling**: Zero-config SSL tunnels allowing workshop owners and technicians to access the application securely on mobile devices from anywhere.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12+, Django 5+, Django REST Framework
- **Frontend**: Bootstrap 5, Bootstrap Icons, HTMX, JetBrains Mono & Inter typography
- **Database**: PostgreSQL (or SQLite for quick local development)
- **Web Server**: Waitress (Production WSGI) + WhiteNoise
- **Tunneling / Networking**: Cloudflare Tunnel (`cloudflared`)

---

## 📂 Project Structure

```text
ECAR Space/
├── garageapp/               # Django core project configuration & settings
├── jobs/                    # Workshop jobs, departments, and user profiles
│   ├── migrations/          # Database migrations
│   ├── models.py            # Job, Profile, StatusUpdate, Department models
│   ├── views.py             # Owner & Technician views, HTMX partials & APIs
│   ├── services.py          # Notification & event dispatch services
│   └── urls.py              # Application routing
├── static/
│   ├── css/ecarspace.css    # Custom dark/light styling & mobile layout rules
│   ├── js/                  # Real-time and push notification scripts
│   └── img/                 # Workshop branding & logo assets
├── templates/               # Django HTML templates (Boosted with HTMX)
│   ├── jobs/                # Job boards, detail views, and settings
│   └── base.html            # Main application layout & responsive navigation
├── start_dev_offline.bat    # Quick offline dev launcher
├── start_live_server.bat    # Fast multi-threaded Waitress production launcher
├── start_online_tunnel.bat  # Cloudflare HTTPS tunnel launcher
├── requirements.txt         # Python package dependencies
└── manage.py                # Django CLI entrypoint
```

---

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.11+**
- **PostgreSQL** (or SQLite)
- **Git**

### 2. Clone the Repository

```bash
git clone https://github.com/zskyspy/ecar-manage.git
cd ecar-manage
```

### 3. Setup Virtual Environment

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
pip install waitress whitenoise pywebpush
```

### 5. Environment Variables

Create a `.env` file in the root directory (based on the sample below):

```env
DEBUG=True
SECRET_KEY=your-secure-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,*.trycloudflare.com,*
CSRF_TRUSTED_ORIGINS=https://*.trycloudflare.com,http://localhost:8000

# PostgreSQL Configuration
DB_NAME=garageflow
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432
```

### 6. Database Setup & Migrations

```bash
python manage.py migrate
python manage.py createsuperuser
```

---

## 🏃 Running the Application

### Option A: Fast Production Mode (Recommended)
Double-click `start_live_server.bat` or run:
```bash
python manage.py collectstatic --noinput
.\venv\Scripts\waitress-serve.exe --host=0.0.0.0 --port=8000 --threads=8 garageapp.wsgi:application
```
Access the application at `http://localhost:8000` (or `http://<YOUR_LOCAL_IP>:8000` on your workshop Wi-Fi network).

### Option B: Standard Development Mode
Double-click `start_dev_offline.bat` or run:
```bash
python manage.py runserver 0.0.0.0:8000
```

### Option C: Remote Online Access (Cloudflare Tunnel)
Double-click `start_online_tunnel.bat` to spin up a secure, public HTTPS URL accessible on any mobile device worldwide without opening router ports.

---

## 🔒 User Roles & Workflow

| Role | Access Level | Key Capabilities |
| :--- | :--- | :--- |
| **Workshop Owner** | Full Management | View workshop revenue, assign technicians, inspect jobs across departments, manage settings. |
| **Technician (Electronics)** | Department Scoped | Access assigned ECU/electronics repair jobs, log real-time progress, submit diagnostic updates. |
| **Technician (Mechanical)** | Department Scoped | Access assigned engine/mechanical overhaul jobs, update job lifecycle. |

---

## 📄 License

This project is proprietary and maintained for **ECAR Space Workshop Systems**. All rights reserved.
