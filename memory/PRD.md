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

## Implemented (2026-06-27 — fork continuation)
- Admin restrictions: Super Admin can no longer submit PAN (New/CSF) or wallet recharges — backend returns 403; frontend hides the entire "PAN Services" sidebar section and guards goTo() for pan-new/pan-csf. Admin keeps PAN Status, Recharge Approvals, Settings, Rate Setup.
- New PAN form: added "Name on Card" and "PAN Card Type (Normal/Minor)" fields (per client screenshot).
- CSF (Correction) form rebuilt as a full single-page form: PAN Number, applicant identity, parent details, Aadhaar/contact, address, AO-code cascade (State→City→Ward), Number of Documents, and "Change/Correction Requested" checkboxes (Full Name, Father's Name, DOB, Gender, Address) + document uploads.
- UPI/QR payment settings: Admin Settings has a UPI ID + Payee + Note + QR image upload card; non-admin recharge screen displays the configured UPI ID/QR (`upi` returned to non-admins via GET /api/settings, no SMTP/FTP leakage).
- build_index.py now auto-restarts the `frontend` supervisor program so freshly built index.html is served (CRA caching gotcha).
- DB clean for launch (scope a): cleared pan_applications/recharge_requests/transactions/notifications/tickets/audit_logs and reset all wallet balances to ₹0; kept users (33), settings (incl. UPI), and ao_codes (1832). Script: backend/clear_test_data.py.
- Verified: backend 6/6 iteration-6 tests pass; frontend flows 100% (test_reports/iteration_6.json).

## Implemented (2026-06-29 — iteration 7)
- Name autofill: typing 'Name as per Aadhaar' auto-splits into First/Middle/Last (New PAN + CSF) and mirrors the Identity 'Name as per Aadhaar' field.
- Full official dropdowns: Source of Income (6), Proof of Identity (23), Proof of Address (33), Proof of DOB (14) — populated via DOC_LISTS/populateDocLists.
- Single 'Form + Documents PDF' upload (max 2MB, .pdf) replaces the 4 separate upload tiles in both forms, with the 200dpi note.
- Dynamic wallet balance on New PAN review (real balance + role rate + remaining), no more hardcoded numbers.
- Admin 'Add Balance' (sidebar → Wallet Management): pick role → user → amount; instantly credits wallet (apply_wallet) and inserts an Approved recharge_requests row (utr='ADMIN CREDIT') so it shows in the user's recharge history. Endpoint: POST /api/wallet/admin-credit.
- Acknowledgement Number field in the PAN Accept review flow (stored on pan_applications.acknowledgement_number).
- Per-role service rates: Rate Setup is now a matrix (New PAN/CSF PAN × Super Distributor/Distributor/Retailer). pricing stored as nested dict; create_pan charges submitter's role rate via resolve_price() (fallback New 107 / CSF 85).
- Dynamic profile: loads real user data via /auth/me, edit name/mobile/email/shop/address + photo upload. Endpoint: PUT /api/profile (public_user now returns photo_path).
- Admin PAN detail modal shows ALL submitted fields with per-row copy icons + 'Copy All Details'.
- Verified: backend 6/6 (iteration_7.json), frontend 100% on all 10 flows, zero bugs.

## Backlog / Next
- P1: Add data-testid attributes across the HTML for robust automation.
- P1: OTP expiry (TTL) + login rate-limiting/brute-force lockout.
- P2: Real SMTP (Hostinger) + real FTP credentials wiring (currently mocked).
- P2: Tighten CORS to explicit origins for production.
- P2 (future): Razorpay auto-recharge, NSDL/UTI API, PDF summary, commission/payout, GST invoicing.
