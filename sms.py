import re
from twilio.rest import Client


def normalize_phone(phone: str) -> str:
    """Normalize phone number to E.164 format (+1XXXXXXXXXX for US)."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    elif digits.startswith("+"):
        return digits
    return f"+{digits}"


def send_sms(account_sid: str, auth_token: str,
             from_number: str, to_number: str, body: str) -> str:
    """Send SMS via Twilio. Returns message SID."""
    client = Client(account_sid, auth_token)
    message = client.messages.create(
        body=body,
        from_=from_number,
        to=normalize_phone(to_number)
    )
    return message.sid
