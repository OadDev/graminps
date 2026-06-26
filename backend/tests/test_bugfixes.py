"""Regression tests for the two reported bugs:
  BUG 1: Email OTP must work (real SMTP if configured, dev_otp fallback otherwise)
  BUG 2: POST /api/uploads must accept retailer-auth file uploads, reject unauth + bad extensions
Plus regression for: settings persistence (partial update), tickets role gating, PAN-with-docs.
"""
import os
import io
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pan-app-engine.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(uid, pw):
    return requests.post(f"{API}/auth/login", json={"user_id": uid, "password": pw}, timeout=30)


@pytest.fixture(scope="module")
def admin_token():
    r = _login("AD-0001", "Admin@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def retailer_token():
    r = _login("RT10234", "Password@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


# ============================ BUG 1: OTP ============================
class TestOtpRegistration:
    def test_send_otp_returns_dev_otp_fallback(self):
        email = f"test_otp_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/register/send-otp", json={"email": email}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("sent") is True
        # SMTP not configured/invalid -> emailed False and dev_otp returned
        assert "emailed" in d
        if not d["emailed"]:
            assert "dev_otp" in d
            assert len(d["dev_otp"]) == 6
            assert d["dev_otp"].isdigit()

    def test_register_with_valid_otp_succeeds(self, admin_token):
        email = f"test_reg_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/register/send-otp", json={"email": email}, timeout=30)
        assert r.status_code == 200
        dev_otp = r.json().get("dev_otp")
        assert dev_otp, "Expected dev_otp fallback when SMTP not configured"

        payload = {
            "name": "TEST OTP User",
            "aadhaar": "123456789012",
            "pan": f"ABCDE{uuid.uuid4().hex[:4].upper()}Z",
            "mobile": "9876543210",
            "email": email,
            "password": "Password@123",
            "shop_name": "TEST Shop",
            "address": "TEST Address, Guwahati",
            "otp": dev_otp,
        }
        rr = requests.post(f"{API}/auth/register", json=payload, timeout=30)
        assert rr.status_code == 200, rr.text
        body = rr.json()
        assert body.get("status") == "Pending"
        assert body.get("reference_id", "").startswith("REG-")
        reg_id = body["reference_id"]

        # Verify registration appears in admin GET /api/registrations
        regs = requests.get(f"{API}/registrations", headers=_auth(admin_token), timeout=30)
        assert regs.status_code == 200
        ids = [x.get("reg_id") for x in regs.json()]
        assert reg_id in ids

    def test_register_with_wrong_otp_returns_400(self):
        email = f"test_bad_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/register/send-otp", json={"email": email}, timeout=30)
        assert r.status_code == 200
        payload = {
            "name": "TEST Bad", "aadhaar": "123456789012",
            "pan": f"BBBBB{uuid.uuid4().hex[:4].upper()}Z", "mobile": "9876543210",
            "email": email, "password": "Password@123", "shop_name": "TEST",
            "address": "x", "otp": "000001" if r.json().get("dev_otp") != "000001" else "999998",
        }
        rr = requests.post(f"{API}/auth/register", json=payload, timeout=30)
        assert rr.status_code == 400


