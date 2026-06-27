"""Regression tests for iteration 4 bug fixes:

BUG 1: Registration form needs Name + Role -> RegisterIn now has name+role; new user is created
       directly in users collection with status Pending (no longer separate registrations row).
BUG 2 & 3: Pending self-registrations show up in their role section (GET /api/users?role=X
           returns Active+Pending+Blocked+Rejected); new endpoint GET /api/users/{id} for full detail.
BUG 4: New endpoints POST /api/users/{id}/approve and /reject for pending lifecycle.
       PAN review now stores receipt_path so frontend Download Receipt can open the file.
REGRESSION: admin login, list endpoints, admin Add User.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USER = "ADMIN"
ADMIN_PASSWORD = "Bakkar@111"
RETAILER_USER = "RT10234"
RETAILER_PASSWORD = "Password@123"


def _login(uid, pw):
    return requests.post(f"{API}/auth/login", json={"user_id": uid, "password": pw}, timeout=30)


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def admin_token():
    r = _login(ADMIN_USER, ADMIN_PASSWORD)
    assert r.status_code == 200, f"admin login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def retailer_token():
    r = _login(RETAILER_USER, RETAILER_PASSWORD)
    assert r.status_code == 200, f"retailer login failed: {r.text}"
    return r.json()["token"]


def _register_pending(role_label, name_prefix="TEST"):
    """Helper: create a new pending self-registration with the given role label."""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register/send-otp", json={"email": email}, timeout=30)
    assert r.status_code == 200
    otp = r.json().get("dev_otp")
    assert otp, "dev_otp missing"
    payload = {
        "name": f"{name_prefix} {role_label} {uuid.uuid4().hex[:4]}",
        "role": role_label,
        "aadhaar": "123412341234",
        "pan": f"ABCDE{uuid.uuid4().hex[:4].upper()}Z",
        "mobile": "9876543210",
        "email": email,
        "otp": otp,
        "password": "Password@123",
        "shop_name": f"{name_prefix} Shop",
        "address": "TEST Addr",
    }
    rr = requests.post(f"{API}/auth/register", json=payload, timeout=30)
    assert rr.status_code == 200, rr.text
    return rr.json(), payload


# ============================ BUG 1: Register creates Pending user with role+name ============================
class TestRegistrationCreatesPendingUser:
    def test_register_distributor_returns_dt_code(self, admin_token):
        body, payload = _register_pending("Distributor")
        ref = body.get("reference_id", "")
        assert body.get("status") == "Pending"
        assert ref.startswith("DT"), f"Expected DT#### code, got {ref}"
        # Confirm the new pending user is visible in role=distributor list
        rows = requests.get(f"{API}/users", params={"role": "distributor"},
                            headers=_auth(admin_token), timeout=30)
        assert rows.status_code == 200
        codes = [u.get("user_code") for u in rows.json()]
        assert ref in codes, "newly registered DT not in distributor list"
        statuses = {u["user_code"]: u.get("status") for u in rows.json()}
        assert statuses[ref] == "Pending"

    def test_register_superdistributor_returns_sd_code(self, admin_token):
        body, _ = _register_pending("Super Distributor")
        ref = body.get("reference_id", "")
        assert ref.startswith("SD"), f"Expected SD#### code, got {ref}"
        rows = requests.get(f"{API}/users", params={"role": "superdistributor"},
                            headers=_auth(admin_token), timeout=30)
        codes = [u.get("user_code") for u in rows.json()]
        assert ref in codes

    def test_register_retailer_returns_rt_code(self, admin_token):
        body, _ = _register_pending("Retailer")
        ref = body.get("reference_id", "")
        assert ref.startswith("RT"), f"Expected RT#### code, got {ref}"

    def test_pending_user_cannot_login(self):
        body, payload = _register_pending("Distributor")
        r = _login(body["reference_id"], payload["password"])
        assert r.status_code == 403, "pending user should not be able to log in"

    def test_duplicate_email_rejected(self):
        body, payload = _register_pending("Retailer")
        # Try registering again with same email — should hit "Email already registered" after OTP
        email = payload["email"]
        r = requests.post(f"{API}/auth/register/send-otp", json={"email": email}, timeout=30)
        otp = r.json().get("dev_otp")
        payload2 = {**payload, "otp": otp, "pan": f"ZZZZZ{uuid.uuid4().hex[:4].upper()}Z"}
        rr = requests.post(f"{API}/auth/register", json=payload2, timeout=30)
        assert rr.status_code == 400


# ============================ BUG 2/3: GET /api/users/{id} full detail ============================
class TestUserDetailEndpoint:
    def test_user_detail_returns_full_fields(self, admin_token):
        body, payload = _register_pending("Retailer")
        # find the new user id from list
        rows = requests.get(f"{API}/users", params={"role": "retailer"},
                            headers=_auth(admin_token), timeout=30).json()
        match = [u for u in rows if u["user_code"] == body["reference_id"]]
        assert match, "user not in role list"
        uid = match[0]["id"]

        r = requests.get(f"{API}/users/{uid}", headers=_auth(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for key in ("user_code", "name", "role", "status", "mobile", "email",
                    "aadhaar", "pan", "shop_name", "address", "wallet"):
            assert key in d, f"missing {key}"
        assert d["status"] == "Pending"
        assert d["aadhaar"] == payload["aadhaar"]
        assert d["pan"] == payload["pan"].upper()
        assert d["name"] == payload["name"]
        assert d["self_registered"] is True

    def test_user_detail_404(self, admin_token):
        r = requests.get(f"{API}/users/does-not-exist", headers=_auth(admin_token), timeout=30)
        assert r.status_code == 404

    def test_user_detail_requires_auth(self):
        r = requests.get(f"{API}/users/abc", timeout=30)
        assert r.status_code in (401, 403)


# ============================ BUG 3: Approve / Reject ============================
class TestApproveRejectFlow:
    def test_approve_pending_user_makes_login_work(self):
        body, payload = _register_pending("Distributor", name_prefix="TEST_APR")
        admin_token = _login(ADMIN_USER, ADMIN_PASSWORD).json()["token"]

        rows = requests.get(f"{API}/users", params={"role": "distributor"},
                            headers=_auth(admin_token), timeout=30).json()
        match = [u for u in rows if u["user_code"] == body["reference_id"]]
        assert match
        uid = match[0]["id"]

        r = requests.post(f"{API}/users/{uid}/approve", headers=_auth(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "Active"

        # Verify via GET /users/{id}
        detail = requests.get(f"{API}/users/{uid}", headers=_auth(admin_token), timeout=30).json()
        assert detail["status"] == "Active"

        # Now login should succeed
        lg = _login(body["reference_id"], payload["password"])
        assert lg.status_code == 200, f"Approved user should login: {lg.text}"

        # cleanup
        requests.delete(f"{API}/users/{uid}", headers=_auth(admin_token), timeout=30)

    def test_reject_pending_user_sets_rejected_status(self):
        body, _ = _register_pending("Retailer", name_prefix="TEST_REJ")
        admin_token = _login(ADMIN_USER, ADMIN_PASSWORD).json()["token"]
        rows = requests.get(f"{API}/users", params={"role": "retailer"},
                            headers=_auth(admin_token), timeout=30).json()
        match = [u for u in rows if u["user_code"] == body["reference_id"]]
        uid = match[0]["id"]

        r = requests.post(f"{API}/users/{uid}/reject", headers=_auth(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "Rejected"

        # rejected user appears in list (admin must see)
        rows2 = requests.get(f"{API}/users", params={"role": "retailer"},
                             headers=_auth(admin_token), timeout=30).json()
        statuses = {u["user_code"]: u["status"] for u in rows2}
        assert statuses.get(body["reference_id"]) == "Rejected"

        # cleanup
        requests.delete(f"{API}/users/{uid}", headers=_auth(admin_token), timeout=30)

    def test_approve_requires_auth(self):
        r = requests.post(f"{API}/users/abc/approve", timeout=30)
        assert r.status_code in (401, 403)


# ============================ BUG 4: PAN review receipt_path stored ============================
class TestPanReviewReceiptPath:
    def test_pan_review_stores_receipt_path(self, retailer_token, admin_token):
        # Submit a PAN
        payload = {"type": "New PAN", "applicant_name": "TEST RcptApp"}
        r = requests.post(f"{API}/pan-applications", json=payload,
                          headers=_auth(retailer_token), timeout=30)
        if r.status_code == 400 and "Insufficient" in r.text:
            pytest.skip("retailer wallet too low for PAN test")
        assert r.status_code == 200, r.text
        app = r.json()["application"]
        app_id = app["app_id"]

        # Upload a receipt png
        files = {"file": ("rcpt.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")}
        u = requests.post(f"{API}/uploads", files=files, headers=_auth(admin_token), timeout=30)
        assert u.status_code == 200, u.text
        rcpt_url = u.json()["url"]

        # Review (Approved) with receipt
        rev = requests.post(
            f"{API}/pan-applications/{app_id}/review",
            json={"action": "Approved", "receipt_name": "rcpt.png", "receipt_path": rcpt_url},
            headers=_auth(admin_token), timeout=30,
        )
        assert rev.status_code == 200, rev.text

        # Pull list and verify receipt_path
        ls = requests.get(f"{API}/pan-applications", headers=_auth(admin_token), timeout=30)
        assert ls.status_code == 200
        match = [a for a in ls.json() if a.get("app_id") == app_id]
        assert match
        assert match[0].get("receipt_path") == rcpt_url
        assert match[0].get("receipt_name") == "rcpt.png"
        assert match[0].get("status") == "Approved"


# ============================ REGRESSION ============================
class TestRegression:
    def test_admin_login_works(self):
        r = _login(ADMIN_USER, ADMIN_PASSWORD)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "superadmin"

    def test_admin_add_user_creates_active_retailer(self, admin_token):
        email = f"test_addu_{uuid.uuid4().hex[:8]}@example.com"
        payload = {"name": "TEST AddU", "mobile": "9876543210",
                   "email": email, "role": "retailer"}
        r = requests.post(f"{API}/users", json=payload, headers=_auth(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        u = d["user"]
        assert u["user_code"].startswith("RT")
        assert u["status"] == "Active"

        # cleanup
        requests.delete(f"{API}/users/{u['id']}", headers=_auth(admin_token), timeout=30)

    def test_settings_get_works(self, admin_token):
        r = requests.get(f"{API}/settings", headers=_auth(admin_token), timeout=30)
        assert r.status_code == 200
        assert "smtp" in r.json()

    def test_dashboard_stats_works(self, admin_token):
        r = requests.get(f"{API}/dashboard/stats", headers=_auth(admin_token), timeout=30)
        assert r.status_code == 200
