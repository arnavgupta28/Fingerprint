"""Privacy guardrails: masking, PII-safe logging, rate limiting."""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict, deque

EMAIL_PAT = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PAT = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?)?\d{3,5}[\s.-]?\d{4,5}(?!\d)")


def mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    return f"{local[:1]}•••@{domain}" if domain else "•••"


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 6:
        return "•" * len(digits)
    return f"{digits[:2]}{'•' * (len(digits) - 5)}{digits[-3:]}"


def mask_text_value(value: str, keep: int = 4) -> str:
    """Generic mask for addresses, DOB, etc: keep the first few characters."""
    value = value.strip()
    return value[:keep] + "•••" if len(value) > keep else "•••"


def mask(type_: str, value: str) -> str:
    if type_ == "email":
        return mask_email(value)
    if type_ == "phone":
        return mask_phone(value)
    if type_ in ("address", "dob", "age"):
        return mask_text_value(value, keep=6 if type_ == "address" else 2)
    return value


# Any run of 6+ digits, with or without separators: catches truncated / hyphenated phone fragments
# like "9896830" or "989-683-05…" in page titles, plus PIN codes and ID numbers.
DIGIT_RUN = re.compile(r"(?<![\d•])\+?\d(?:[\s().-]{0,2}\d){5,}(?!\d)")


def redact(text: str) -> str:
    """Mask every email and phone-like number in free text (evidence quotes, page titles, logs)."""
    text = EMAIL_PAT.sub(lambda m: mask_email(m.group(0)), text)
    # Fully masked: partial hints from several fragments could be combined to rebuild a number.
    return DIGIT_RUN.sub(lambda m: "•" * min(10, len(re.sub(r"\D", "", m.group(0)))), text)


class PIIRedactingFilter(logging.Filter):
    """Attach to handlers so personal data never reaches logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            record.args = tuple(redact(str(a)) for a in record.args)
        return True


class RateLimiter:
    """Sliding-window limiter per key (client IP). In-memory: fine for a single instance."""

    def __init__(self, limit: int, window_seconds: int = 3600):
        self.limit = limit
        self.window = window_seconds
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True
