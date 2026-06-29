"""Iteration-7 backend tests:
- Per-role pricing via PUT /api/settings (nested pricing.{New PAN,CSF PAN}.{role})
- POST /api/wallet/admin-credit: credits + Approved recharge_requests row (utr=ADMIN CREDIT)
- Retailer New PAN charges role-rate (default 107 or configured)
- PUT /api/profile updates name/shop/photo_path
- PAN review with acknowledgement_number stored
- admin POST /api/pan-applications -> 403
"""
import os
import time
import pytest
import requests

def _read_frontend_env():
    try:
        with open('/app/frontend/.env') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL'):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or _read_frontend_env() or '').rstrip('/')
API = f"{BASE_URL}/api"

ADMIN = ("ADMIN", "Bakkar@111")
RETAILER = ("RT10234", "Password@123")


def _login(uid, pwd):
    r = requests.post(f"{API}/auth/login", json={"user_id": uid, "password": pwd}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def retailer_token():
    return _login(*RETAILER)


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- per-role pricing ----------
def test_settings_per_role_pricing(admin_token):
    cur = requests.get(f"{API}/settings", headers=H(admin_token)).json()
    pricing = cur.get("pricing", {})
    # write nested pricing
    new_pricing = {
        "New PAN": {"superdistributor": 100, "distributor": 105, "retailer": 110},
        "CSF PAN": {"superdistributor": 80, "distributor": 82, "retailer": 90},
    }
    r = requests.put(f"{API}/settings", headers=H(admin_token), json={"pricing": new_pricing})
    assert r.status_code == 200, r.text
    # re-read
    after = requests.get(f"{API}/settings", headers=H(admin_token)).json()
    pr = after.get("pricing", {})
    # accept either nested per-role or backend may store as-is
    assert pr.get("New PAN", {}).get("retailer") in (110, 110.0)
    assert pr.get("CSF PAN", {}).get("retailer") in (90, 90.0)


# ---------- admin-credit ----------
def test_admin_credit_creates_approved_recharge(admin_token, retailer_token):
    # Get retailer user id
    users = requests.get(f"{API}/users?role=retailer", headers=H(admin_token)).json()
    target = next((u for u in users if u.get("user_code") == "RT10234"), None)
    assert target, "RT10234 not found"
    me_before = requests.get(f"{API}/auth/me", headers=H(retailer_token)).json()
    bal_before = float(str(me_before.get("wallet_balance", "0")).replace("₹", "").replace(",", "") or 0)

    r = requests.post(f"{API}/wallet/admin-credit", headers=H(admin_token),
                      json={"user_id": target["id"], "amount": 250})
    assert r.status_code == 200, r.text

    me_after = requests.get(f"{API}/auth/me", headers=H(retailer_token)).json()
    bal_after = float(str(me_after.get("wallet_balance", "0")).replace("₹", "").replace(",", "") or 0)
    assert bal_after >= bal_before + 249, f"{bal_before} -> {bal_after}"

    # verify recharge_requests has Approved row with utr ADMIN CREDIT
    hist = requests.get(f"{API}/wallet/recharge-requests", headers=H(retailer_token)).json()
    assert any(h.get("utr") == "ADMIN CREDIT" and h.get("status") == "Approved" for h in hist), hist[:2]


# ---------- retailer New PAN charged role rate ----------
def test_retailer_new_pan_charged_role_rate(admin_token, retailer_token):
    # ensure retailer has enough balance (top up if needed)
    users = requests.get(f"{API}/users?role=retailer", headers=H(admin_token)).json()
    target = next((u for u in users if u.get("user_code") == "RT10234"), None)
    requests.post(f"{API}/wallet/admin-credit", headers=H(admin_token),
                  json={"user_id": target["id"], "amount": 500})

    me_before = requests.get(f"{API}/auth/me", headers=H(retailer_token)).json()
    bal_before = float(str(me_before.get("wallet_balance", "0")).replace("₹", "").replace(",", "") or 0)

    payload = {
        "type": "New PAN",
        "category": "Individual",
        "applicant_type": "Indian Citizen Form 49A",
        "title": "Shri",
        "full_name_aadhaar": "Bikash Kumar Sharma",
        "first_name": "Bikash", "middle_name": "Kumar", "last_name": "Sharma",
        "dob": "1990-01-01",
        "gender": "Male",
        "mobile": "9999999999",
        "email": "x@y.com",
    }
    r = requests.post(f"{API}/pan-applications", headers=H(retailer_token), json=payload)
    assert r.status_code in (200, 201), r.text

    me_after = requests.get(f"{API}/auth/me", headers=H(retailer_token)).json()
    bal_after = float(str(me_after.get("wallet_balance", "0")).replace("₹", "").replace(",", "") or 0)
    delta = bal_before - bal_after
    # expect ~110 (configured) or 107 default
    assert 100 <= delta <= 130, f"unexpected charge {delta}"
    return r.json().get("app_id")


# ---------- profile update ----------
def test_profile_update(retailer_token):
    r = requests.put(f"{API}/profile", headers=H(retailer_token), json={
        "name": "Bikash Updated", "shop_name": "Bikash Shop", "mobile": "9876543210"
    })
    assert r.status_code == 200, r.text
    me = requests.get(f"{API}/auth/me", headers=H(retailer_token)).json()
    assert me.get("name") == "Bikash Updated"


# ---------- acknowledgement_number stored ----------
def test_acknowledgement_in_review(admin_token, retailer_token):
    # create a fresh app
    requests.post(f"{API}/wallet/admin-credit",
                  headers=H(admin_token),
                  json={"user_id": (next(u for u in requests.get(f"{API}/users?role=retailer", headers=H(admin_token)).json() if u.get("user_code") == "RT10234"))["id"], "amount": 300})
    payload = {
        "type": "New PAN", "category": "Individual",
        "applicant_type": "Indian Citizen Form 49A", "title": "Shri",
        "full_name_aadhaar": "Ack Test Person", "first_name": "Ack",
        "middle_name": "Test", "last_name": "Person", "dob": "1990-01-01",
        "gender": "Male", "mobile": "9999999999", "email": "a@b.com",
    }
    cr = requests.post(f"{API}/pan-applications", headers=H(retailer_token), json=payload)
    assert cr.status_code in (200, 201), cr.text
    app_id = cr.json()["application"]["app_id"]

    rv = requests.post(f"{API}/pan-applications/{app_id}/review",
                       headers=H(admin_token),
                       json={"action": "Approved", "acknowledgement_number": "ACK-998877",
                             "receipt_name": "test.pdf", "receipt_path": "/tmp/x.pdf"})
    assert rv.status_code == 200, rv.text

    # fetch list and verify acknowledgement_number stored
    lst = requests.get(f"{API}/pan-applications", headers=H(admin_token)).json()
    target = next((a for a in lst if a.get("app_id") == app_id), None)
    assert target, f"app {app_id} not found in admin list"
    assert target.get("acknowledgement_number") == "ACK-998877", target


# ---------- admin cannot POST pan-applications ----------
def test_admin_cannot_submit_pan(admin_token):
    payload = {"type": "New PAN", "category": "Individual",
               "applicant_type": "Indian Citizen Form 49A", "title": "Shri",
               "full_name_aadhaar": "Admin Try", "first_name": "Admin",
               "middle_name": "", "last_name": "Try", "dob": "1990-01-01",
               "gender": "Male", "mobile": "9999999999", "email": "x@y.com"}
    r = requests.post(f"{API}/pan-applications", headers=H(admin_token), json=payload)
    assert r.status_code == 403, r.text
