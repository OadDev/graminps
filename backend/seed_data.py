import os
import uuid
from datetime import datetime, timezone

from database import db
from security import hash_password

STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
]

CITIES = {
    "Assam": ["Barpeta", "Bongaigaon", "Dhubri", "Dibrugarh", "Digboi", "Duliajan", "Goalpara", "Golaghat",
              "Guwahati", "Jorhat", "Karimganj", "Mangaldoi", "Morigaon", "Nagaon", "Nalbari",
              "North Lakhimpur", "Silchar", "Sivasagar", "Tezpur", "Tinsukia"],
    "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Darbhanga"],
    "Delhi": ["New Delhi", "South Delhi", "North Delhi", "East Delhi", "West Delhi"],
    "Karnataka": ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi", "Belagavi"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad"],
    "West Bengal": ["Kolkata", "Howrah", "Siliguri", "Durgapur", "Asansol"],
}

AO_CODES = {
    "Guwahati": [
        {"ward": "ITO IT&TP KOLKATA AT GUWAHATI", "area_code": "DLC", "ao_type": "W", "range_code": "603", "ao_number": "1", "category": "Both"},
        {"ward": "WARD 2(3), EXEMP, GUWAHATI", "area_code": "DLC", "ao_type": "WX", "range_code": "259", "ao_number": "3", "category": "Both"},
        {"ward": "DCIT/ACIT CIR-1, GUWAHATI", "area_code": "SHL", "ao_type": "C", "range_code": "1", "ao_number": "1", "category": "Individual"},
        {"ward": "ACIT CIRCLE-2, GUWAHATI", "area_code": "SHL", "ao_type": "C", "range_code": "2", "ao_number": "1", "category": "Individual"},
        {"ward": "ITO WARD -1(1), GUWAHATI", "area_code": "SHL", "ao_type": "W", "range_code": "1", "ao_number": "1", "category": "Individual"},
        {"ward": "ITO WARD -1(2), GUWAHATI", "area_code": "SHL", "ao_type": "W", "range_code": "1", "ao_number": "2", "category": "Individual"},
        {"ward": "ITO WARD -2(1), GUWAHATI", "area_code": "SHL", "ao_type": "W", "range_code": "2", "ao_number": "1", "category": "Individual"},
    ],
    "Jorhat": [
        {"ward": "ITO WARD -1, JORHAT", "area_code": "SHL", "ao_type": "W", "range_code": "7", "ao_number": "1", "category": "Individual"},
    ],
    "Silchar": [
        {"ward": "DCIT/ACIT CIRCLE SILCHAR", "area_code": "SHL", "ao_type": "C", "range_code": "16", "ao_number": "1", "category": "Individual"},
        {"ward": "ITO WARD -1, SILCHAR", "area_code": "SHL", "ao_type": "W", "range_code": "16", "ao_number": "1", "category": "Individual"},
    ],
    "Dibrugarh": [
        {"ward": "ACIT/DCIT CIRCLE 1 DIBRUGARH", "area_code": "SHL", "ao_type": "C", "range_code": "25", "ao_number": "1", "category": "Individual"},
        {"ward": "ITO WARD 1(1), DIBRUGARH", "area_code": "SHL", "ao_type": "W", "range_code": "25", "ao_number": "1", "category": "Individual"},
        {"ward": "ITO WARD 1(2) DIBRUGARH", "area_code": "SHL", "ao_type": "W", "range_code": "25", "ao_number": "2", "category": "Individual"},
    ],
    "default": [
        {"ward": "DCIT/ACIT CIRCLE EXEMPTION, NAGPUR", "area_code": "DLC", "ao_type": "CA", "range_code": "221", "ao_number": "1", "category": "Both"},
        {"ward": "ITO WARD-1, EXEMPTION, NAGPUR", "area_code": "DLC", "ao_type": "WX", "range_code": "221", "ao_number": "1", "category": "Both"},
        {"ward": "ITO WARD-2, EXEMPTION, NAGPUR", "area_code": "DLC", "ao_type": "WX", "range_code": "221", "ao_number": "2", "category": "Both"},
        {"ward": "ITO WARD-3, EXEMPTION, NAGPUR", "area_code": "DLC", "ao_type": "WX", "range_code": "221", "ao_number": "3", "category": "Both"},
        {"ward": "ITO WARD-4, EXEMPTION, NAGPUR", "area_code": "DLC", "ao_type": "WX", "range_code": "221", "ao_number": "4", "category": "Both"},
    ],
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_inr(s):
    return float(s.replace("\u20b9", "").replace(",", "").strip() or 0)


async def seed():
    # ---------- Settings ----------
    if not await db.settings.find_one({"id": "global"}):
        await db.settings.insert_one({
            "id": "global",
            "smtp": {"host": "smtp.hostinger.com", "port": 465, "username": "", "password": "", "from_email": "noreply@graminpanseva.in"},
            "ftp": {"host": "", "port": 21, "username": "", "password": "", "base_path": "/pan_docs"},
            "pricing": {"New PAN": 107.0, "CSF PAN": 85.0},
            "toggles": {"registration_open": True, "maintenance_mode": False},
            "updated_at": now_iso(),
        })

    # ---------- AO codes / meta ----------
    if await db.ao_codes.count_documents({}) == 0:
        rows = []
        for city, wards in AO_CODES.items():
            for w in wards:
                rows.append({"id": str(uuid.uuid4()), "city": city, **w})
        await db.ao_codes.insert_one({"id": "default", "city": "default", "wards": AO_CODES["default"]}) if False else None
        await db.ao_codes.insert_many(rows)

    if not await db.meta.find_one({"id": "geo"}):
        await db.meta.insert_one({"id": "geo", "states": STATES, "cities": CITIES})

    # ---------- Users ----------
    if await db.users.count_documents({}) > 0:
        return  # already seeded

    seed_pw = os.environ.get("SEED_USER_PASSWORD", "Password@123")
    admin_pw = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    admin_code = os.environ.get("ADMIN_USER_ID", "AD-0001")

    admin_id = str(uuid.uuid4())
    await db.users.insert_one({
        "id": admin_id, "user_code": admin_code, "name": "Admin Office",
        "email": os.environ.get("ADMIN_EMAIL", "admin@graminpanseva.in"),
        "mobile": "9000000000", "password_hash": hash_password(admin_pw),
        "role": "superadmin", "status": "Active", "parent_id": None, "ancestors": [],
        "wallet_balance": 0.0, "shop_name": "Gramin PAN Seva HQ", "address": "Head Office",
        "created_at": now_iso(),
    })

    def mkuser(code, name, mobile, status, wallet, role, parent_id, ancestors):
        return {
            "id": str(uuid.uuid4()), "user_code": code, "name": name, "email": f"{code.lower()}@example.com",
            "mobile": mobile, "password_hash": hash_password(seed_pw), "role": role, "status": status,
            "parent_id": parent_id, "ancestors": ancestors, "wallet_balance": parse_inr(wallet),
            "shop_name": f"{name} Center", "address": "Assam, India", "created_at": now_iso(),
        }

    sd_rows = [
        ("SD1001", "Pranjal Bora", "9864512230", "Active", "\u20b984,250"),
        ("SD1002", "Nilima Hazarika", "9854113302", "Active", "\u20b946,800"),
        ("SD1003", "Rituraj Gogoi", "9678541290", "Blocked", "\u20b912,400"),
        ("SD1004", "Dipankar Saikia", "9854120098", "Pending", "\u20b90"),
        ("SD1005", "Mridul Phukan", "8765432109", "Active", "\u20b961,500"),
    ]
    sds = {}
    for code, name, mob, st, wal in sd_rows:
        u = mkuser(code, name, mob, st, wal, "superdistributor", admin_id, [admin_id])
        sds[code] = u
    await db.users.insert_many(list(sds.values()))
    sd1001 = sds["SD1001"]["id"]

    dist_rows = [
        ("DT2031", "Manoj Deka", "9854221190", "Active", "\u20b922,180"),
        ("DT2032", "Suman Kalita", "8965231087", "Active", "\u20b915,600"),
        ("DT2033", "Joyanta Nath", "7896541230", "Blocked", "\u20b93,200"),
        ("DT2034", "Bedanta Sarma", "9123456780", "Pending", "\u20b90"),
        ("DT2035", "Hiranya Baruah", "9087654321", "Active", "\u20b99,840"),
        ("DT2036", "Plabita Das", "8001234567", "Active", "\u20b918,950"),
    ]
    dists = {}
    for code, name, mob, st, wal in dist_rows:
        u = mkuser(code, name, mob, st, wal, "distributor", sd1001, [admin_id, sd1001])
        dists[code] = u
    await db.users.insert_many(list(dists.values()))
    dt2031 = dists["DT2031"]["id"]

    ret_rows = [
        ("RT10234", "Bikash Sharma", "9854001122", "Active", "\u20b93,640"),
        ("RT10235", "Rina Bora", "9678123450", "Active", "\u20b91,280"),
        ("RT10236", "Pinku Saikia", "8765012398", "Pending", "\u20b90"),
        ("RT10237", "Anjali Devi", "7896012345", "Active", "\u20b95,920"),
        ("RT10238", "Kishore Das", "9012345678", "Blocked", "\u20b9640"),
        ("RT10239", "Mousumi Kalita", "8123456709", "Active", "\u20b92,410"),
        ("RT10240", "Tridib Phukan", "9654321870", "Active", "\u20b9780"),
    ]
    rets = {}
    for code, name, mob, st, wal in ret_rows:
        u = mkuser(code, name, mob, st, wal, "retailer", dt2031, [admin_id, sd1001, dt2031])
        rets[code] = u
    await db.users.insert_many(list(rets.values()))
    bikash = rets["RT10234"]["id"]

    role_user = {"retailer": bikash, "distributor": dt2031, "superdistributor": sd1001}

    # ---------- Counters ----------
    await db.counters.insert_many([
        {"_id": "superdistributor", "seq": 1005},
        {"_id": "distributor", "seq": 2036},
        {"_id": "retailer", "seq": 10240},
        {"_id": "pan", "seq": 22045},
        {"_id": "txn", "seq": 88231},
        {"_id": "ticket", "seq": 3381},
        {"_id": "reg", "seq": 8841},
    ])

    # ---------- PAN applications ----------
    pan_rows = [
        ("APP-22045", "Rina Bora", "New PAN", "18 Jun 2026", "Approved", "retailer", "", "receipt_22045.pdf"),
        ("APP-22044", "Kishore Das", "CSF PAN", "17 Jun 2026", "Processed", "retailer", "", ""),
        ("APP-22043", "Aryan Das", "New PAN", "17 Jun 2026", "Processed", "distributor", "", ""),
        ("APP-22042", "Mousumi Kalita", "New PAN", "16 Jun 2026", "Rejected", "retailer", "Aadhaar name does not match PAN application name.", ""),
        ("APP-22041", "Tridib Phukan", "New PAN", "15 Jun 2026", "Hold", "retailer", "Address proof document is blurred. Please re-upload a clear scan and resubmit.", ""),
        ("APP-22040", "Anjali Devi", "CSF PAN", "14 Jun 2026", "Approved", "superdistributor", "Verified and processed.", "receipt_22040.jpg"),
        ("APP-22039", "Pinku Saikia", "New PAN", "13 Jun 2026", "Processed", "retailer", "", ""),
        ("APP-22038", "Diganta Bora", "New PAN", "12 Jun 2026", "Approved", "distributor", "", "receipt_22038.pdf"),
    ]
    pans = []
    for app_id, name, ptype, date, status, by, remark, receipt in pan_rows:
        pans.append({
            "id": str(uuid.uuid4()), "app_id": app_id, "applicant_name": name, "type": ptype,
            "date": date, "status": status, "submitted_by_role": by,
            "submitted_by_user_id": role_user.get(by, bikash), "applicant_type": "Major Applicant",
            "remark": remark, "receipt_name": receipt, "receipt_path": "", "form_data": {},
            "created_at": now_iso(),
        })
    await db.pan_applications.insert_many(pans)

    # ---------- Wallet transactions (Bikash) ----------
    txn_rows = [
        ("19 Jun 2026", "TXN-88231", 2000, 0, 3640, "Wallet recharge approved"),
        ("18 Jun 2026", "TXN-88219", 0, 107, 1640, "New PAN service charge \u2014 APP-22045"),
        ("17 Jun 2026", "TXN-88204", 0, 85, 1747, "CSF PAN service charge \u2014 APP-22044"),
        ("15 Jun 2026", "TXN-88172", 1500, 0, 1832, "Wallet recharge approved"),
        ("12 Jun 2026", "TXN-88130", 0, 107, 332, "New PAN service charge \u2014 APP-22038"),
    ]
    txns = []
    for date, tid, credit, debit, bal, rem in txn_rows:
        txns.append({"id": str(uuid.uuid4()), "user_id": bikash, "date": date, "txn_id": tid,
                     "credit": float(credit), "debit": float(debit), "balance": float(bal),
                     "remarks": rem, "created_at": now_iso()})
    await db.transactions.insert_many(txns)

    # ---------- Recharge requests ----------
    code_to_id = {"RT10234": bikash, "DT2031": dt2031, "SD1001": sd1001}
    rr_rows = [
        ("Bikash Sharma", "RT10234", "19 Jun 2026", 2000, "UTR882310091", "Approved"),
        ("Manoj Deka", "DT2031", "10 Jun 2026", 1500, "UTR881720456", "Approved"),
        ("Pranjal Bora", "SD1001", "21 Jun 2026", 3000, "UTR884401123", "Pending"),
        ("Bikash Sharma", "RT10234", "05 Jun 2026", 500, "UTR880912789", "Rejected"),
    ]
    rrs = []
    for name, code, date, amt, utr, status in rr_rows:
        rrs.append({"id": str(uuid.uuid4()), "user_id": code_to_id.get(code, bikash),
                    "submitted_by_name": name, "user_code": code, "date": date,
                    "amount": float(amt), "utr": utr, "status": status, "created_at": now_iso()})
    await db.recharge_requests.insert_many(rrs)

    # ---------- Tickets ----------
    tk_rows = [
        ("TK-3381", "Payment not reflecting in wallet", "Wallet", "High", "Open", "21 Jun 2026"),
        ("TK-3375", "PAN application stuck on processing", "PAN Service", "Medium", "In Progress", "19 Jun 2026"),
        ("TK-3360", "Unable to upload Aadhaar document", "Technical", "Low", "Closed", "14 Jun 2026"),
        ("TK-3352", "Certificate download not working", "Certificates", "Low", "Closed", "10 Jun 2026"),
    ]
    tks = []
    for tid, subject, cat, prio, status, date in tk_rows:
        tks.append({"id": str(uuid.uuid4()), "ticket_id": tid, "user_id": bikash,
                    "subject": subject, "category": cat, "priority": prio, "status": status,
                    "date": date, "messages": [{"sender_role": "retailer", "text": subject, "at": now_iso()}],
                    "created_at": now_iso()})
    await db.tickets.insert_many(tks)

    # ---------- Notifications (Bikash) ----------
    notif_rows = [
        ("fa-check", "var(--success-bg)", "var(--success)", "Registration Approved", "Your retailer account has been verified and activated.", "2 days ago"),
        ("fa-id-card", "var(--success-bg)", "var(--success)", "PAN Approved", "Application APP-22045 for Rina Bora has been approved.", "5 hr ago"),
        ("fa-xmark", "var(--danger-bg)", "var(--danger)", "PAN Rejected", "Application APP-22042 for Mousumi Kalita was rejected.", "1 day ago"),
        ("fa-wallet", "var(--info-bg)", "var(--info)", "Wallet Approved", "Your recharge request of \u20b92,000 has been approved.", "2 days ago"),
        ("fa-circle-exclamation", "var(--warning-bg)", "var(--warning)", "Wallet Rejected", "Your recharge request of \u20b9500 was rejected \u2014 invalid UTR.", "1 week ago"),
    ]
    notifs = []
    for icon, bg, color, title, detail, time in notif_rows:
        notifs.append({"id": str(uuid.uuid4()), "user_id": bikash, "icon": icon, "bg": bg,
                       "color": color, "title": title, "detail": detail, "time": time,
                       "read": False, "created_at": now_iso()})
    await db.notifications.insert_many(notifs)

    # ---------- Pending registrations ----------
    reg_rows = [
        ("REG-2026-08841", "Pinku Saikia", "Retailer", "8765012398", "pinku.saikia@example.com", "Saikia Digital Seva", "24 Jun 2026"),
        ("REG-2026-08839", "Joyanta Nath", "Distributor", "7896541230", "joyanta.nath@example.com", "Nath Enterprises", "23 Jun 2026"),
        ("REG-2026-08835", "Dipankar Saikia", "Super Distributor", "9854120098", "dipankar.saikia@example.com", "Saikia Distribution Network", "22 Jun 2026"),
    ]
    regs = []
    for rid, name, role, mob, email, shop, date in reg_rows:
        regs.append({"id": str(uuid.uuid4()), "reg_id": rid, "name": name, "role": role,
                     "mobile": mob, "email": email, "shop_name": shop, "address": "Assam, India",
                     "aadhaar": "", "pan": "", "password_hash": hash_password(seed_pw),
                     "photo_path": "", "date": date, "status": "Pending", "created_at": now_iso()})
    await db.registrations.insert_many(regs)
