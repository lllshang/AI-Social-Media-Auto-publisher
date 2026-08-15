# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **AI Multi-Platform Content Auto-Publishing System** (MVP) - a FastAPI backend + Vue 3 frontend application for automated content publishing to social media platforms (Xiaohongshu/小红书, Douyin/抖音, Kuaishou/快手).

**Main development branch:** `develop_P0`  
**Core application directory:** `ai-publish/`  
**Management UI:** `/app/` route (e.g., `http://127.0.0.1:8765/app/`)

## Repository Structure

```
ai-publish/                 # Main application
├── backend/app/            # FastAPI backend (Python 3.11+)
├── web/                    # Vue 3 + Element Plus admin UI
├── scripts/                # Database init, deployment, E2E scripts
├── docker-compose.yml      # Production orchestration
├── .env.example            # Local development env template
├── .env.docker.example     # Docker deployment env template
├── start.sh / start.ps1    # Local startup scripts
└── web.sh                  # Frontend build script

docs/                       # User/operations documentation
openspec/                   # Specification-driven development (SDD) specs
vendor/social-auto-upload/  # Third-party reference: Playwright scraping/publishing
```

## Essential Commands

### Local Development (macOS/Linux)

```bash
# First-time setup
cd ai-publish
cp .env.example .env
./web.sh                    # Build Vue frontend
./start.sh                  # Start API server

# Daily development
./start.sh                  # Starts FastAPI on http://127.0.0.1:8765
./web.sh dev                # Frontend dev mode on http://127.0.0.1:5173

# Rebuild frontend after changes
./web.sh
```

### Local Development (Windows PowerShell)

```powershell
cd ai-publish
copy .env.example .env
cd web; npm install; npm run build; cd ..
.\start.ps1
```

### Docker Deployment

```bash
cd ai-publish
cp .env.docker.example .env
./web.sh                              # Build frontend first
docker compose up -d --build          # Start all services

# View logs
docker compose logs -f api
docker compose logs -f worker

# Stop services
docker compose down
```

### Testing

```bash
# E2E smoke test
cd ai-publish/scripts
python e2e_publish.py

# Platform adapter verification
python verify_platform_adapters.py
```

### Production Deployment

```bash
# Sync to server (configure scripts/deploy.env first)
cd ai-publish
./web.sh
bash scripts/sync-to-server.sh

# On server: upgrade
bash scripts/upgrade.sh
```

## Backend Architecture

### Layer Structure

```
backend/app/
├── main.py                 # FastAPI entry, router registration, lifecycle (scheduler/Redis consumer)
├── config.py               # Environment config (DB, Redis, AI keys, storage)
├── database.py             # SQLAlchemy engine & sessions
├── dependencies.py         # JWT auth, RBAC permission dependencies
├── models/                 # ORM entities (User, Role, PublishTask, Material...)
├── schemas/                # Pydantic request/response models
├── api/                    # HTTP route layer
│   ├── auth.py             # Login /api/auth
│   ├── dashboard.py        # Dashboard stats /api/dashboard
│   ├── platform_accounts.py
│   ├── account_groups.py
│   ├── materials.py        # Materials + AI copy/image generation
│   ├── publish_tasks.py    # Task CRUD, execution, review
│   ├── ai_models.py        # AI model detection & switching
│   └── ...
├── services/               # Business logic
│   ├── publish_service.py  # Task state machine, submit, execute
│   ├── material_service.py # Materials, AI content generation
│   └── ...
├── adapters/               # Pluggable adapters
│   ├── factory.py          # Platform/AI/storage factories
│   ├── platform/           # xhs, douyin, kuaishou publish adapters
│   ├── ai_text/            # Copy generation (Tongyi, OpenAI-compatible)
│   ├── ai_image/           # Text-to-image
│   └── storage/            # local, cos/oss/s3 object storage
├── workers/                # Background tasks
│   ├── redis_queue.py      # Redis publish task queue
│   ├── redis_consumer.py   # Standalone worker process entry
│   ├── schedule_worker.py  # APScheduler for scheduled publishing
│   ├── task_runner.py      # Execute single publish task
│   └── upload_worker.py    # Call platform adapter for actual upload
├── templates/prompts/      # Per-platform YAML prompt templates
└── utils/                  # Migrations, Playwright, permissions, encryption
```

