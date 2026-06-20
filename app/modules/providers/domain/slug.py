import re
import secrets
import unicodedata
from typing import Optional

MAX_PROVIDER_SLUG_LENGTH = 80
PROVIDER_SLUG_SUFFIX_BYTES = 4
DEFAULT_PROVIDER_SLUG_BASE = 'provider'

NON_ALNUM_PATTERN = re.compile(r'[^a-z0-9]+')
HYPHEN_RUN_PATTERN = re.compile(r'-+')


def _slugify_base(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value.strip())
    ascii_value = normalized.encode('ascii', 'ignore').decode('ascii').lower()
    slug = NON_ALNUM_PATTERN.sub('-', ascii_value)
    slug = HYPHEN_RUN_PATTERN.sub('-', slug).strip('-')

    return slug or DEFAULT_PROVIDER_SLUG_BASE


def _truncate_base(base: str, suffix: str) -> str:
    max_base_length = MAX_PROVIDER_SLUG_LENGTH - len(suffix) - 1
    if max_base_length < 1:
        msg = 'slug suffix is too long'
        raise ValueError(msg)

    truncated = base[:max_base_length].rstrip('-')
    if truncated:
        return truncated

    fallback = DEFAULT_PROVIDER_SLUG_BASE[:max_base_length].rstrip('-')
    return fallback or DEFAULT_PROVIDER_SLUG_BASE[:max_base_length]


def generate_provider_slug(display_name: str, *, suffix: Optional[str] = None) -> str:
    base = _slugify_base(display_name)
    slug_suffix = suffix or secrets.token_hex(PROVIDER_SLUG_SUFFIX_BYTES)
    truncated_base = _truncate_base(base, slug_suffix)
    return f'{truncated_base}-{slug_suffix}'
