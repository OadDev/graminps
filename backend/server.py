import os
import uuid
import random
import logging
import asyncio
import smtplib
import ssl
import ftplib
import io
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from pymongo import ReturnDocument

from database import db, client
from security import hash_password, verify_password, create_access_token, get_current_user, require_roles
import seed_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("gramin")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Gramin PAN Seva API")
api = APIRouter(prefix="/api")

ROLE_LABEL_TO_KEY = {"Super Distributor": "superdistributor", "Distributor": "distributor", "Retailer": "retailer"}
ROLE_KEY_TO_LABEL = {"superdistributor": "Super Distributor", "distributor": "Distributor", "retailer": "Retailer", "superadmin": "Super Admin"}
CODE_PREFIX = {"superdistributor": "SD", "distributor": "DT", "retailer": "RT"}
# who each role is allowed to create
CREATE_RIGHTS = {
    "superadmin": {"superdistributor", "distributor", "retailer"},
    "superdistributor": {"distributor", "retailer"},
    "distributor": {"retailer"},
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def fmt_inr(v):
    return "\u20b9" + f"{int(round(v)):,}"


def today_str():
    return datetime.now(timezone.utc).strftime("%d %b %Y")


async def get_global_settings() -> dict:
    return await db.settings.find_one({"id": "global"}, {"_id": 0}) or {}


def smtp_is_configured(smtp: dict) -> bool:
    return bool(smtp and smtp.get("host") and smtp.get("username") and smtp.get("password"))


def ftp_is_configured(ftp: dict) -> bool:
    return bool(ftp and ftp.get("host") and ftp.get("username") and ftp.get("password"))


def _send_email_blocking(smtp: dict, to_email: str, subject: str, html_body: str, text_body: str):
    host = smtp["host"]
    port = int(smtp.get("port") or 465)
    user = smtp["username"]
    pwd = smtp["password"]
    from_email = smtp.get("from_email") or user
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as s:
            s.login(user, pwd)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.ehlo()
            s.starttls(context=context)
            s.login(user, pwd)
            s.send_message(msg)


async def send_email(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    settings = await get_global_settings()
    smtp = settings.get("smtp", {})
    if not smtp_is_configured(smtp):
        return False
    try:
        await asyncio.to_thread(_send_email_blocking, smtp, to_email, subject, html_body, text_body)
        return True
    except Exception as e:
        logger.error(f"SMTP send failed: {e}")
        return False


def _ftp_upload_blocking(ftp_cfg: dict, fname: str, data: bytes) -> str:
    host = ftp_cfg["host"]
    port = int(ftp_cfg.get("port") or 21)
    user = ftp_cfg["username"]
    pwd = ftp_cfg["password"]
    base = (ftp_cfg.get("base_path") or "").strip()
    ftp = ftplib.FTP()
    ftp.connect(host, port, timeout=25)
    ftp.login(user, pwd)
    if base:
        for part in [p for p in base.strip("/").split("/") if p]:
            try:
                ftp.cwd(part)
            except ftplib.error_perm:
                ftp.mkd(part)
                ftp.cwd(part)
    ftp.storbinary(f"STOR {fname}", io.BytesIO(data))
    ftp.quit()
    return f"{base.rstrip('/')}/{fname}" if base else f"/{fname}"


async def next_seq(name: str) -> int:
    doc = await db.counters.find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    return doc["seq"]


async def gen_user_code(role: str) -> str:
    return f"{CODE_PREFIX[role]}{await next_seq(role)}"


async def audit(actor: dict, action: str, detail: str):
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()), "actor_id": actor.get("id"), "actor_code": actor.get("user_code"),
        "action": action, "detail": detail, "at": now_iso(),
    })


async def notify(user_id: str, icon: str, bg: str, color: str, title: str, detail: str):
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()), "user_id": user_id, "icon": icon, "bg": bg, "color": color,
        "title": title, "detail": detail, "time": "just now", "read": False, "created_at": now_iso(),
    })


async def apply_wallet(user_id: str, credit: float, debit: float, remarks: str) -> float:
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "wallet_balance": 1})
    bal = float(u.get("wallet_balance", 0)) + credit - debit
    await db.users.update_one({"id": user_id}, {"$set": {"wallet_balance": bal}})
    await db.transactions.insert_one({
        "id": str(uuid.uuid4()), "user_id": user_id, "date": today_str(),
        "txn_id": f"TXN-{await next_seq('txn')}", "credit": float(credit), "debit": float(debit),
        "balance": bal, "remarks": remarks, "created_at": now_iso(),
    })
    return bal