**Data Flow:**
1. User creates content in `web` publish wizard → generates copy/cover → `materials` + `publish_tasks`
2. After submit, task is `pending`; manual or scheduled trigger → Redis queue → `worker` executes
3. `upload_worker` uses `vendor/social-auto-upload` Playwright scripts to publish to platforms

### Key Technology Choices

- **FastAPI** with Pydantic for validation
- **SQLAlchemy ORM** - supports both SQLite (local dev) and MySQL (production)
- **Redis** for task queue (can be disabled via `TASK_QUEUE_ENABLED=false`)
- **Playwright** (via Patchright) for platform automation (login/publish)
- **APScheduler** for scheduled publishing
- **JWT** authentication with RBAC (admin, operator, reviewer, viewer roles)

## Frontend Architecture

```
web/src/
├── views/
│   ├── DashboardView.vue     # /app/ - Dashboard with failed tasks, account health, AI stats
│   ├── AccountsView.vue      # /app/accounts - Platform accounts, groups, QR code login
│   ├── ModelsView.vue        # /app/models - AI model & key configuration
│   ├── MaterialsView.vue     # /app/materials - Material library, batch AI image generation
│   ├── TasksView.vue         # /app/tasks - Task list & operations
│   ├── PublishView.vue       # /app/publish - 5-step publish wizard
│   ├── LogsView.vue          # /app/logs - Log center
│   └── SettingsView.vue      # /app/settings - System settings (RBAC visible)
├── api/index.js              # All backend API wrappers
├── stores/auth.js            # Login state, role permissions
└── constants/platforms.js    # Xiaohongshu/Douyin/Kuaishou constants
```

## Docker Compose Services

| Service | Port (default) | Role |
|---------|---------------|------|
| `mysql` | 3307→3306 | Business database |
| `redis` | 6380→6379 | Publish task queue |
| `api` | 8000 | FastAPI + static admin page |
| `worker` | - | Consume Redis queue, execute publishing |
| `nginx` | 8080/8443 | HTTP/HTTPS reverse proxy to API |

## Configuration & Environment

**Critical Environment Variables:**

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Database connection (SQLite for dev, MySQL for prod) |
| `REDIS_URL` | Redis connection for task queue |
| `TASK_QUEUE_ENABLED` | Enable/disable Redis queue |
| `STORAGE` | `local` / `cos` / `oss` / `s3` |
| `PLAYWRIGHT_HEADLESS` | `true` for server, `false` for local QR code scanning |
| `PLAYWRIGHT_CHANNEL` | `chrome` for local, system Chromium for Docker |
| `SAU_VENDOR_PATH` | Path to vendor/social-auto-upload |
| `SCHEDULER_ENABLED` | Enable scheduled publishing |
| AI keys: `DASHSCOPE_API_KEY`, `OPENAI_API_KEY`, `HUNYUAN_API_KEY`, etc. |

**Configuration precedence:** System settings page (`/app/settings`) > environment variables

## Database

**Main tables:**
- `users` / `roles` - User & RBAC
- `platform_accounts` / `account_cookies` - Platform accounts & encrypted cookies
- `account_groups` - Account grouping
- `materials` - Materials (uploaded/AI-generated)
- `ai_generation_records` - AI call logs (tokens/images counted in cost)
- `publish_tasks` / `publish_task_logs` - Publish tasks & execution logs
- `system_configs` - Backend-modifiable system switches
- `operation_logs` - Management operation audit

**Schema:** `ai-publish/scripts/init_db.sql`  
**Migrations:** SQLite incremental migrations in `backend/app/utils/migrations.py`

## Default Accounts

