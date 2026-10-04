"""Turning human text into URL-safe slugs.

Pure functions: no database, no I/O. Checking whether a slug is already taken
needs the database, so that loop lives in the service, not here.
"""

import re
import unicodedata

MAX_SLUG_LENGTH = 100

_NOT_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


def slugify(text: str, fallback: str) -> str:
    """'Jane Doe!' -> 'jane-doe'.

    Accented letters are reduced to their plain form (é -> e). Anything else
    outside a-z and 0-9 becomes a single hyphen. If nothing usable remains —
    a name written entirely in a non-Latin script, say — the fallback is used.
    """
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = _NOT_SLUG_CHARS.sub("-", plain.lower()).strip("-")
    slug = slug[:MAX_SLUG_LENGTH].rstrip("-")
    return slug or fallback


def with_discriminator(base: str, number: int) -> str:
    """('jane-doe', 2) -> 'jane-doe-2', trimming the base so the result
    still fits within the length limit."""
    suffix = f"-{number}"
    return base[: MAX_SLUG_LENGTH - len(suffix)].rstrip("-") + suffix