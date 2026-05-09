import json
import uuid
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
            CREATE TABLE IF NOT EXISTS variants (
                id TEXT PRIMARY KEY,
                phone TEXT NOT NULL,
                text TEXT NOT NULL,
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


async def save_variant(path: str, phone: str, text: str) -> str:
    """Save a response variant and return its short ID."""
    vid = str(uuid.uuid4())[:8]
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT INTO variants (id, phone, text) VALUES (?, ?, ?)",
            (vid, phone, text)
        )
        await db.commit()
    return vid


async def get_variant(path: str, vid: str) -> Optional[str]:
    """Fetch variant text by ID."""
    async with aiosqlite.connect(path) as db:
        async with db.execute(
            "SELECT text FROM variants WHERE id = ?", (vid,)
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else None
