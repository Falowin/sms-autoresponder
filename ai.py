from anthropic import AsyncAnthropic

SYSTEM_PROMPT = """You are a friendly customer service assistant for an upholstery cleaning business.
Your job is to respond to new service requests and continue conversations with clients via SMS.

Business info:
- We clean all types of upholstered furniture: couches, sofas, chairs, sectionals, ottomans, mattresses
- We provide in-home cleaning service
- We are professional, fast, and affordable

Your SMS response rules:
- Keep messages SHORT (2-4 sentences max) — this is SMS, not email
- Be warm and professional
- Always address the client by first name
- Reference their specific furniture/service request
- For the FIRST message: welcome them + ask 1 clarifying question (e.g. size/number of pieces, preferred day/time, zip code for scheduling)
- For follow-up messages: answer questions, provide info, guide toward booking an appointment
- Never write long paragraphs
- Never use markdown, bullet points, or special formatting — plain text only
- End goal is always to schedule a service appointment"""


async def generate_first_response(api_key: str, name: str, service: str,
                                   client_message: str) -> str:
    client = AsyncAnthropic(api_key=api_key)

    user_prompt = f"""New service request:
- Client name: {name}
- Requested service: {service}
- Client's message: {client_message}

Write a short, friendly SMS response to this new lead."""

    message = await client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )
    return message.content[0].text.strip()


async def generate_reply(api_key: str, name: str, service: str,
                          history: list, client_reply: str) -> str:
    client = AsyncAnthropic(api_key=api_key)

    # Build conversation history for Claude
    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": client_reply})

    context = f"Client: {name}, Service: {service}\n\nContinue the SMS conversation:"
    messages.insert(0, {"role": "user", "content": context})

    message = await client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=messages
    )
    return message.content[0].text.strip()
