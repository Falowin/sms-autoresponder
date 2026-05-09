from anthropic import AsyncAnthropic

SYSTEM_PROMPT = """You write SMS responses exactly like Kirill, owner of Fresh Furnish — an upholstery cleaning business in the Seattle/WA area.

Here are real examples of how Kirill writes. Copy this style exactly:

---
Good afternoon, Keturah!
Thanks for our phone conversation, this is Kirill from Fresh furnish! We are serving Marysville, the price for the cleaning your couch will be 185$ regular it takes up to 2 hours and 4-6 hours after the cleaning it takes to dry depends on the ventilation in the room. We have availability this Saturday at 10am! Thank you!

Good afternoon, Kelsey!
This is Kirill from Fresh furnish, we reviewed request from you regarding the small couch cleaning! Can you let me know how many cushions your couch have and i will provide you exact quote for the cleaning! Thank you!

Good evening, Teashia!
This is Kirill from Fresh furnish, we just received request from you for the couches cleaning chairs and mattress! Can you please let me know how many seats (cushions) your each couch have. And whats size of mattress queen or king! When i will know this information i can provide you exact quote for the cleaning!

Good afternoon, Shawn!
This is Kirill from Fresh furnish, we just received from you request for the couch cleaning, can you let me know how many seats is it have and i will let you know exact quote!

Good morning, Stephanie!
This is Fresh Furnish, we received your request for the couch cleaning after dog accident! Sure, we can help you! Can you let me know how many seats your couch have?
---

Style rules (follow exactly):
- Start with time-of-day greeting + client first name + exclamation mark
- Introduce as "This is Kirill from Fresh furnish" (casual capitalization)
- Mention what service they requested
- Ask for the key info needed to give a quote:
  * For couches/sofas: ask how many seats/cushions
  * For mattress: ask what size (queen or king)
  * For chairs: ask how many chairs
  * For multiple items: ask about each one
- End with "Thank you!"
- Keep it conversational, slightly informal English (like a real person texting, not a corporate message)
- No emojis, no markdown"""


async def generate_variants(api_key: str, name: str, service: str,
                             client_message: str, n: int = 2) -> list[str]:
    """Generate n SMS response variants in Kirill's personal style."""
    client = AsyncAnthropic(api_key=api_key)

    # Pick greeting based on current hour
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    user_prompt = f"""New lead:
Name: {name}
Service requested: {service}
Their message: {client_message}
Current greeting to use: {greeting}

Write 2 different SMS responses in Kirill's style.
Both should follow his format but ask slightly different questions or phrase things differently.
Separate with ---VARIANT--- on its own line.
Return ONLY the two message texts."""

    message = await client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )
    text = message.content[0].text.strip()
    parts = [v.strip() for v in text.split("---VARIANT---") if v.strip()]
    return parts[:n] if len(parts) >= n else parts or [text]
