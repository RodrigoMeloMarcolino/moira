import re

PHONE_SEPARATOR_PATTERN = re.compile(r"[\s\-\(\)]")

class CustomerPhoneInvalid(Exception):
    pass

def normalize_customer_phone(value: str) -> str:
    phone = PHONE_SEPARATOR_PATTERN.sub("", value.strip())

    if not phone.startswith("+"):
        raise CustomerPhoneInvalid("customer phone must be in canonical E.164 format")
    
    digits = phone[1:]
    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        raise CustomerPhoneInvalid("customer phone must be in canonical E.164 format")
    
    return phone