import hashlib
import json
from typing import Any


def build_idempotency_fingerprint(payload: dict[str, Any]) -> str:
    encoded_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')

    return hashlib.sha256(encoded_payload).hexdigest()
