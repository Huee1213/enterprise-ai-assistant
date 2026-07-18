import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='conversation_history'"))
        for r in result:
            print(f"{r[0]:20} {r[1]}")

asyncio.run(check())
