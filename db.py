import json
import aiosqlite
from typing import Optional


async def init_db(path: str):
    async with aiosqlite.connect(path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                name TEXT,
                email TEXT,
                service TEXT,
                lead_message TEXT,
                history TEXT DEFAULT '[]',
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                direction TEXT NOT NULL,  -- 'outbound' or 'inbound_reply'
                draft_text TEXT NOT NULL,
                telegram_message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def upsert_conversation(path: str, phone: str, name: str, email: str,
                               service: str, lead_message: str):
    async with aiosqlite.connect(path) as db:
        await db.execute("""
            INSERT INTO conversations (phone, name, email, service, lead_message, history, status)
            VALUES (?, ?, ?, ?, ?, '[]', 'new')
            ON CONFLICT(phone) DO UPDATE SET
                name=excluded.name,
                email=excluded.email,
                service=excluded.service,
                lead_message=excluded.lead_message,
                status='new',
                updated_at=CURRENT_TIMESTAMP
        """, (phone, name, email, service, lead_message))
        await db.commit()


async def get_conversation(path: str, phone: str) -> Optional[dict]:
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM conversations WHERE phone = ?", (phone,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                d = dict(row)
                d["history"] = json.loads(d["history"])
                return d
    return None


async def append_history(path: str, phone: str, role: str, content: str):
    conv = await get_conversation(path, phone)
    if not conv:
        return
    history = conv["history"]
    history.append({"role": role, "content": content})
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "UPDATE conversations SET history=?, updated_at=CURRENT_TIMESTAMP WHERE phone=?",
            (json.dumps(history), phone)
        )
        await db.commit()


async def update_status(path: str, phone: str, status: str):
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "UPDATE conversations SET status=?, updated_at=CURRENT_TIMESTAMP WHERE phone=?",
            (status, phone)
        )
        await db.commit()


async def save_pending(path: str, phone: str, direction: str, draft_text: str,
                        telegram_message_id: Optional[int] = None) -> int:
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute("""
            INSERT INTO pending_messages (phone, direction, draft_text, telegram_message_id)
            VALUES (?, ?, ?, ?)
        """, (phone, direction, draft_text, telegram_message_id))
        await db.commit()
        return cursor.lastrowid


async def get_pending(path: str, pending_id: int) -> Optional[dict]:
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM pending_messages WHERE id = ?", (pending_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def delete_pending(path: str, pending_id: int):
    async with aiosqlite.connect(path) as db:
        await db.execute("DELETE FROM pending_messages WHERE id = ?", (pending_id,))
        await db.commit()
