"""PII redaction for logs (PLAN 6.9): phones, Aadhaar-like 12 digits, PAN, GSTIN (keep first 2 + last 3), emails."""
from __future__ import annotations

import logging
import re

_RULES: list[tuple[re.Pattern, object]] = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"), lambda m: m.group(0)[:2] + "*" * 10 + m.group(0)[-3:]),  # GSTIN
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[pan]"),
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"), "[12-digit]"),
    (re.compile(r"(?<!\d)(?:\+91[ -]?)?[6-9]\d{9}(?!\d)"), "[phone]"),
]


def redact(text: str) -> str:
    for pat, rep in _RULES:
        text = pat.sub(rep, text)  # type: ignore[arg-type]
    return text


class RedactionFilter(logging.Filter):
    """Redacts the message and every string argument but KEEPS the args tuple: uvicorn's access formatter unpacks 5 positional args."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
        return True


def install() -> None:
    f = RedactionFilter()
    root = logging.getLogger()
    root.addFilter(f)
    for h in root.handlers:
        h.addFilter(f)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "advisor", "kyc"):
        logging.getLogger(name).addFilter(f)