def public_user(u: dict) -> dict:
    return {
        "id": u["id"], "user_code": u["user_code"], "name": u["name"], "email": u.get("email"),
        "mobile": u.get("mobile"), "role": u["role"], "role_label": ROLE_KEY_TO_LABEL.get(u["role"], u["role"]),
        "status": u.get("status"), "wallet_balance": u.get("wallet_balance", 0),
        "wallet": fmt_inr(u.get("wallet_balance", 0)), "shop_name": u.get("shop_name"),
        "address": u.get("address"),
    }


# ============================ MODELS ============================
class SendOtpIn(BaseModel):
    email: EmailStr


class RegisterIn(BaseModel):
    name: str = "New Retailer"
    aadhaar: str
    pan: str
    mobile: str
    email: EmailStr
    otp: str
    password: str
    shop_name: str
    address: str
    photo_path: Optional[str] = ""


class LoginIn(BaseModel):
    user_id: str
    password: str
    role: Optional[str] = None


class CreateUserIn(BaseModel):
    name: str
    mobile: str
    email: EmailStr
    role: str  # label or key


class EditUserIn(BaseModel):
    name: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[EmailStr] = None


class ReviewRegIn(BaseModel):
    decision: str  # Approved | Rejected
    remark: Optional[str] = ""


class PanCreateIn(BaseModel):
    type: str = "New PAN"
    applicant_name: str = "New Applicant"
    applicant_type: Optional[str] = "Major Applicant"
    state: Optional[str] = ""
    city: Optional[str] = ""
    area_code: Optional[str] = ""
    ao_type: Optional[str] = ""
    range_code: Optional[str] = ""
    ao_number: Optional[str] = ""
    form_data: Optional[dict] = {}


class PanReviewIn(BaseModel):
    action: str  # Approved | Rejected | Hold
    remark: Optional[str] = ""
    receipt_name: Optional[str] = ""


class RechargeIn(BaseModel):
    amount: float
    utr: str


class ReviewDecisionIn(BaseModel):
    decision: str  # Approved | Rejected


class TicketCreateIn(BaseModel):
    subject: str
    category: str = "General"
    priority: str = "Medium"
    message: Optional[str] = ""


class ReplyIn(BaseModel):
    text: str


class SettingsIn(BaseModel):
    smtp: Optional[dict] = None
    ftp: Optional[dict] = None
    pricing: Optional[dict] = None
    toggles: Optional[dict] = None


# ============================ AUTH ============================
@api.post("/auth/register/send-otp")
async def send_otp(body: SendOtpIn):
    code = f"{random.randint(0, 999999):06d}"
    await db.otps.update_one(
        {"email": body.email.lower()},
        {"$set": {"email": body.email.lower(), "code": code, "created_at": now_iso()}},
        upsert=True,
    )
    subject = "Your Gramin PAN Seva verification code"
    html = (f"<div style='font-family:Arial,sans-serif'><h2 style='color:#163C5A'>Gramin PAN Seva</h2>"
            f"<p>Your email verification code is:</p>"
            f"<p style='font-size:28px;font-weight:bold;letter-spacing:4px;color:#163C5A'>{code}</p>"
            f"<p>This code is valid for 10 minutes. If you did not request this, please ignore.</p></div>")
    text = f"Your Gramin PAN Seva verification code is {code}. Valid for 10 minutes."
    emailed = await send_email(body.email, subject, html, text)
    logger.info(f"[OTP] {body.email}: {code} (emailed={emailed})")
    resp = {
        "sent": True,
        "emailed": emailed,
        "message": "OTP sent to your email." if emailed else "OTP generated. Configure SMTP in Settings to email it.",
    }
    if not emailed:
        resp["dev_otp"] = code  # MOCK fallback when SMTP is not configured
    return resp


