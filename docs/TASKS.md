# Task Tracking (Kanban Board)

## TODO
- [ ] Connect TanStack Query to FastAPI endpoints for live data fetching.
- [ ] Initialize Alembic migration environment for PostgreSQL.
- [ ] Define SQLAlchemy 2.x Async ORM models (`Report`, `Inventory`, `ActivityLog`, `OutboxMessage`).
- [ ] Refactor `app/db.py` to Async Repository pattern using SQLAlchemy 2.x.
- [ ] Create Pydantic v2 schemas for all API request/response DTOs.

## IN PROGRESS
- [ ] Backend implementation of Reys Reports data endpoints and PostgreSQL tables.

## DONE
- [x] Phase 1: Initialize documentation framework (`docs/*`) and architecture specification.
- [x] Phase A Frontend: Implement explicit React Router path routing for every view:
  - `/reports` (Reports choice menu)
  - `/reports/cargos` (Cargo list + FAB (+) modal)
  - `/reports/cargos/:cargoId` (Cargo detail + top 3 reys collapsed list)
  - `/reports/reys` (Direct all reys list)
  - `/` (Dashboard)
  - `/activity` (Activity audit log)
  - `/login` (4-digit PIN code web auth)
- [x] Phase A Frontend: Simplify Reys & Cargo cards to use `code` (`kodi`) as primary header.
- [x] Phase A Frontend: Verify production build (`npm run build` passed with zero errors).

## Blocked
*None*

## Technical Debt
- Legacy raw SQL queries in `app/db.py` pending migration to SQLAlchemy 2.x async ORM.
- Legacy `webapp/` vanilla JS codebase ready for deprecation once Vite + React frontend is deployed.
