"""Iteration-6 backend tests:
- Super Admin cannot submit PAN or recharge (403)
- Retailer CAN submit recharge (200)
- Admin can save/get UPI settings
- Retailer GET /settings returns pricing+upi, no smtp/ftp secrets
- Retailer CSF submit: 200 or 400 insufficient-balance (both acceptable)
"""
import os
import time
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"


def _login(uid, pw):
    return requests.post(f"{API}/auth/login", json={"user_id": uid, "password": pw}, timeout=20)


def _h(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="session")
def admin_token():
    r = _login("ADMIN", "Bakkar@111")
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def retailer_token():
    r = _login("RT10234", "Password@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---- Admin restrictions ----
class TestAdminRestrictions:
    def test_admin_pan_submit_forbidden(self, admin_token):
        r = requests.post(f"{API}/pan-applications", json={
            "type": "New PAN", "applicant_name": "TEST_AdminBlocked"
        }, headers=_h(admin_token))
        assert r.status_code == 403, r.text
        body = r.json()
        msg = (body.get("detail") or "").lower()
        assert "admin" in msg or "forbidden" in msg or "not allowed" in msg or "cannot" in msg

    def test_admin_recharge_submit_forbidden(self, admin_token):
        r = requests.post(f"{API}/wallet/recharge",
                          json={"amount": 100, "utr": "TEST_ADMIN_UTR"}, headers=_h(admin_token))
        assert r.status_code == 403, r.text


# ---- Retailer recharge ----
class TestRetailerRecharge:
    def test_retailer_can_submit_recharge(self, retailer_token):
        r = requests.post(f"{API}/wallet/recharge",
                          json={"amount": 250, "utr": f"TEST_UTR_{int(time.time())}"},
                          headers=_h(retailer_token))
        assert r.status_code == 200, r.text
        d = r.json()
        assert "id" in d


# ---- UPI settings ----
class TestUpiSettings:
    def test_admin_save_and_get_upi(self, admin_token):
        upi_payload = {
            "upi": {
                "upi_id": "graminpan@upi",
                "payee_name": "Gramin PAN Seva",
                "qr_path": ""
            }
        }
        r = requests.put(f"{API}/settings", json=upi_payload, headers=_h(admin_token))
        assert r.status_code == 200, r.text

        r2 = requests.get(f"{API}/settings", headers=_h(admin_token))
        assert r2.status_code == 200
        d = r2.json()
        assert "upi" in d, f"UPI missing in admin settings: {d.keys()}"
        assert d["upi"].get("upi_id") == "graminpan@upi"
        assert d["upi"].get("payee_name") == "Gramin PAN Seva"

    def test_retailer_sees_upi_no_secrets(self, retailer_token):
        r = requests.get(f"{API}/settings", headers=_h(retailer_token))
        assert r.status_code == 200, r.text
        d = r.json()
        assert "pricing" in d
        assert "upi" in d, f"Retailer settings missing upi: {d.keys()}"
        assert d["upi"].get("upi_id") == "graminpan@upi"
        # secrets must not leak
        assert "smtp" not in d
        assert "ftp" not in d


# ---- CSF retailer submit ----
class TestCsfSubmit:
    def test_retailer_csf_submit(self, retailer_token):
        payload = {
            "type": "CSF PAN",
            "applicant_name": "TEST CSF Applicant",
            "state": "Assam",
            "city": "Guwahati",
            "form_data": {
                "pan_number": "ABCDE1234F",
                "father_name": "TEST Father",
                "mother_name": "TEST Mother",
                "dob": "1990-01-01",
                "gender": "Male",
                "address_line1": "Addr 1",
                "ao_code": {"area_code": "GUW", "ao_type": "W", "range_code": "1", "ao_number": "1"},
                "num_documents": 2,
                "corrections": ["Full Name", "Date of Birth"]
            }
        }
        r = requests.post(f"{API}/pan-applications", json=payload, headers=_h(retailer_token))
        assert r.status_code in (200, 400), r.text
        if r.status_code == 400:
            assert "insufficient" in r.json().get("detail", "").lower()
        else:
            app = r.json().get("application", {})
            assert app.get("type") == "CSF PAN"
