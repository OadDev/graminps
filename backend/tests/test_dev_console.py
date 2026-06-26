"""Developer Console tests:
- DEV LOGIN BACKEND: admin/Biki@1626 returns 200+token; wrong creds 401
- DEV AUTH ISOLATION: no token=401, normal user token=403, dev token cannot access admin endpoints
- CHANGE ADMIN CREDS: rotate ADMIN -> TESTADMIN -> ADMIN with verification
- VALIDATION: empty user_id 400, short password 400, collision 400
"""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

DEV_USER = "admin"
DEV_PASS = "Biki@1626"
ADMIN_USER = "ADMIN"
ADMIN_PASS = "Bakkar@111"
RETAILER_USER = "RT10234"
RETAILER_PASS = "Password@123"


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _login(uid, pw):
    return requests.post(f"{API}/auth/login", json={"user_id": uid, "password": pw}, timeout=30)


# ============================ DEV LOGIN ============================
class TestDevLogin:
    def test_dev_login_success(self):
        r = requests.post(f"{API}/dev/login", json={"username": DEV_USER, "password": DEV_PASS}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "token" in d
        assert isinstance(d["token"], str) and len(d["token"]) > 20

    def test_dev_login_wrong_password(self):
        r = requests.post(f"{API}/dev/login", json={"username": DEV_USER, "password": "WRONGPASS"}, timeout=30)
        assert r.status_code == 401

    def test_dev_login_wrong_username(self):
        r = requests.post(f"{API}/dev/login", json={"username": "notadmin", "password": DEV_PASS}, timeout=30)
        assert r.status_code == 401


@pytest.fixture(scope="module")
def dev_token():
    r = requests.post(f"{API}/dev/login", json={"username": DEV_USER, "password": DEV_PASS}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def retailer_token():
    r = _login(RETAILER_USER, RETAILER_PASS)
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ============================ AUTH ISOLATION ============================
class TestDevAuthIsolation:
    def test_get_dev_admin_no_token_401(self):
        r = requests.get(f"{API}/dev/admin", timeout=30)
        assert r.status_code == 401

    def test_get_dev_admin_with_user_token_403(self, retailer_token):
        r = requests.get(f"{API}/dev/admin", headers=_auth(retailer_token), timeout=30)
        assert r.status_code == 403, r.text

    def test_dev_token_cannot_access_admin_endpoint(self, dev_token):
        # Dev token must NOT work on admin-only app endpoints
        r = requests.get(f"{API}/registrations", headers=_auth(dev_token), timeout=30)
        assert r.status_code in (401, 403), r.text

    def test_dev_token_cannot_access_auth_me(self, dev_token):
        # get_current_user does DB lookup on payload.sub which is "__developer__" -> 401 user not found
        r = requests.get(f"{API}/auth/me", headers=_auth(dev_token), timeout=30)
        assert r.status_code in (401, 403)


# ============================ GET ADMIN ============================
class TestDevGetAdmin:
    def test_get_admin_returns_current_user_id(self, dev_token):
        r = requests.get(f"{API}/dev/admin", headers=_auth(dev_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "user_id" in d
        assert "email" in d
        assert "name" in d
        # Current admin should be ADMIN at start (per memory)
        assert d["user_id"] == ADMIN_USER, f"Unexpected admin user_id: {d['user_id']}"


# ============================ VALIDATION ============================
class TestDevValidation:
    def test_empty_user_id_returns_400(self, dev_token):
        r = requests.post(f"{API}/dev/admin", json={"user_id": "", "password": "Goodpass1"},
                          headers=_auth(dev_token), timeout=30)
        assert r.status_code == 400, r.text

    def test_short_password_returns_400(self, dev_token):
        r = requests.post(f"{API}/dev/admin", json={"user_id": "ADMIN", "password": "abc"},
                          headers=_auth(dev_token), timeout=30)
        assert r.status_code == 400, r.text

    def test_collision_with_existing_user_returns_400(self, dev_token):
        r = requests.post(f"{API}/dev/admin", json={"user_id": "RT10234"},
                          headers=_auth(dev_token), timeout=30)
        assert r.status_code == 400, r.text


# ============================ CHANGE ADMIN CREDS (e2e rotation) ============================
class TestChangeAdminCreds:
    """CRITICAL: must restore ADMIN/Bakkar@111 at the end."""

    def test_full_rotation_and_restore(self, dev_token):
        # 0) Verify ADMIN currently works
        r0 = _login(ADMIN_USER, ADMIN_PASS)
        assert r0.status_code == 200, f"Pre-check: ADMIN/Bakkar@111 must work. Got {r0.status_code}: {r0.text}"

        try:
            # 1) Change to TESTADMIN / NewPass@123
            r1 = requests.post(f"{API}/dev/admin",
                               json={"user_id": "TESTADMIN", "password": "NewPass@123"},
                               headers=_auth(dev_token), timeout=30)
            assert r1.status_code == 200, r1.text
            d1 = r1.json()
            assert d1.get("ok") is True
            assert d1.get("user_id") == "TESTADMIN"

            # 2) Verify TESTADMIN/NewPass@123 succeeds and role is superadmin
            r2 = _login("TESTADMIN", "NewPass@123")
            assert r2.status_code == 200, r2.text
            body = r2.json()
            assert body["user"]["role"] == "superadmin"
            assert body["user"]["user_code"] == "TESTADMIN"

            # 3) Verify old ADMIN/Bakkar@111 no longer works
            r3 = _login(ADMIN_USER, ADMIN_PASS)
            assert r3.status_code == 401, f"Old admin login should fail; got {r3.status_code}"

            # 4) Verify GET /dev/admin reflects new id
            r4 = requests.get(f"{API}/dev/admin", headers=_auth(dev_token), timeout=30)
            assert r4.status_code == 200
            assert r4.json()["user_id"] == "TESTADMIN"

        finally:
            # 5) RESTORE: ADMIN/Bakkar@111 regardless of test outcome
            rr = requests.post(f"{API}/dev/admin",
                               json={"user_id": ADMIN_USER, "password": ADMIN_PASS},
                               headers=_auth(dev_token), timeout=30)
            assert rr.status_code == 200, f"RESTORE FAILED: {rr.text}"

        # 6) Verify ADMIN/Bakkar@111 works after restore
        rfinal = _login(ADMIN_USER, ADMIN_PASS)
        assert rfinal.status_code == 200, f"Post-restore: ADMIN/Bakkar@111 must work. Got {rfinal.status_code}"
        assert rfinal.json()["user"]["role"] == "superadmin"


# ============================ REGRESSION ============================
class TestRegression:
    def test_admin_login_still_works(self):
        r = _login(ADMIN_USER, ADMIN_PASS)
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == "superadmin"
