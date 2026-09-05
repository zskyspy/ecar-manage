# ECAR Manage - Workshop Management System

A web-based workshop management application built for automotive repair shops, specifically designed to handle separate workflows for electronic diagnostics/repairs and mechanical jobs. 

The goal of this project was to replace messy paperwork and disconnected chat messages with a centralized system where owners can track revenue and job intake, while technicians get a dedicated, distraction-free board for their assigned work.

---

## What It Does

- **Department Isolation**: Distinct workflows for Electronic Repair (`// Elect`) and Mechanical Repair (`// Mech`). Technicians in one department only see what is relevant to their bay.
- **Owner Dashboard**: Live overview of workshop activity, active repairs, revenue stats, technician assignment, and job creation.
- **Technician Bay View**: Clean view for technicians to track assigned vehicles, update repair progress (Pending, In Progress, Waiting for Parts, Completed), and add notes.
- **Fast Navigation & Search**: Uses HTMX for instant vehicle/customer search, tab filtering, and page transitions without full browser reloads.
- **Mobile Friendly**: Designed to be used on phones and tablets in the shop, with a bottom navigation bar, tap-to-call buttons for customer numbers, and touch-optimized controls.
- **Self-Hosted & Production Ready**: Set up to run locally on the workshop network via multi-threaded Waitress and WhiteNoise, with Cloudflare tunnel scripts for secure remote access on phones outside the shop.

---

## Tech Stack

- **Backend**: Python, Django, Django REST Framework
- **Frontend**: Bootstrap 5, HTMX, Bootstrap Icons
- **Database**: PostgreSQL (can also run on SQLite for local testing)
- **Web Server**: Waitress (WSGI), WhiteNoise
- **Remote Access**: Cloudflare Tunnel (`cloudflared`)

---

## Project Layout

```text
ECAR Space/
├── garageapp/               # Django project settings and WSGI configuration
├── jobs/                    # Core workshop app (models, views, forms, API)
│   ├── migrations/          # Database migrations
│   ├── models.py            # Job, Profile, StatusUpdate, Department models
│   ├── views.py             # Owner and technician views, HTMX endpoints
│   └── urls.py              # URL routing
├── static/                  # CSS, icons, images, and client scripts
├── templates/               # HTML templates (base layout, job views, settings)
├── start_dev_offline.bat    # Quick local dev server launcher
├── start_live_server.bat    # Production Waitress launcher (8 threads)
├── start_online_tunnel.bat  # Cloudflare tunnel launcher for remote phone access
├── requirements.txt         # Dependencies
└── manage.py
```

---

## Setup & Local Installation

### 1. Clone the repo
```bash
git clone https://github.com/zskyspy/ecar-manage.git
cd ecar-manage
```

### 2. Create and activate a virtual environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install packages
```bash
pip install -r requirements.txt
pip install waitress whitenoise pywebpush
```

### 4. Configure environment variables
Create a `.env` file in the project root:
```env
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,*.trycloudflare.com,*
CSRF_TRUSTED_ORIGINS=https://*.trycloudflare.com,http://localhost:8000

# Database
DB_NAME=garageflow
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### 5. Apply migrations and create an admin
```bash
python manage.py migrate
python manage.py createsuperuser
```

---

## How to Run

### Live Server Mode (Fast multi-threaded server)
Double click `start_live_server.bat` or run:
```bash
python manage.py collectstatic --noinput
.\venv\Scripts\waitress-serve.exe --host=0.0.0.0 --port=8000 --threads=8 garageapp.wsgi:application
```
Then open `http://localhost:8000` or use your computer's local network IP on your phone.

### Standard Dev Mode
Double click `start_dev_offline.bat` or run:
```bash
python manage.py runserver 0.0.0.0:8000
```

### Remote Access (Cloudflare Tunnel)
Double click `start_online_tunnel.bat` to expose the local server over a secure HTTPS link, so you can open the app on your phone even when outside the shop Wi-Fi.

---

## User Roles

- **Owner**: Full access across both departments, revenue numbers, job assignments, and settings.
- **Electronics Technician**: Only sees electronic diagnostic and repair jobs assigned to them.
- **Mechanical Technician**: Only sees mechanical and maintenance jobs assigned to them.
