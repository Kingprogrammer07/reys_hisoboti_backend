# Target Architecture Specification

## Overview
`mandarin_foto_hisobot` is an admin-only trip report ("reys hisoboti") management system supporting Telegram Mini App context and standalone web access.

```
+-------------------------------------------------------+
|                      Clients                          |
|  +------------------------+  +---------------------+  |
|  | Telegram Mini App (TG) |  | Standalone Browser  |  |
|  +-----------+------------+  +----------+----------+  |
+--------------|--------------------------|-------------+
               | (initData)               | (Session Cookie/JWT)
               v                          v
+-------------------------------------------------------+
|                    FastAPI Server                     |
|  +-------------------------------------------------+  |
|  |             Auth & Security Middleware           |  |
|  +------------------------+------------------------+  |
|                           |                           |
|  +------------------------v------------------------+  |
|  |             API Controllers / Routers           |  |
|  +------------------------+------------------------+  |
|                           |                           |
|  +------------------------v------------------------+  |
|  |             Service Layer (Rules)               |  |
|  +------------------------+------------------------+  |
|                           |                           |
|  +------------------------v------------------------+  |
|  |         Async SQLAlchemy 2.x Repository         |  |
|  +------------------------+------------------------+  |
+---------------------------|---------------------------+
                            v
+-------------------------------------------------------+
|             Database & Storage Layer                  |
|  +------------------------+  +---------------------+  |
|  | PostgreSQL (Neon DB)   |  | Cloudflare R2 / S3  |  |
|  +------------------------+  +---------------------+  |
+-------------------------------------------------------+
```

## Backend Architecture Design
- **Async First:** Asyncio event loop running both Uvicorn (FastAPI) and aiogram-3 Dispatcher.
- **ORM:** SQLAlchemy 2.x with `AsyncSession` and `asyncpg` driver.
- **Schemas:** Pydantic v2 models for strict request/response validation and OpenAPI schema generation.
- **Outbox Pattern:** Asynchronous outbox worker ensuring reliable Telegram channel notification deliveries without blocking user requests.

## Frontend Architecture Design
- **Framework:** React 18 / 19 with TypeScript, bundled via Vite.
- **UI System:** shadcn/ui built on top of Tailwind CSS.
- **Icons & Typography:** Lucide React icons with Inter font.
- **Data Fetching:** TanStack Query (React Query v5) for cache control, optimistic updates, and loading states.
- **Form Validation:** React Hook Form integrated with Zod schemas.