| Role | Username | Default Password | Environment Variable |
|------|----------|-----------------|---------------------|
| Admin | `admin` | `admin123` | `ADMIN_USERNAME` / `ADMIN_PASSWORD` |
| Operator | `operator` | `operator123` | `OPERATOR_USERNAME` / `OPERATOR_PASSWORD` |
| Reviewer | `reviewer` | `reviewer123` | `REVIEWER_USERNAME` / `REVIEWER_PASSWORD` |
| Viewer | `viewer` | `viewer123` | `VIEWER_USERNAME` / `VIEWER_PASSWORD` |

**Change passwords immediately in production!** Passwords are bcrypt-hashed and cannot be viewed in the system after modification.

## Key APIs

| Prefix | Module |
|--------|--------|
| `/api/auth` | Login, current user |
| `/api/dashboard` | Dashboard statistics |
| `/api/platform-accounts` | Platform accounts, QR login, cookies |
| `/api/account-groups` | Account groups |
| `/api/materials` | Material upload/list |
| `/api/ai/text/generate` | AI copy generation |
| `/api/ai/image/generate` | AI text-to-image |
| `/api/ai/models` | Model detection & switching |
| `/api/publish-tasks` | Full task lifecycle |
| `/api/logs` | AI records, operation logs |
| `/api/system/runtime` | Runtime environment info |
| `/api/system/configs` | System configuration |
| `/api/reviews/pending` | Pending review tasks |
| `/health` | Health check |
| `/docs` | Swagger UI |

## Common Development Workflows

### Adding a New Platform

1. Create platform adapter in `backend/app/adapters/platform/<platform>_adapter.py`
2. Register in `adapters/factory.py`
3. Add platform constants to `web/src/constants/platforms.js`
4. Update `platform_accounts` table to support new platform type
5. Add Playwright automation script or integrate vendor implementation

### Adding a New AI Provider

1. Create text/image adapter in `backend/app/adapters/ai_text/` or `ai_image/`
2. Implement the provider interface (generate method, model detection)
3. Register in factory
4. Add API key to `.env.example` and `config.py`
5. Update `ai_models.py` detection logic

### Modifying Publishing Workflow

- State machine logic: `services/publish_service.py`
- Task execution: `workers/task_runner.py`
- Platform upload: `workers/upload_worker.py`
- UI wizard: `web/src/views/PublishView.vue`

## Important Notes

### Playwright & Browser Automation

- **Local dev:** Uses local Chrome (`PLAYWRIGHT_HEADLESS=false`) for QR code scanning
- **Docker:** Uses system Chromium with `--no-sandbox` (see `utils/chromium_launch.py`)
- **Vendor integration:** `vendor/social-auto-upload` provides reference Playwright implementations for Xiaohongshu/Douyin/Kuaishou

### Task Queue

- Redis queue can be disabled for testing with `TASK_QUEUE_ENABLED=false`
- Worker can run embedded in API (`TASK_QUEUE_EMBEDDED_CONSUMER=true`) or separate process
- Scheduled tasks use APScheduler, independent of Redis queue

### Storage

- Local dev: `./data/materials`
- Production: Supports Tencent COS, Alibaba OSS, AWS S3 via `STORAGE` env var
- Cookies stored encrypted in `data/cookies/`

## Documentation

**Must-read for new developers:**
1. [docs/project-overview.md](docs/project-overview.md) - Full code structure & doc index
2. [docs/deployment.md](docs/deployment.md) - Deployment guide for all platforms
3. [docs/daily-usage.md](docs/daily-usage.md) - User manual for login, publishing, AI config
4. [docs/api-test.md](docs/api-test.md) - curl examples for all APIs

**SDD Specifications:**
- Current specs: `openspec/specs/` - Stable module specifications
- Active development: `openspec/changes/content-flow-41-complete/` - Current phase tasks
- Archived MVP: `openspec/changes/archive/2026-06-09-mvp-xhs-auto-publish/`

## Python Version

**Required:** Python 3.11+ (tested with 3.14)

## Access Points

- **Local development:** `http://127.0.0.1:8765/app/`
- **Docker:** `http://127.0.0.1:8000/app/`
- **With Nginx:** `http://127.0.0.1:8080/app/` (HTTP) or `https://127.0.0.1:8443/app/` (HTTPS)
