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
