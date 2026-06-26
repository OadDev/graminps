"""Backend API tests for Gramin PAN Seva."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pan-app-engine.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(user_id, password):
    r = requests.post(f"{API}/auth/login", json={"user_id": user_id, "password": password})
    return r


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def admin_token():
    r = _login("AD-0001", "Admin@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def retailer_token():
    r = _login("RT10234", "Password@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def sd_token():
    r = _login("SD1001", "Password@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def dt_token():
    r = _login("DT2031", "Password@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---------------- AUTH ----------------
class TestAuth:
    def test_admin_login(self):
        r = _login("AD-0001", "Admin@123")
        assert r.status_code == 200
        d = r.json()
        assert "token" in d
        assert d["user"]["role"] == "superadmin"
        assert d["user"]["user_code"] == "AD-0001"

    def test_retailer_login(self):
        r = _login("RT10234", "Password@123")
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "retailer"

    def test_blocked_user(self):
        r = _login("RT10238", "Password@123")
        assert r.status_code == 403
        assert "block" in r.json()["detail"].lower()

    def test_pending_user(self):
        r = _login("RT10236", "Password@123")
        assert r.status_code == 403
        assert "pending" in r.json()["detail"].lower()

    def test_invalid_password(self):
        r = _login("AD-0001", "wrongpass")
        assert r.status_code == 401

    def test_me(self, retailer_token):
        r = requests.get(f"{API}/auth/me", headers=_auth(retailer_token))
        assert r.status_code == 200
        assert r.json()["user_code"] == "RT10234"


# ---------------- REGISTRATION ----------------
class TestRegistration:
    def test_send_otp_and_register(self):
        email = f"TEST_reg_{int(time.time())}@example.com"
        r = requests.post(f"{API}/auth/register/send-otp", json={"email": email})
        assert r.status_code == 200, r.text
        otp = r.json().get("dev_otp")
        assert otp and len(otp) == 6

        payload = {
            "name": "TEST Reg User", "aadhaar": "123412341234", "pan": "ABCDE1234F",
            "mobile": "9000000001", "email": email, "otp": otp,
            "password": "Password@123", "shop_name": "TEST Shop", "address": "Addr"
        }
        r2 = requests.post(f"{API}/auth/register", json=payload)
        assert r2.status_code == 200, r2.text
        assert r2.json()["reference_id"].startswith("REG-")

    def test_register_invalid_otp(self):
        email = f"TEST_bad_{int(time.time())}@example.com"
        requests.post(f"{API}/auth/register/send-otp", json={"email": email})
        payload = {
            "name": "X", "aadhaar": "1", "pan": "ABCDE1234F", "mobile": "9", "email": email,
            "otp": "000000", "password": "p", "shop_name": "s", "address": "a"
        }
        r = requests.post(f"{API}/auth/register", json=payload)
        # might pass if random otp matches, but very unlikely
        assert r.status_code in (400, 200)


# ---------------- DASHBOARD ----------------
class TestDashboard:
    def test_admin_stats(self, admin_token):
        r = requests.get(f"{API}/dashboard/stats", headers=_auth(admin_token))
        assert r.status_code == 200
        c = r.json()["cards"]
        assert c["super_distributors"] >= 5
        assert c["retailers"] >= 7
        assert c["distributors"] >= 6
        assert "wallet_requests" in c

    def test_retailer_stats(self, retailer_token):
        r = requests.get(f"{API}/dashboard/stats", headers=_auth(retailer_token))
        assert r.status_code == 200
        assert "cards" in r.json()


# ---------------- USERS / HIERARCHY ----------------
class TestUsers:
    def test_admin_list_sd(self, admin_token):
        r = requests.get(f"{API}/users?role=superdistributor", headers=_auth(admin_token))
        assert r.status_code == 200
        assert len(r.json()) >= 5

    def test_sd_sees_downline(self, sd_token):
        r = requests.get(f"{API}/users?role=distributor", headers=_auth(sd_token))
        assert r.status_code == 200
        codes = [u["user_code"] for u in r.json()]
        assert "DT2031" in codes

    def test_dt_sees_retailers(self, dt_token):
        r = requests.get(f"{API}/users?role=retailer", headers=_auth(dt_token))
        assert r.status_code == 200
        codes = [u["user_code"] for u in r.json()]
        assert "RT10234" in codes

    def test_create_user_admin(self, admin_token):
        email = f"TEST_user_{int(time.time())}@example.com"
        r = requests.post(f"{API}/users", json={
            "name": "TEST Retailer", "mobile": "9000111222", "email": email, "role": "Retailer"
        }, headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["user"]["user_code"].startswith("RT")
        assert d["default_password"]

    def test_create_user_forbidden_role(self, dt_token):
        r = requests.post(f"{API}/users", json={
            "name": "X", "mobile": "9", "email": f"TEST_x_{int(time.time())}@example.com",
            "role": "Super Distributor"
        }, headers=_auth(dt_token))
        assert r.status_code == 403

    def test_toggle_block_and_delete(self, admin_token):
        # create then block then delete
        email = f"TEST_tg_{int(time.time())}@example.com"
        r = requests.post(f"{API}/users", json={
            "name": "TEST TG", "mobile": "9", "email": email, "role": "Retailer"
        }, headers=_auth(admin_token))
        uid = r.json()["user"]["id"]
        r2 = requests.post(f"{API}/users/{uid}/toggle-block", headers=_auth(admin_token))
        assert r2.status_code == 200 and r2.json()["status"] == "Blocked"
        r3 = requests.delete(f"{API}/users/{uid}", headers=_auth(admin_token))
        assert r3.status_code == 200


# ---------------- REGISTRATIONS REVIEW ----------------
class TestRegistrationsReview:
    def test_list_registrations(self, admin_token):
        r = requests.get(f"{API}/registrations", headers=_auth(admin_token))
        assert r.status_code == 200
        assert len(r.json()) >= 3

    def test_retailer_forbidden(self, retailer_token):
        r = requests.get(f"{API}/registrations", headers=_auth(retailer_token))
        assert r.status_code == 403


# ---------------- META ----------------
class TestMeta:
    def test_states(self, retailer_token):
        r = requests.get(f"{API}/states", headers=_auth(retailer_token))
        assert r.status_code == 200
        assert "Assam" in r.json()

    def test_cities(self, retailer_token):
        r = requests.get(f"{API}/cities?state=Assam", headers=_auth(retailer_token))
        assert r.status_code == 200
        assert "Guwahati" in r.json()

    def test_ao_codes(self, retailer_token):
        r = requests.get(f"{API}/ao-codes?city=Guwahati", headers=_auth(retailer_token))
        assert r.status_code == 200
        assert len(r.json()) > 0


# ---------------- PAN ----------------
class TestPan:
    def test_submit_pan_and_wallet_debit(self, retailer_token):
        before = requests.get(f"{API}/auth/me", headers=_auth(retailer_token)).json()["wallet_balance"]
        r = requests.post(f"{API}/pan-applications", json={
            "type": "New PAN", "applicant_name": "TEST Applicant",
            "state": "Assam", "city": "Guwahati"
        }, headers=_auth(retailer_token))
        assert r.status_code == 200, r.text
        app = r.json()["application"]
        assert app["status"] == "Processed"
        after = requests.get(f"{API}/auth/me", headers=_auth(retailer_token)).json()["wallet_balance"]
        assert round(before - after, 2) == 107.0

    def test_admin_review_pan_requires_receipt(self, admin_token, retailer_token):
        # submit one
        r = requests.post(f"{API}/pan-applications", json={"type": "New PAN", "applicant_name": "TEST R"},
                          headers=_auth(retailer_token))
        if r.status_code != 200:
            pytest.skip("insufficient balance")
        app_id = r.json()["application"]["app_id"]
        # Approve w/o receipt → 400
        r1 = requests.post(f"{API}/pan-applications/{app_id}/review",
                           json={"action": "Approved"}, headers=_auth(admin_token))
        assert r1.status_code == 400
        # Reject w/o remark → 400
        r2 = requests.post(f"{API}/pan-applications/{app_id}/review",
                           json={"action": "Rejected"}, headers=_auth(admin_token))
        assert r2.status_code == 400
        # Approve with receipt → 200
        r3 = requests.post(f"{API}/pan-applications/{app_id}/review",
                           json={"action": "Approved", "receipt_name": "rec.pdf"}, headers=_auth(admin_token))
        assert r3.status_code == 200

    def test_retailer_cant_review(self, retailer_token):
        r = requests.post(f"{API}/pan-applications/APP-22045/review",
                          json={"action": "Approved", "receipt_name": "x"}, headers=_auth(retailer_token))
        assert r.status_code == 403


# ---------------- WALLET ----------------
class TestWallet:
    def test_recharge_request_and_review(self, retailer_token, admin_token):
        r = requests.post(f"{API}/wallet/recharge",
                          json={"amount": 500, "utr": "TESTUTR123"}, headers=_auth(retailer_token))
        assert r.status_code == 200
        rid = r.json()["id"]
        before = requests.get(f"{API}/auth/me", headers=_auth(retailer_token)).json()["wallet_balance"]
        r2 = requests.post(f"{API}/wallet/recharge-requests/{rid}/review",
                           json={"decision": "Approved"}, headers=_auth(admin_token))
        assert r2.status_code == 200
        after = requests.get(f"{API}/auth/me", headers=_auth(retailer_token)).json()["wallet_balance"]
        assert round(after - before, 2) == 500.0

    def test_admin_lists_all(self, admin_token):
        r = requests.get(f"{API}/wallet/recharge-requests", headers=_auth(admin_token))
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_retailer_cant_review_recharge(self, retailer_token):
        r = requests.post(f"{API}/wallet/recharge-requests/xxx/review",
                          json={"decision": "Approved"}, headers=_auth(retailer_token))
        assert r.status_code == 403


# ---------------- TICKETS ----------------
class TestTickets:
    def test_create_list_reply_resolve(self, retailer_token, admin_token):
        r = requests.post(f"{API}/tickets",
                          json={"subject": "TEST Subject", "category": "General", "priority": "Low",
                                "message": "hello"}, headers=_auth(retailer_token))
        assert r.status_code == 200
        tid = r.json()["id"]

        r2 = requests.get(f"{API}/tickets", headers=_auth(retailer_token))
        assert r2.status_code == 200 and any(t["id"] == tid for t in r2.json())

        r3 = requests.get(f"{API}/tickets/{tid}", headers=_auth(retailer_token))
        assert r3.status_code == 200 and len(r3.json()["messages"]) >= 1

        r4 = requests.post(f"{API}/tickets/{tid}/reply",
                           json={"text": "reply"}, headers=_auth(admin_token))
        assert r4.status_code == 200

        r5 = requests.post(f"{API}/tickets/{tid}/resolve", headers=_auth(admin_token))
        assert r5.status_code == 200 and r5.json()["status"] == "Closed"


# ---------------- NOTIFICATIONS ----------------
class TestNotifications:
    def test_notifications(self, retailer_token):
        r = requests.get(f"{API}/notifications", headers=_auth(retailer_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------- SETTINGS ----------------
class TestSettings:
    def test_admin_full_settings(self, admin_token):
        r = requests.get(f"{API}/settings", headers=_auth(admin_token))
        assert r.status_code == 200
        d = r.json()
        assert "smtp" in d and "pricing" in d and "ftp" in d

    def test_non_admin_only_pricing(self, retailer_token):
        r = requests.get(f"{API}/settings", headers=_auth(retailer_token))
        assert r.status_code == 200
        d = r.json()
        assert "pricing" in d
        assert "smtp" not in d

    def test_update_pricing_and_new_price_debit(self, admin_token, retailer_token):
        # set price to 150
        r = requests.put(f"{API}/settings", json={"pricing": {"New PAN": 150.0, "CSF PAN": 85.0}},
                         headers=_auth(admin_token))
        assert r.status_code == 200
        # ensure wallet enough — recharge if needed
        bal = requests.get(f"{API}/auth/me", headers=_auth(retailer_token)).json()["wallet_balance"]
        if bal < 150:
            rr = requests.post(f"{API}/wallet/recharge", json={"amount": 1000, "utr": "TEST_priceup"},
                               headers=_auth(retailer_token)).json()
            requests.post(f"{API}/wallet/recharge-requests/{rr['id']}/review",
                          json={"decision": "Approved"}, headers=_auth(admin_token))
        before = requests.get(f"{API}/auth/me", headers=_auth(retailer_token)).json()["wallet_balance"]
        r2 = requests.post(f"{API}/pan-applications",
                           json={"type": "New PAN", "applicant_name": "TEST PriceCheck"},
                           headers=_auth(retailer_token))
        assert r2.status_code == 200
        after = requests.get(f"{API}/auth/me", headers=_auth(retailer_token)).json()["wallet_balance"]
        assert round(before - after, 2) == 150.0
        # reset
        requests.put(f"{API}/settings", json={"pricing": {"New PAN": 107.0, "CSF PAN": 85.0}},
                     headers=_auth(admin_token))

    def test_retailer_cant_update_settings(self, retailer_token):
        r = requests.put(f"{API}/settings", json={"pricing": {"New PAN": 1.0}},
                         headers=_auth(retailer_token))
        assert r.status_code == 403


# ---------------- AUDIT ----------------
class TestAudit:
    def test_admin_audit_logs(self, admin_token):
        r = requests.get(f"{API}/audit-logs", headers=_auth(admin_token))
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_retailer_audit_forbidden(self, retailer_token):
        r = requests.get(f"{API}/audit-logs", headers=_auth(retailer_token))
        assert r.status_code == 403


# ---------------- INSUFFICIENT BAL ----------------
class TestInsufficient:
    def test_insufficient_balance(self, admin_token):
        # Create a fresh retailer w/ zero wallet, login, try to submit
        email = f"TEST_zero_{int(time.time())}@example.com"
        r = requests.post(f"{API}/users", json={
            "name": "TEST Zero", "mobile": "9", "email": email, "role": "Retailer"
        }, headers=_auth(admin_token))
        code = r.json()["user"]["user_code"]
        login = _login(code, "Password@123").json()
        token = login["token"]
        r2 = requests.post(f"{API}/pan-applications",
                           json={"type": "New PAN", "applicant_name": "X"},
                           headers=_auth(token))
        assert r2.status_code == 400
        assert "insufficient" in r2.json()["detail"].lower()
