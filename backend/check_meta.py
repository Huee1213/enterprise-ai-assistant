import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT id, role, content, msg_meta FROM conversation_history ORDER BY id DESC LIMIT 4"))
        for r in result:
            meta = r[3][:80] if r[3] and r[3] != "{}" else "(empty)"
            print(f"id={r[0]} role={r[1]} content={r[2][:30]}... meta={meta}")

asyncio.run(check())
