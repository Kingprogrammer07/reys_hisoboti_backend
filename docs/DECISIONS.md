# Architectural Decision Records (ADR)

## ADR-001: Adoption of PostgreSQL with SQLAlchemy 2.x Async Engine
* **Date:** 2026-08-06
* **Status:** Approved
* **Context:** The MVP relied on local SQLite (`reys.db`) with raw SQL queries. As the application transitions to production with potential serverless hosting (Neon DB), concurrent multi-user transactions require robust PostgreSQL capabilities.
* **Decision:** Use PostgreSQL with SQLAlchemy 2.x async ORM (`asyncpg` driver) and Alembic for database migrations.
* **Tradeoffs:** Requires migration scripts for existing data and async session management overhead, but guarantees concurrency safety, transactional stability, and Neon cloud scalability.

## ADR-002: Frontend Framework Selection (Vite + React + TypeScript + shadcn/ui)
* **Date:** 2026-08-06
* **Status:** Approved
* **Context:** The MVP frontend used a single vanilla `app.js` file (~150KB) and `index.html`. While fast to initial load without a build step, it is difficult to maintain, type, and scale.
* **Decision:** Move to Vite + React + TypeScript with shadcn/ui design tokens, Lucide icons, and Inter font.
* **Tradeoffs:** Introduces a build step and bundle, offset by developer productivity, strict typing, component modularity, and superior UI/UX aesthetics matching enterprise standards.

## ADR-003: Cargo & Reys Soft Delete and Data Retention Rules
* **Date:** 2026-08-07
* **Status:** Approved
* **Context:** Deleting Cargos or Reys requires consistent cascading logic between the high-level Cargo containers and individual Reys items, alongside 30-day retention in a Recycle Bin ("Savatcha").
* **Decision:**
  1. **Cargo Deletion Rule:** Deleting a Cargo soft-deletes the Cargo container. The child Reys objects remain attached to the Cargo, but **all entry data/weights inside those child Reys are temporarily cleared/zeroed out**. Restoring the Cargo restores all entry data back to its original state.
  2. **Reys Deletion Rule:** Trips listed in `/reports/reys` map 1-to-1 with trips inside Cargos (`/reports/cargos/:cargoId`). Soft-deleting a Reys in `/reports/reys` soft-deletes that specific 1 trip from its parent Cargo as well.
  3. **30-Day Retention & Purge:** All soft-deleted items (Cargos and Reys) are retained in the Recycle Bin (`deleted_at` timestamp) for 30 days before background worker auto-purging. Admins can restore or permanently delete items at any time.
* **Tradeoffs:** Requires handling `is_deleted` flags and entry state preservation in PostgreSQL tables, ensuring full data recovery and zero accidental data loss.

## ADR-004: 320px Mobile-First Responsive Standard & Multi-Photo Workflow
* **Date:** 2026-09-22
* **Status:** Approved
* **Context:** Warehouse scales and cold storage operators frequently use compact mobile devices (e.g., iPhone SE 1st gen, 320px screen width) often in rugged cases. Previously, wide headers, bulky badges, single photo constraints, and non-wrapping button groups degraded mobile usability.
* **Decision:**
  1. **Strict 320px Responsiveness:** All pages, cards, modals, headers, and forms must render flawlessly at 320px minimum screen width with zero horizontal overflow (`overflow-x`). Padding uses `px-2.5 sm:px-4`, typography scales dynamically (`text-[11px]` to `text-xs`), and button groups wrap cleanly.
  2. **Multi-Photo Per Box Support:** Operators can capture 1 or more photos per box (scale readout, barcode, produce quality). Continuous shutter capture in fullscreen camera with immediate counter and preview strip, multiple file gallery uploads (`multiple`), thumbnail strip with zoom and individual delete.
  3. **Terminology Consistency:** Standardized on "Og'irlik" (not Brutto), "Karobka og'irligi" (not Tara), and "Toza vazn" (not Netto).
* **Tradeoffs:** Requires persistent multi-photo array state (`photoUrls: string[]`) and strict Tailwind CSS responsiveness testing at 320px width.

