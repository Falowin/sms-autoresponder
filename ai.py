from anthropic import AsyncAnthropic

SYSTEM_PROMPT = """You are writing SMS responses on behalf of Kyrylo, owner of Fresh Furnish — a professional upholstery cleaning business in Bothell, WA.

Business info:
- We clean couches, sofas, chairs, sectionals, ottomans, mattresses — all upholstery
- In-home service, Seattle/Bothell area
- Fast, affordable, professional

Writing style rules:
- Sound like a real person texting, not a corporate bot
- Short and conversational — 2-3 sentences max
- Address client by first name
- Mention their specific item/service
- End with ONE question to move things forward (availability, location, size, etc.)
- No emojis, no exclamation overload, no "Great!" or "Awesome!" openers
- Plain text only — no formatting"""


async def generate_variants(api_key: str, name: str, service: str,
                             client_message: str, n: int = 2) -> list[str]:
    """Generate n meaningfully different SMS response variants for a new lead."""
    client = AsyncAnthropic(api_key=api_key)

    user_prompt = f"""New lead came in:
Name: {name}
Service: {service}
Their message: {client_message}

Write 2 SMS responses. They must be NOTICEABLY different — not just different wording of the same structure. For example:
- Variant 1: direct and to the point, jump straight to scheduling
- Variant 2: a bit more personal, acknowledge what they said, then move to next step

Separate with ---VARIANT--- on its own line.
Return ONLY the two message texts, nothing else."""

    message = await client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )
    text = message.content[0].text.strip()
    parts = [v.strip() for v in text.split("---VARIANT---") if v.strip()]
    return parts[:n] if len(parts) >= n else parts or [text]
