"""One-off: clear test submissions for live launch (keeps users, admin, settings, ao_codes)."""
import asyncio
from database import db


async def main():
    drop_cols = ["pan_applications", "recharge_requests", "transactions",
                 "notifications", "tickets", "audit_logs"]
    for c in drop_cols:
        res = await db[c].delete_many({})
        print(f"cleared {c}: {res.deleted_count}")
    bal = await db.users.update_many({}, {"$set": {"wallet_balance": 0}})
    print(f"reset wallet balances on {bal.modified_count} users")
    print("users kept:", await db.users.count_documents({}))
    print("ao_codes kept:", await db.ao_codes.count_documents({}))


if __name__ == "__main__":
    asyncio.run(main())
