# Gramin PAN Seva — Deploy to your own VPS (graminpanseva.in)

This folder contains everything to run the app on a VPS with **Docker Compose**:
MongoDB + FastAPI (serves the API **and** the website) + Nginx + automatic HTTPS (Let's Encrypt).

> The frontend is a single static HTML file (`frontend/public/index.html`); all CSS/JS come
> from CDNs and inline code, so **no Node build is needed** — FastAPI serves it directly.

---

## 0) Prerequisites

- A VPS (Ubuntu 22.04+ recommended) with a public IP.
- Domain DNS configured: create **A records** pointing to your VPS IP:
  - `graminpanseva.in` → `YOUR_VPS_IP`
  - `www.graminpanseva.in` → `YOUR_VPS_IP`
- Docker + Docker Compose installed:
  ```bash
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker $USER     # then log out/in
  ```

---

## 1) Get the code on the VPS

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>/deploy
```

## 2) Configure environment

```bash
cp .env.example .env
nano .env
```
Set at least:
- `JWT_SECRET` → run `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `ADMIN_PASSWORD` and `SEED_USER_PASSWORD` → strong values
- (optional) `ADMIN_EMAIL`, `DB_NAME`

## 3) Build the images

```bash
docker compose build
```

## 4) Get SSL certificates + start everything (one command)

Edit the email at the top of `init-letsencrypt.sh` (optional), then:
```bash
chmod +x init-letsencrypt.sh
./init-letsencrypt.sh
```
This issues real Let's Encrypt certs for `graminpanseva.in` + `www`, starts Nginx,
backend, MongoDB and the auto-renew certbot loop.

➡️ Open **https://graminpanseva.in** — homepage loads, **/login** opens the portal.

---

## Day-2 operations

| Task | Command (run inside `deploy/`) |
|------|--------------------------------|
| View logs | `docker compose logs -f backend` |
| Restart after code pull | `git pull && docker compose build backend && docker compose up -d backend` |
| Stop everything | `docker compose down` |
| Full rebuild | `docker compose up -d --build` |
| Mongo shell | `docker compose exec mongo mongosh gramin_pan_seva` |

SSL auto-renews (certbot container runs `certbot renew` every 12h and Nginx reloads on schedule).

---

## Default admin login (change ADMIN_PASSWORD before deploy!)
- User ID: value of `ADMIN_USER_ID` (default `AD-0001`)
- Password: value of `ADMIN_PASSWORD`

The Super Admin is auto-seeded on first startup, along with demo data and the full
AO-code dataset from `backend/ao_codes.csv`.

---

## Notes / things to wire later (currently MOCKED)
- **Email OTP (SMTP):** OTP is logged in backend logs (and returned as `dev_otp`).
  Configure real SMTP from the Super Admin → settings to send actual emails.
- **Document uploads (FTP):** stored on the backend container disk (`uploads_data` volume),
  served at `/api/uploads/...`. Configure real FTP from settings when ready.

---

## Alternative: run without Docker (systemd + nginx)

1. Install Python 3.11, MongoDB, Nginx on the host.
2. `cd backend && pip install -r ../deploy/requirements.txt`
3. Create `/etc/gramin.env` with the same variables as `.env` (plus `MONGO_URL=mongodb://localhost:27017`, `FRONTEND_DIR=/path/to/frontend/public`).
4. Run with: `uvicorn server:app --host 127.0.0.1 --port 8001` (via a systemd unit, `EnvironmentFile=/etc/gramin.env`).
5. Point Nginx `proxy_pass http://127.0.0.1:8001;` and add SSL with `certbot --nginx -d graminpanseva.in -d www.graminpanseva.in`.
