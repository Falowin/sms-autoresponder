from anthropic import AsyncAnthropic

SYSTEM_PROMPT = """You are a friendly customer service assistant for Fresh Furnish — a professional upholstery cleaning business.

Business info:
- We clean all types of upholstered furniture: couches, sofas, chairs, sectionals, ottomans, mattresses
- We provide in-home cleaning service in the Seattle/Bothell, WA area
- We are professional, fast, and affordable

Your SMS response rules:
- Keep messages SHORT (2-4 sentences max) — this is SMS, not email
- Be warm and professional
- Always address the client by first name
- Reference their specific furniture/service request
- Welcome them and ask 1 clarifying question (e.g. preferred day/time, number of pieces, zip code)
- Never use markdown, bullet points, or special formatting — plain text only
- End goal is always to schedule a service appointment"""


async def generate_variants(api_key: str, name: str, service: str,
                             client_message: str, n: int = 2) -> list[str]:
    """Generate n different SMS response variants for a new lead."""
    client = AsyncAnthropic(api_key=api_key)

    user_prompt = f"""New service request:
- Client name: {name}
- Requested service: {service}
- Client's message: {client_message}

Write {n} different short SMS responses to this lead.
Make each variant slightly different in tone or phrasing.
Separate variants with exactly this marker on its own line: ---VARIANT---
Return ONLY the message texts, nothing else."""

    message = await client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )
    text = message.content[0].text.strip()
    parts = [v.strip() for v in text.split("---VARIANT---") if v.strip()]
    return parts[:n] if len(parts) >= n else parts or [text]
