# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2026-08-06

### Added / Changed
- Modularized Reports section into explicit React Router URL paths for human and AI clarity:
  - `/reports` -> `ReportsMenuPage.tsx` (2 category choice cards)
  - `/reports/cargos` -> `CargoListPage.tsx` (Kargolar list view with search & FAB + creation modal)
  - `/reports/cargos/:cargoId` -> `CargoDetailPage.tsx` (Cargo reys list with top 3 visible & collapse toggle)
  - `/reports/reys` -> `ReysListPage.tsx` (Direct reys list view)
- Extracted `ReysCard` component to `frontend/src/components/reports/ReysCard.tsx`.
- Updated documentation suite under `docs/`.
