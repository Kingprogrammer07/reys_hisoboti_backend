# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2026-09-22

### Added / Changed
- **Multi-Photo Support (`ReysEntryFormPage.tsx`, `ReysEntriesListPage.tsx`):**
  - Allowed capturing and uploading multiple photos per entry (`photoUrls: string[]`).
  - Added continuous camera shutter snapping with live count badge and viewfinder thumbnail strip.
  - Multi-photo thumbnail reel with individual delete, lightbox enlargement, and add-photo triggers.
- **Mandatory 320px Responsive Standard Across Entire App:**
  - Standardized all pages, cards, and modals down to 320px screen width without horizontal overflow.
  - Horizontally scrollable tables with `overflow-x-auto` and `min-w-[480px]`.
- **Savatcha (Recycle Bin) Modals 320px Optimization:**
  - Kargolar and Reyslar recycle bin cards auto-stack into responsive vertical cards on mobile (`< sm`).
  - Compact dialog padding and truncated titles to prevent layout clipping.
- **Mobile Navigation & Header Polish:**
  - Removed "Kirish" tab from `MobileNav` (system operates behind authentication).
  - Unmounted `MobileNav` and top `Navbar` during full-screen camera and entry workflow (`/entry/`).
  - Rebranded header to **"Hisobot oynasi"** with emerald spreadsheet avatar.
- **Dashboard Metric Simplification:**
  - Removed legacy hero banner and platform status card; balanced 3 core business metrics.
  - Shortened "Tovar balansi / Joriy zaxira" section.

