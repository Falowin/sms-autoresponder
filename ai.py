from anthropic import AsyncAnthropic

KIRILL_STYLE = """You write SMS responses exactly like Kirill, owner of Fresh Furnish — an upholstery cleaning business in the Seattle/WA area.

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
- Introduce as "This is Kirill from Fresh furnish"
- Mention what service they requested
- Ask for info needed for quote (seats/cushions for couches, size for mattress, etc.)
- End with "Thank you!"
- Conversational, slightly informal English
- No emojis, no markdown"""

SALES_STYLE = """You write high-converting sales SMS responses for Fresh Furnish — an upholstery cleaning business in Seattle/WA area, owned by Kirill.

Goal: turn a cold lead into a booked appointment as fast as possible.

Sales tactics to use:
- Create mild urgency (limited slots, weekend availability filling up)
- Build trust quickly (mention experience, satisfaction guarantee, or that you serve their area)
- Make it easy to say yes (offer a specific time slot right away)
- Give a sense of value (fast drying, professional equipment, before/after results)
- End with a clear call to action — get them to confirm or reply with one piece of info

Style:
- Start with time-of-day greeting + client first name
- Introduce as "This is Kirill from Fresh Furnish"
- Enthusiastic but not pushy
- Slightly more polished than casual texting
- Short — 3-4 sentences max
- No emojis, no markdown, plain text only"""


async def generate_variants(api_key: str, name: str, service: str,
                             client_message: str) -> list[str]:
    """Generate 3 SMS variants: 2 in Kirill's natural style + 1 sales-focused."""
    client = AsyncAnthropic(api_key=api_key)

    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    lead_context = f"""New lead:
Name: {name}
Service requested: {service}
Their message: {client_message}
Current greeting: {greeting}"""

    # Generate 2 variants in Kirill's natural style
    resp1 = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=KIRILL_STYLE,
        messages=[{"role": "user", "content": f"""{lead_context}

Write 2 different SMS responses in Kirill's style.
Separate with ---VARIANT--- on its own line.
Return ONLY the two message texts."""}]
    )
    text1 = resp1.content[0].text.strip()
    kirill_variants = [v.strip() for v in text1.split("---VARIANT---") if v.strip()]

    # Generate 1 sales-focused variant
    resp2 = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SALES_STYLE,
        messages=[{"role": "user", "content": f"""{lead_context}

Write 1 sales-focused SMS response that creates urgency and pushes toward booking.
Return ONLY the message text."""}]
    )
    sales_variant = resp2.content[0].text.strip()

    all_variants = kirill_variants[:2] + [sales_variant]
    return all_variants