# ============================ BUG 2: UPLOADS ============================
class TestUploads:
    def test_upload_without_auth_returns_401(self):
        files = {"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")}
        r = requests.post(f"{API}/uploads", files=files, timeout=30)
        assert r.status_code in (401, 403), r.text

    def test_upload_png_as_retailer(self, retailer_token):
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 128
        files = {"file": ("aadhaar.png", png_bytes, "image/png")}
        r = requests.post(f"{API}/uploads", files=files, headers=_auth(retailer_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("filename") == "aadhaar.png"
        assert d.get("storage") == "local"
        assert d.get("url", "").startswith("/api/uploads/")
        assert d.get("path", "").startswith("/api/uploads/")

    def test_upload_rejects_unsupported_extension(self, retailer_token):
        files = {"file": ("evil.csv", b"a,b\n1,2", "text/csv")}
        r = requests.post(f"{API}/uploads", files=files, headers=_auth(retailer_token), timeout=30)
        assert r.status_code == 400, r.text

    def test_upload_rejects_txt(self, retailer_token):
        files = {"file": ("note.txt", b"hello", "text/plain")}
        r = requests.post(f"{API}/uploads", files=files, headers=_auth(retailer_token), timeout=30)
        assert r.status_code == 400


# ============================ PAN SUBMIT WITH DOCS ============================
class TestPanWithDocs:
    def test_pan_submit_with_uploaded_docs_debits_wallet(self, retailer_token):
        # 1. upload an aadhaar_front doc
        files = {"file": ("front.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")}
        u = requests.post(f"{API}/uploads", files=files, headers=_auth(retailer_token), timeout=30)
        assert u.status_code == 200
        doc_url = u.json()["url"]

        # 2. get wallet balance + new-pan price
        me = requests.get(f"{API}/auth/me", headers=_auth(retailer_token), timeout=30)
        assert me.status_code == 200
        wallet_before = me.json().get("wallet_balance", 0)

        s = requests.get(f"{API}/settings", headers=_auth(retailer_token), timeout=30)
        # settings may be admin-only — fall back to known price
        if s.status_code != 200:
            price = None
        else:
            price = (s.json().get("pricing") or {}).get("new_pan") or (s.json().get("pricing") or {}).get("New PAN")

        # 3. submit a PAN application with documents
        payload = {
            "type": "New PAN",
            "applicant_name": "TEST Applicant",
            "form_data": {
                "name": "TEST Applicant",
                "documents": {
                    "aadhaar_front": doc_url,
                }
            },
        }
        r = requests.post(f"{API}/pan-applications", json=payload, headers=_auth(retailer_token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        app = body.get("application", body)
        assert app.get("type") == "New PAN"
        assert (app.get("form_data") or {}).get("documents", {}).get("aadhaar_front") == doc_url

        # 4. verify wallet debited
        me2 = requests.get(f"{API}/auth/me", headers=_auth(retailer_token), timeout=30)
        wallet_after = me2.json().get("wallet_balance", 0)
        assert wallet_after < wallet_before, f"Wallet not debited: before={wallet_before} after={wallet_after}"

        # 5. verify visible in PAN status list
        ls = requests.get(f"{API}/pan-applications", headers=_auth(retailer_token), timeout=30)
        assert ls.status_code == 200
        assert any(a.get("id") == app.get("id") for a in ls.json())


# ============================ SETTINGS partial update ============================
class TestSettingsPersistence:
    def test_get_settings(self, admin_token):
        r = requests.get(f"{API}/settings", headers=_auth(admin_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "smtp" in d
        assert "ftp" in d
        assert "pricing" in d

    def test_put_ftp_only_does_not_wipe_smtp(self, admin_token):
        # snapshot smtp first
        before = requests.get(f"{API}/settings", headers=_auth(admin_token), timeout=30).json()
        smtp_before = dict(before.get("smtp") or {})

        ftp_cfg = {"host": "ftp.example.com", "port": 21, "base_path": "/uploads",
                   "username": "u", "password": "p"}
        pr = requests.put(f"{API}/settings", json={"ftp": ftp_cfg},
                          headers=_auth(admin_token), timeout=30)
        assert pr.status_code in (200, 204), pr.text

        after = requests.get(f"{API}/settings", headers=_auth(admin_token), timeout=30).json()
        # FTP fields saved
        for k in ("host", "port", "base_path", "username"):
            assert (after.get("ftp") or {}).get(k) == ftp_cfg[k], f"ftp.{k} not saved"
        # SMTP keys preserved
        for k in (smtp_before.keys()):
            assert (after.get("smtp") or {}).get(k) == smtp_before[k], f"smtp.{k} got wiped"


# ============================ TICKETS regression ============================
class TestTickets:
    def test_admin_cannot_create_ticket(self, admin_token):
        r = requests.post(f"{API}/tickets",
                          json={"subject": "TEST admin", "description": "x", "priority": "Low"},
                          headers=_auth(admin_token), timeout=30)
        assert r.status_code == 403, r.text

    def test_retailer_can_create_ticket(self, retailer_token):
        r = requests.post(f"{API}/tickets",
                          json={"subject": "TEST retailer", "description": "x", "priority": "Low"},
                          headers=_auth(retailer_token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        # API returns either the ticket dict or {id, message}
        assert body.get("id") or body.get("subject") == "TEST retailer"
