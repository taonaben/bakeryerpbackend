
# Bakery ERP — Backend (Django + PostgreSQL + Docker)

This repository contains the backend for the **Bakery ERP project**, built with **Django** and **PostgreSQL**, and fully containerized using **Docker**.

Each developer runs their **own isolated backend and database instance** locally.  
The database schema is shared via migrations; **data is not shared via Git**.

---

## Tech Stack

- Python 3.11
- Django 4.x
- PostgreSQL 15
- Docker & Docker Compose

---

## Prerequisites

Make sure you have the following installed:

- Docker
- Docker Compose

Verify:
```bash
docker --version
docker compose version
````

If these commands fail, fix that before continuing.

---

## Initial Setup (First Time Only)

### 1. Clone the repository

```bash
git clone <repo-url>
cd bakery-erp
```

---

### 2. Create environment file

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` if needed (defaults are fine for development).

⚠️ **Never commit `.env`**.

---

### 3. Build and start containers

```bash
docker compose build
docker compose up
```

This will start:

* Django backend (port 8000)
* PostgreSQL database (internal container network)

Access the backend at:

```
http://localhost:8000
```

---

## Database Setup

### Run migrations

```bash
docker compose exec backend python manage.py migrate
```

### Create a superuser

```bash
docker compose exec backend python manage.py createsuperuser
```

---

## Daily Development Workflow

### Start the project

```bash
docker compose up
```

### Stop the project

```bash
Ctrl + C
```

### Restart (no rebuild)

```bash
docker compose down
docker compose up
```

---

## When to Rebuild

Only rebuild Docker **when one of these changes**:

* `requirements.txt`
* `Dockerfile`
* Python version
* System-level dependencies

Rebuild command:

```bash
docker compose build
docker compose up
```

❌ Do **not** rebuild for normal code changes.

---

## Dependency Management

* All dependencies are defined in:

  ```
  backend/requirements.txt
  ```
* Docker is the **source of truth** for dependencies.
* Local virtual environments (`.venv`) are optional and not authoritative.

### Adding a new dependency

1. Add it to `requirements.txt`
2. Rebuild Docker:

   ```bash
   docker compose build
   docker compose up
   ```

---

## Database & Data Policy

* Each developer has their **own local database**
* Database data is **persistent locally** via Docker volumes
* Database **schema is shared** via Django migrations
* Database **data is NOT shared via Git**

### Shared baseline data

If needed, we use:

* Django fixtures (`dumpdata` / `loaddata`)
* or documented manual seeding

We do **not** commit database dumps or volumes.

---

## Team Rules (Non-Negotiable)

* ❌ Do not run Django outside Docker
* ❌ Do not install Postgres locally
* ❌ Do not hardcode secrets
* ✅ If it doesn’t work in Docker, it’s broken
* ✅ Schema changes must go through migrations

---


## Troubleshooting

### Django not accessible?

* Make sure Django is running on `0.0.0.0:8000` inside Docker
* Access via `http://localhost:8000` on host

### Database issues?

```bash
docker compose down -v
docker compose up
```

⚠️ This wipes your local database.

