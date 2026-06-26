# Gramin PAN Seva — PRD

## Original Problem Statement
B2B PAN card services portal: FastAPI + MongoDB backend powering an existing single-file Bootstrap HTML frontend. Hierarchical roles (Super Admin → Super Distributor → Distributor → Retailer), wallet/billing, manual UTR recharge approvals, PAN application workflow with admin review, email OTP, FTP document uploads, tickets, notifications, settings, audit logs.

## User Choices
- Existing HTML frontend (uploaded) wired to backend via same-origin `/api/*`.
- SMTP configurable in admin settings but **MOCKED** for MVP (OTP logged + returned as `dev_otp`).
- Document uploads via built-in object/local storage, **FTP MOCKED**.
- Auth: JWT + bcrypt, login by **User ID + password**.
- Default pricing ₹107 New PAN / ₹85 CSF, editable from admin Rate Setup.

## Architecture
- Backend: `/app/backend/server.py` (all `/api` routes), `security.py` (JWT Bearer + bcrypt, role deps), `seed_data.py` (idempotent seed), `database.py`.
- Frontend: `/app/frontend/public/index.html` (Bootstrap SPA; inline JS calls `/api/*` with Bearer token from `localStorage.gps_token`). React bundle is a no-op.
- MongoDB collections: users, registrations, pan_applications, transactions, recharge_requests, tickets, notifications, settings, audit_logs, ao_codes, meta, otps, counters.

## Personas
Super Admin (platform owner), Super Distributor (region), Distributor (zone), Retailer (submits PAN apps).

## Implemented (2026-06-26)
- JWT+bcrypt auth, session restore, role-based access control (4 roles), blocked/pending login guards.
- 3-step registration with mocked email OTP → pending registration → admin approval creates real user with auto code.
- Hierarchical user CRUD (ancestors-based downline scoping), create/block/unblock/delete, auto user-code generation.
- Wallet: balance, manual UTR recharge request, admin approve/reject (credits wallet + ledger), transaction history, auto-debit on PAN submit.
- PAN workflow: submit New/CSF (wallet debit + insufficient-balance guard), admin Approve(receipt)/Hold(remark)/Reject(remark), delete, notifications.
- AO code lookup (states/cities/ao-codes), seeded from frontend data.
- Support tickets (create/list/thread/reply/resolve), in-app notifications feed, audit logs.
- Admin settings (SMTP/FTP/pricing/toggles), Rate Setup editing live pricing.
- Mock FTP file uploads (local disk, served at `/api/uploads`).
- Live dashboards (role-aware stats + activity feed).
- Verified: 36/36 backend tests pass; frontend e2e flows verified.

## Backlog / Next
- P1: Add data-testid attributes across the HTML for robust automation.
- P1: OTP expiry (TTL) + login rate-limiting/brute-force lockout.
- P2: Real SMTP (Hostinger) + real FTP credentials wiring (currently mocked).
- P2: Tighten CORS to explicit origins for production.
- P2 (future): Razorpay auto-recharge, NSDL/UTI API, PDF summary, commission/payout, GST invoicing.
