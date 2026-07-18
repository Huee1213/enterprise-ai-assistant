import asyncio, json
from app.database import AsyncSessionLocal
from app.memory import save_message

async def test():
    async with AsyncSessionLocal() as db:
        await save_message(db, "test_user", "test_conv_123", "user", "hello")
        await save_message(db, "test_user", "test_conv_123", "assistant", "world", metadata_str=json.dumps({"steps": [{"test": True}]}))
        print("Saved 2 messages")
        # Read back
        from sqlalchemy import text
        result = await db.execute(text("SELECT role, content, msg_meta FROM conversation_history WHERE conversation_id='test_conv_123' ORDER BY id"))
        for r in result:
            print(f"  role={r[0]} content={r[1]} meta={r[2]}")

asyncio.run(test())
