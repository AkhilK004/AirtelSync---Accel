"""Identifier formats and checksums. Calibrated on the mock registries (docs/data_contract.md): GSTIN checksum 100% -> enforced."""
from __future__ import annotations

import re

_C = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")  # 4th PAN char may be X in the dataset (README)
UDYAM_RE = re.compile(r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$")
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
SYN_ID_RE = re.compile(r"^SYN-ID-\d{6}$")
PAN_ENTITY_CHARS = set("ABCFGHLJPTX")  # X: synthetic dataset PANs

GST_STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana",
    "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland",
    "14": "Manipur", "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand",
    "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat", "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
}


def norm_gstin(s: str | None) -> str | None:
    return re.sub(r"[\s\-]", "", s).upper() if s else None


def norm_udyam(s: str | None) -> str | None:
    if not s:
        return None
    t = re.sub(r"[\s\-_]", "", s).upper()
    m = re.fullmatch(r"UDYAM([A-Z]{2})(\d{2})(\d{7})", t)
    return f"UDYAM-{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else s.strip().upper()


def gstin_format_ok(g: str | None) -> bool:
    return bool(g and GSTIN_RE.match(g))


def gstin_checksum_ok(g: str) -> bool:
    s = sum((p // 36 + p % 36) for p in (_C.index(c) * (1 + i % 2) for i, c in enumerate(g[:14])))
    return _C[(36 - s % 36) % 36] == g[14]


def udyam_format_ok(u: str | None) -> bool:
    return bool(u and UDYAM_RE.match(u))


def pan_format_ok(p: str | None) -> bool:
    return bool(p and PAN_RE.match(p))


def pan_entity_ok(p: str) -> bool:
    return p[3] in PAN_ENTITY_CHARS


# ---- Verhoeff (Aadhaar)
_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
      [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1], [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
      [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
      [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1], [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]


def verhoeff_ok(num: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def aadhaar_ok(num: str | None) -> bool:
    d = re.sub(r"\D", "", num or "")
    return len(d) == 12 and d[0] not in "01" and verhoeff_ok(d)


def mask_aadhaar(num: str | None) -> str | None:
    d = re.sub(r"\D", "", num or "")
    return "XXXXXXXX" + d[-4:] if len(d) >= 4 else None
