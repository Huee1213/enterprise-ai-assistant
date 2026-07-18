import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        for row in result:
            print(row[0])

asyncio.run(check())