@api.post("/auth/register")
async def register(body: RegisterIn):
    rec = await db.otps.find_one({"email": body.email.lower()})
    if not rec or rec.get("code") != body.otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(status_code=400, detail="Email already registered")
    reg_id = f"REG-2026-{await next_seq('reg'):05d}"
    await db.registrations.insert_one({
        "id": str(uuid.uuid4()), "reg_id": reg_id, "name": body.name, "role": "Retailer",
        "mobile": body.mobile, "email": body.email.lower(), "shop_name": body.shop_name,
        "address": body.address, "aadhaar": body.aadhaar, "pan": body.pan.upper(),
        "password_hash": hash_password(body.password), "photo_path": body.photo_path or "",
        "date": today_str(), "status": "Pending", "created_at": now_iso(),
    })
    await db.otps.delete_one({"email": body.email.lower()})
    return {"reference_id": reg_id, "status": "Pending", "message": "Registration submitted for review."}


@api.post("/auth/login")
async def login(body: LoginIn):
    user = await db.users.find_one({"user_code": body.user_id.strip()})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid User ID or password")
    if user.get("status") == "Blocked":
        raise HTTPException(status_code=403, detail="Your account has been blocked. Contact support.")
    if user.get("status") == "Pending":
        raise HTTPException(status_code=403, detail="Your account is pending approval.")
    token = create_access_token(user["id"], user["role"])
    await audit(user, "login", f"{user['user_code']} logged in")
    return {"token": token, "user": public_user(user)}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return public_user(fresh)


@api.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    return {"ok": True}


# ============================ USERS ============================
@api.get("/users")
async def list_users(role: str = Query(...), user: dict = Depends(get_current_user)):
    role_key = ROLE_LABEL_TO_KEY.get(role, role)
    q = {"role": role_key}
    if user["role"] != "superadmin":
        q["ancestors"] = user["id"]
    rows = await db.users.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [public_user(u) for u in rows]


@api.post("/users")
async def create_user(body: CreateUserIn, user: dict = Depends(get_current_user)):
    role_key = ROLE_LABEL_TO_KEY.get(body.role, body.role)
    if role_key not in CREATE_RIGHTS.get(user["role"], set()):
        raise HTTPException(status_code=403, detail="You cannot create this role")
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(status_code=400, detail="Email already in use")
    code = await gen_user_code(role_key)
    default_pw = os.environ.get("SEED_USER_PASSWORD", "Password@123")
    new_user = {
        "id": str(uuid.uuid4()), "user_code": code, "name": body.name, "email": body.email.lower(),
        "mobile": body.mobile, "password_hash": hash_password(default_pw), "role": role_key,
        "status": "Active", "parent_id": user["id"], "ancestors": user.get("ancestors", []) + [user["id"]],
        "wallet_balance": 0.0, "shop_name": f"{body.name} Center", "address": "", "created_at": now_iso(),
    }
    await db.users.insert_one(new_user)
    await audit(user, "create_user", f"Created {role_key} {code} ({body.name})")
    return {"user": public_user(new_user), "default_password": default_pw,
            "message": f"{ROLE_KEY_TO_LABEL[role_key]} created with ID {code}."}


@api.patch("/users/{uid}")
async def edit_user(uid: str, body: EditUserIn, user: dict = Depends(get_current_user)):
    target = await db.users.find_one({"id": uid})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await db.users.update_one({"id": uid}, {"$set": updates})
        await audit(user, "edit_user", f"Edited {target['user_code']}")
    fresh = await db.users.find_one({"id": uid}, {"_id": 0})
    return public_user(fresh)


@api.post("/users/{uid}/toggle-block")
async def toggle_block(uid: str, user: dict = Depends(require_roles("superadmin", "superdistributor", "distributor"))):
    target = await db.users.find_one({"id": uid})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    new_status = "Active" if target.get("status") == "Blocked" else "Blocked"
    await db.users.update_one({"id": uid}, {"$set": {"status": new_status}})
    await audit(user, "toggle_block", f"{target['user_code']} -> {new_status}")
    return {"id": uid, "status": new_status}


@api.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_roles("superadmin"))):
    target = await db.users.find_one({"id": uid})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.delete_one({"id": uid})
    await audit(user, "delete_user", f"Deleted {target['user_code']}")
    return {"ok": True}


