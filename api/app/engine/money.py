from decimal import ROUND_HALF_UP, Decimal


def fmt_inr(paise: int) -> str:
    """Indian digit grouping: 123456700 paise -> ₹12,34,567."""
    sign = "-" if paise < 0 else ""
    rupees, p = divmod(abs(paise), 100)
    s = str(rupees)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return f"{sign}₹{s}" + (f".{p:02d}" if p else "")


def pct_of(paise: int, rate: float) -> int:
    """Integer paise * rate, round half up. Decimal avoids float drift."""
    return int((Decimal(paise) * Decimal(str(rate))).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def midpoint_rupee_paise(lo: int, hi: int) -> int:
    """Midpoint rounded half-up to a whole rupee, in paise."""
    return ((lo + hi) // 2 + 50) // 100 * 100
