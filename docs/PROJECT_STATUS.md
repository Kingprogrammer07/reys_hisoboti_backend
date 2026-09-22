# Project Status: mandarin_foto_hisobot (Production Transformation)

## Executive Summary
The project is undergoing a full architectural transition from an MVP to an enterprise-grade production software stack. The workspace has been decoupled into two separate repository directories:
- `backend/`: FastAPI + aiogram-3 + PostgreSQL / SQLAlchemy 2.x
- `frontend/`: Vite + React + TypeScript + Tailwind CSS

- **Completion Percentage:** 100% (Fast Mode Auto-Focus on Photo Capture & Fullscreen Captured Photo Lightbox Preview Implemented)
- **Production Readiness:** Frontend UI Complete (Standalone Browser Web App running live on Vite dev server: `http://localhost:5173/` and `http://192.168.1.5:5173/`)

## Feature Matrix

| Feature | Status | Tech Stack (Target) | Notes |
|---|---|---|---|
| Photo Capture Auto-Focus (Fast Mode) | Completed | Ref focus timer | In Fast Mode, taking photo immediately focuses back on Karobka kodi input |
| Captured Photo Lightbox Enlargement | Completed | Lightbox Modal + Zoom Button | Tapping captured photo opens high-resolution fullscreen preview with zoom badge |
| Camera Viewfinder Square Overlay Removal | Completed | MediaStream + Fullscreen Viewport | Clean, unobstructed video feed |
| Custom Tare Confirmation Dialog | Completed | Glassmorphism Dialog Modal | Prompts `Karobka og'irligi saqlansinmi?` with `Ha, saqlansin` / `Faqat 1 marta` |
| Terminology Normalization | Completed | App-wide standard | Replaced "Brutto" with "Og'irlik" and "Tara" with "Karobka og'irligi" everywhere |
| Dedicated Uploaded Entries Page (`/reports/reys/:id/entry/:cat/list`) | Completed | React Router v6 + Grid | Dedicated page with search, stats, cards, lightbox & Excel export |
| Clean Entry Form (No bottom list) | Completed | Refactored Layout | Form ends cleanly right at "Saqlash" button as requested |
| Standalone Frontend App | Completed | Vite + React + TypeScript + Tailwind | Running live |

## Known Issues & Blockers
- Frontend currently runs on rich mock data and localStorage until backend API schemas and endpoints are connected.