# ============================ REGISTRATIONS ============================
@api.get("/registrations")
async def list_registrations(user: dict = Depends(require_roles("superadmin"))):
    rows = await db.registrations.find({"status": "Pending"}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(1000)
    return rows


@api.post("/registrations/{reg_id}/review")
async def review_registration(reg_id: str, body: ReviewRegIn, user: dict = Depends(require_roles("superadmin"))):
    reg = await db.registrations.find_one({"reg_id": reg_id})
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")
    if body.decision == "Approved":
        role_key = ROLE_LABEL_TO_KEY.get(reg["role"], "retailer")
        code = await gen_user_code(role_key)
        new_user = {
            "id": str(uuid.uuid4()), "user_code": code, "name": reg["name"], "email": reg["email"],
            "mobile": reg["mobile"], "password_hash": reg["password_hash"], "role": role_key,
            "status": "Active", "parent_id": user["id"], "ancestors": [user["id"]],
            "wallet_balance": 0.0, "shop_name": reg.get("shop_name", ""), "address": reg.get("address", ""),
            "created_at": now_iso(),
        }
        await db.users.insert_one(new_user)
        await db.registrations.update_one({"reg_id": reg_id}, {"$set": {"status": "Approved", "assigned_code": code}})
        await audit(user, "approve_registration", f"{reg_id} approved as {code}")
        return {"status": "Approved", "user_code": code, "message": f"{reg['name']} approved with ID {code}."}
    else:
        await db.registrations.update_one({"reg_id": reg_id}, {"$set": {"status": "Rejected", "remark": body.remark}})
        await audit(user, "reject_registration", f"{reg_id} rejected")
        return {"status": "Rejected", "message": f"{reg['name']}'s registration rejected."}


# ============================ META (states/cities/ao) ============================
@api.get("/states")
async def get_states():
    meta = await db.meta.find_one({"id": "geo"}, {"_id": 0})
    return meta.get("states", [])


@api.get("/cities")
async def get_cities(state: str = Query(...)):
    meta = await db.meta.find_one({"id": "geo"}, {"_id": 0})
    cities = meta.get("cities", {}).get(state)
    if cities:
        return cities
    return [f"{state} (Main)"]


@api.get("/ao-codes")
async def get_ao_codes(city: str = Query(...), state: Optional[str] = None):
    q = {"city": city}
    if state:
        q["state"] = state
    rows = await db.ao_codes.find(q, {"_id": 0, "id": 0}).to_list(2000)
    return rows


# ============================ PAN APPLICATIONS ============================
@api.get("/pan-applications")
async def list_pan(status: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    if user["role"] != "superadmin":
        # submitter sees own + downline applications
        ids = [user["id"]]
        downline = await db.users.find({"ancestors": user["id"]}, {"_id": 0, "id": 1}).to_list(5000)
        ids += [d["id"] for d in downline]
        q["submitted_by_user_id"] = {"$in": ids}
    if status:
        q["status"] = status
    rows = await db.pan_applications.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return rows


@api.post("/pan-applications")
async def create_pan(body: PanCreateIn, user: dict = Depends(get_current_user)):
    settings = await db.settings.find_one({"id": "global"}, {"_id": 0})
    price = float(settings.get("pricing", {}).get(body.type, 107.0))
    bal = float(user.get("wallet_balance", 0))
    if bal < price:
        raise HTTPException(status_code=400, detail=f"Insufficient wallet balance. Need {fmt_inr(price)}, have {fmt_inr(bal)}.")
    app_id = f"APP-{await next_seq('pan')}"
    doc = {
        "id": str(uuid.uuid4()), "app_id": app_id, "applicant_name": body.applicant_name, "type": body.type,
        "date": today_str(), "status": "Processed", "submitted_by_role": user["role"],
        "submitted_by_user_id": user["id"], "applicant_type": body.applicant_type,
        "remark": "", "receipt_name": "", "receipt_path": "",
        "form_data": {**(body.form_data or {}), "state": body.state, "city": body.city,
                      "area_code": body.area_code, "ao_type": body.ao_type,
                      "range_code": body.range_code, "ao_number": body.ao_number},
        "created_at": now_iso(),
    }
    await db.pan_applications.insert_one(doc)
    await apply_wallet(user["id"], 0, price, f"{body.type} service charge \u2014 {app_id}")
    await notify(user["id"], "fa-id-card", "var(--info-bg)", "var(--info)", "PAN Submitted",
                 f"{body.type} application {app_id} submitted successfully.")
    await audit(user, "submit_pan", f"{app_id} ({body.type})")
    doc.pop("_id", None)
    return {"application": doc, "message": "Application submitted.", "wallet_balance": fmt_inr(bal - price)}


@api.post("/pan-applications/{app_id}/review")
async def review_pan(app_id: str, body: PanReviewIn, user: dict = Depends(require_roles("superadmin"))):
    p = await db.pan_applications.find_one({"app_id": app_id})
    if not p:
        raise HTTPException(status_code=404, detail="Application not found")
    if body.action == "Approved" and not body.receipt_name:
        raise HTTPException(status_code=400, detail="Receipt is required to accept an application")
    if body.action in ("Rejected", "Hold") and not body.remark:
        raise HTTPException(status_code=400, detail="Remark is required to reject or hold")
    await db.pan_applications.update_one({"app_id": app_id}, {"$set": {
        "status": body.action, "remark": body.remark or "",
        "receipt_name": body.receipt_name if body.action == "Approved" else "",
    }})
    icon = {"Approved": "fa-check", "Rejected": "fa-xmark", "Hold": "fa-circle-pause"}[body.action]
    color = {"Approved": "var(--success)", "Rejected": "var(--danger)", "Hold": "var(--warning)"}[body.action]
    bg = {"Approved": "var(--success-bg)", "Rejected": "var(--danger-bg)", "Hold": "var(--warning-bg)"}[body.action]
    await notify(p["submitted_by_user_id"], icon, bg, color, f"PAN {body.action}",
                 f"Application {app_id} for {p['applicant_name']} was {body.action.lower()}.")
    await audit(user, "review_pan", f"{app_id} -> {body.action}")
    return {"app_id": app_id, "status": body.action}


@api.delete("/pan-applications/{app_id}")
async def delete_pan(app_id: str, user: dict = Depends(require_roles("superadmin"))):
    res = await db.pan_applications.delete_one({"app_id": app_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Application not found")
    await audit(user, "delete_pan", app_id)
    return {"ok": True}


# ============================ WALLET ============================
@api.get("/wallet/transactions")
async def wallet_transactions(filter: Optional[str] = None, user: dict = Depends(get_current_user)):
    rows = await db.transactions.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    out = []
    for t in rows:
        if filter == "credit" and t["credit"] <= 0:
            continue
        if filter == "debit" and t["debit"] <= 0:
            continue
        out.append({
            "date": t["date"], "txnId": t["txn_id"],
            "credit": fmt_inr(t["credit"]) if t["credit"] > 0 else "-",
            "debit": fmt_inr(t["debit"]) if t["debit"] > 0 else "-",
            "balance": fmt_inr(t["balance"]), "remarks": t["remarks"],
        })
    return out


@api.post("/wallet/recharge")
async def submit_recharge(body: RechargeIn, user: dict = Depends(get_current_user)):
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    if not body.utr.strip():
        raise HTTPException(status_code=400, detail="UTR number is required")
    doc = {
        "id": str(uuid.uuid4()), "user_id": user["id"], "submitted_by_name": user["name"],
        "user_code": user["user_code"], "date": today_str(), "amount": float(body.amount),
        "utr": body.utr, "status": "Pending", "created_at": now_iso(),
    }
    await db.recharge_requests.insert_one(doc)
    await audit(user, "recharge_request", f"{fmt_inr(body.amount)} UTR {body.utr}")
    return {"message": "Recharge request submitted for approval.", "id": doc["id"]}


@api.get("/wallet/recharge-requests")
async def list_recharge(user: dict = Depends(get_current_user)):
    q = {} if user["role"] == "superadmin" else {"user_id": user["id"]}
    rows = await db.recharge_requests.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [{
        "id": r["id"], "submittedBy": r["submitted_by_name"], "userCode": r["user_code"],
        "date": r["date"], "amount": fmt_inr(r["amount"]), "utr": r["utr"], "status": r["status"],
    } for r in rows]


@api.post("/wallet/recharge-requests/{rid}/review")
async def review_recharge(rid: str, body: ReviewDecisionIn, user: dict = Depends(require_roles("superadmin"))):
    r = await db.recharge_requests.find_one({"id": rid})
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")
    if r["status"] != "Pending":
        raise HTTPException(status_code=400, detail="Request already reviewed")
    await db.recharge_requests.update_one({"id": rid}, {"$set": {"status": body.decision}})
    if body.decision == "Approved":
        await apply_wallet(r["user_id"], r["amount"], 0, "Wallet recharge approved")
        await notify(r["user_id"], "fa-wallet", "var(--info-bg)", "var(--info)", "Wallet Approved",
                     f"Your recharge request of {fmt_inr(r['amount'])} has been approved.")
    else:
        await notify(r["user_id"], "fa-circle-exclamation", "var(--warning-bg)", "var(--warning)", "Wallet Rejected",
                     f"Your recharge request of {fmt_inr(r['amount'])} was rejected.")
    await audit(user, "review_recharge", f"{rid} -> {body.decision}")
    return {"id": rid, "status": body.decision}


# ============================ TICKETS ============================
@api.get("/tickets")
async def list_tickets(user: dict = Depends(get_current_user)):
    q = {} if user["role"] == "superadmin" else {"user_id": user["id"]}
    rows = await db.tickets.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [{"id": t["ticket_id"], "subject": t["subject"], "category": t["category"],
             "priority": t["priority"], "status": t["status"], "date": t["date"]} for t in rows]


@api.post("/tickets")
async def create_ticket(body: TicketCreateIn, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Admins manage tickets and cannot raise them")
    tid = f"TK-{await next_seq('ticket')}"
    doc = {
        "id": str(uuid.uuid4()), "ticket_id": tid, "user_id": user["id"], "subject": body.subject,
        "category": body.category, "priority": body.priority, "status": "Open", "date": today_str(),
        "messages": [{"sender_role": user["role"], "text": body.message or body.subject, "at": now_iso()}],
        "created_at": now_iso(),
    }
    await db.tickets.insert_one(doc)
    return {"id": tid, "message": "Ticket created."}


@api.get("/tickets/{tid}")
async def get_ticket(tid: str, user: dict = Depends(get_current_user)):
    t = await db.tickets.find_one({"ticket_id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t


@api.post("/tickets/{tid}/reply")
async def reply_ticket(tid: str, body: ReplyIn, user: dict = Depends(get_current_user)):
    t = await db.tickets.find_one({"ticket_id": tid})
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    msg = {"sender_role": user["role"], "text": body.text, "at": now_iso()}
    new_status = "In Progress" if t["status"] == "Open" else t["status"]
    await db.tickets.update_one({"ticket_id": tid}, {"$push": {"messages": msg}, "$set": {"status": new_status}})
    return {"ok": True}


@api.post("/tickets/{tid}/resolve")
async def resolve_ticket(tid: str, user: dict = Depends(require_roles("superadmin"))):
    res = await db.tickets.update_one({"ticket_id": tid}, {"$set": {"status": "Closed"}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"id": tid, "status": "Closed"}


# ============================ NOTIFICATIONS ============================
@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    rows = await db.notifications.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [{"icon": n["icon"], "bg": n["bg"], "color": n["color"], "title": n["title"],
             "detail": n["detail"], "time": n.get("time", "")} for n in rows]


# ============================ SETTINGS ============================
@api.get("/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    s = await db.settings.find_one({"id": "global"}, {"_id": 0})
    if user["role"] != "superadmin":
        return {"pricing": s.get("pricing", {})}
    return s


@api.put("/settings")
async def update_settings(body: SettingsIn, user: dict = Depends(require_roles("superadmin"))):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updates["updated_at"] = now_iso()
    await db.settings.update_one({"id": "global"}, {"$set": updates})
    await audit(user, "update_settings", ", ".join(updates.keys()))
    return await db.settings.find_one({"id": "global"}, {"_id": 0})


# ============================ DASHBOARD ============================
@api.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    role = user["role"]
    wallet = fmt_inr(user.get("wallet_balance", 0)) + ".00"
    if role == "superadmin":
        sd = await db.users.count_documents({"role": "superdistributor"})
        dist = await db.users.count_documents({"role": "distributor"})
        ret = await db.users.count_documents({"role": "retailer"})
        total_pan = await db.pan_applications.count_documents({})
        pending = await db.pan_applications.count_documents({"status": "Processed"})
        approved = await db.pan_applications.count_documents({"status": "Approved"})
        hold = await db.pan_applications.count_documents({"status": "Hold"})
        wallet_reqs = await db.recharge_requests.count_documents({"status": "Pending"})
        return {"role": role, "wallet": wallet, "cards": {
            "total_users": sd + dist + ret, "retailers": ret, "distributors": dist,
            "super_distributors": sd, "total_pan": total_pan, "pending_pan": pending,
            "approved_pan": approved, "hold_pan": hold, "wallet_requests": wallet_reqs}}
    # downline-aware
    downline = await db.users.find({"ancestors": user["id"]}, {"_id": 0, "id": 1, "role": 1}).to_list(5000)
    ids = [user["id"]] + [d["id"] for d in downline]
    dist = sum(1 for d in downline if d["role"] == "distributor")
    ret = sum(1 for d in downline if d["role"] == "retailer")
    total_pan = await db.pan_applications.count_documents({"submitted_by_user_id": {"$in": ids}})
    pending = await db.pan_applications.count_documents({"submitted_by_user_id": {"$in": ids}, "status": "Processed"})
    approved = await db.pan_applications.count_documents({"submitted_by_user_id": {"$in": ids}, "status": "Approved"})
    hold = await db.pan_applications.count_documents({"submitted_by_user_id": {"$in": ids}, "status": "Hold"})
    rejected = await db.pan_applications.count_documents({"submitted_by_user_id": {"$in": ids}, "status": "Rejected"})
    return {"role": role, "wallet": wallet, "cards": {
        "distributors": dist, "retailers": ret, "total_pan": total_pan,
        "pending_pan": pending, "approved_pan": approved, "hold_pan": hold, "rejected_pan": rejected}}


@api.get("/dashboard/activity")
async def dashboard_activity(user: dict = Depends(get_current_user)):
    logs = await db.audit_logs.find({}, {"_id": 0}).sort("at", -1).to_list(8)
    icon_map = {"login": ("fa-right-to-bracket", "var(--info-bg)", "var(--info)"),
                "submit_pan": ("fa-id-card", "var(--info-bg)", "var(--info)"),
                "review_pan": ("fa-stamp", "var(--success-bg)", "var(--success)"),
                "review_recharge": ("fa-wallet", "var(--info-bg)", "var(--info)"),
                "approve_registration": ("fa-user-plus", "var(--hold-bg)", "var(--hold)"),
                "create_user": ("fa-user-plus", "var(--hold-bg)", "var(--hold)")}
    out = []
    for l in logs:
        icon, bg, color = icon_map.get(l["action"], ("fa-circle-info", "var(--info-bg)", "var(--info)"))
        out.append({"icon": icon, "bg": bg, "color": color,
                    "title": l["action"].replace("_", " ").title(), "detail": l["detail"], "time": ""})
    return out


# ============================ AUDIT ============================
@api.get("/audit-logs")
async def audit_logs(user: dict = Depends(require_roles("superadmin"))):
    return await db.audit_logs.find({}, {"_id": 0}).sort("at", -1).to_list(500)


# ============================ UPLOADS (MOCK FTP) ============================
@api.post("/uploads")
async def upload_file(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    allowed = {".jpg", ".jpeg", ".png", ".pdf", ".webp"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    fname = f"{uuid.uuid4().hex}{ext}"
    settings = await get_global_settings()
    ftp_cfg = settings.get("ftp", {})
    if ftp_is_configured(ftp_cfg):
        try:
            remote_path = await asyncio.to_thread(_ftp_upload_blocking, ftp_cfg, fname, data)
            return {"filename": file.filename, "path": remote_path, "url": remote_path, "storage": "ftp"}
        except Exception as e:
            logger.error(f"FTP upload failed, using local storage: {e}")
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        f.write(data)
    # When FTP is not configured, files are stored on local disk and served at /api/uploads.
    return {"filename": file.filename, "path": f"/api/uploads/{fname}", "url": f"/api/uploads/{fname}", "storage": "local"}


@api.get("/")
async def root():
    return {"message": "Gramin PAN Seva API", "status": "ok"}


app.include_router(api)
app.mount("/api/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ---------- Serve the static frontend (production / VPS) ----------
# In the Emergent preview, "/" is routed to the React dev server, so this catch-all is dormant.
# On a VPS, FastAPI serves the single-file Bootstrap frontend for all non-API routes (SPA fallback).
FRONTEND_DIR = os.environ.get(
    "FRONTEND_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public")
)


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not found")
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend not built")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await seed_data.seed()
    logger.info("Gramin PAN Seva API started and seeded.")


@app.on_event("shutdown")
async def shutdown():
    client.close()
