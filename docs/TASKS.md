# Task Tracking (Kanban Board)

## TODO
- [ ] Connect TanStack Query to FastAPI endpoints for live data fetching.
- [ ] Initialize Alembic migration environment for PostgreSQL.
- [ ] Define SQLAlchemy 2.x Async ORM models (`Report`, `Inventory`, `ActivityLog`, `OutboxMessage`).
- [ ] Refactor `app/db.py` to Async Repository pattern using SQLAlchemy 2.x.
- [ ] Create Pydantic v2 schemas for all API request/response DTOs.

## IN PROGRESS
- [ ] Backend implementation of Cargo & Reys CRUD API endpoints, Excel date-range export generation, soft deletion (Recycle Bin 30-day retention), and PostgreSQL tables.

## DONE
- [x] Phase 1: Initialize documentation framework (`docs/*`) and architecture specification.
- [x] Phase A Frontend: Implement **Fast Mode Auto-Focus on Karobka Kodi** immediately after snapping/capturing photo or selecting from gallery.
- [x] Phase A Frontend: Implement **Fullscreen Photo Lightbox Enlargement** for captured photos with zoom button, overlay, and discard/retake controls.
- [x] Phase A Frontend: Remove square reticle overlay from camera viewfinder.
- [x] Phase A Frontend: Replace raw checkbox with modern glassmorphism confirmation dialog asking if custom tare weight should be saved.
- [x] Phase A Frontend: Standardize terminology across the application replacing "Brutto" with "Og'irlik" and "Tara" with "Karobka og'irligi".
- [x] Phase A Frontend: Verify production build (`npm run build` passed with zero errors).

## Blocked
*None*

## Technical Debt
- Legacy raw SQL queries in `app/db.py` pending migration to SQLAlchemy 2.x async ORM.
- Legacy `webapp/` vanilla JS codebase ready for deprecation once Vite + React frontend is deployed.
