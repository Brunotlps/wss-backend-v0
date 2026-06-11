# Server Optimization — 2026-05-26

**VPS:** DigitalOcean NYC1 (`<VPS_IP>`, user `<VPS_USER>`)
**Project path:** `/home/<VPS_USER>/wss-backend-v0/`
**Executed:** 2026-05-26
**PR:** #4 (squash merged to main)

---

## Diagnostic Snapshot (Pre-Optimization)

| Resource | Before | After |
|----------|--------|-------|
| Disk used | 9.3GB / 48GB (20%) | ~7.2GB / 48GB (15%) |
| RAM used | 1.3GB / 1.9GB (68%) | 914MB / 1.9GB (47%) |
| Swap | 0B | 1GB active |
| Free RAM | 154MB | 324MB (+1GB swap) |
| Docker build cache | 3.029GB | 904MB (2.125GB freed) |
| Docker log rotation | None | 10MB x 3 per container |
| Django ERROR logs | 4021 lines/month (bots) | ~0 (blocked at Nginx) |

### Container Memory (Pre-Optimization)

| Container | Memory | Limit |
|-----------|--------|-------|
| wss_backend | 364.3MB | 1GB |
| wss_celery | 194.5MB | **None** |
| wss_celery_beat | 194.6MB | **None** |
| wss_nginx | 9.4MB | None |
| wss_postgres | 44.1MB | None |
| wss_redis | 4.0MB | None |

---

## Execution Results

### Subtask 1 — Docker Build Cache Cleanup
- **Status:** Done
- **Result:** 2.125GB freed
- **Command:** `docker builder prune -f`

### Subtask 2 — Remove Orphan Volume
- **Status:** Skipped
- **Reason:** Volume `8205d76f...` is attached to wss_redis (anonymous data volume, 8KB). Not worth the risk.

### Subtask 3 — Docker Log Rotation
- **Status:** Done
- **Config:** `/etc/docker/daemon.json` — `max-size: 10m`, `max-file: 3`
- **Applied via:** `sudo systemctl restart docker`

### Subtask 4 — Swap 1GB
- **Status:** Done
- **Config:** `/swapfile` (1GB), persistent via `/etc/fstab`

### Subtask 5 — Celery Memory Limits
- **Status:** Done
- **Changes:** `docker-compose.yml`
  - celery worker: 384MB limit, 128MB reservation
  - celery-beat: 128MB limit, 64MB reservation

### Subtask 6 — Redis maxmemory
- **Status:** Done
- **Config:** `maxmemory 64mb`, `maxmemory-policy allkeys-lru`
- **Note:** Applied via `CONFIG SET` (runtime). Non-persistent — reapply after Redis restart, or add to compose command.

### Subtask 7 — Django Log Errors Investigation
- **Status:** Done
- **Finding:** 100% of 4021 errors were `Invalid HTTP_HOST header` from bots/scanners (ultclub.at, bclub.tk, staging2.wargaming3d.com, etc.)
- **Fix (Nginx):** Default server block returning 444 drops bot connections before reaching Django
- **Fix (Django):** `django.security.DisallowedHost` logger set to WARNING in `production.py`

### Subtask 8 — Split requirements.txt
- **Status:** Pending (future optimization)
- **Impact:** ~100-150MB per Docker image reduction
- **Packages to move:** black, isort, flake8, coverage, pytest, pytest-cov, pytest-django, factory-boy, Faker, django-debug-toolbar, django-extensions

---

## Files Changed

| File | Change |
|------|--------|
| `nginx/nginx.conf` | Added default server (444 for bots), set `server_name api.nousflow.com.br` |
| `docker-compose.yml` | Added `deploy.resources.limits` to celery and celery-beat |
| `backend/config/settings/production.py` | Added `django.security.DisallowedHost` logger at WARNING level |

## Server-Side Changes (Not in Git)

| Change | Location |
|--------|----------|
| Docker log rotation | `/etc/docker/daemon.json` |
| Swap file | `/swapfile` + `/etc/fstab` |
| Redis maxmemory | Runtime config (non-persistent) |
| Build cache pruned | Docker builder cache |
