from __future__ import annotations

from app.config import (MANUFACTURING_KEYWORDS, MULTI_SITE_MAX_LOCATIONS, MULTI_SITE_MIN_LOCATIONS,
                        PROFESSIONAL_KEYWORDS)
from app.data.loaders import get_data
from app.models.engine import Note, Profile, Segment

# business_type -> segment comes from the leads data (loaders.business_type_segments)
_SEG_MAP = {"Small manufacturers": Segment.MANUFACTURER, "Small multi-site businesses": Segment.MULTI_SITE,
            "Professional offices": Segment.PROFESSIONAL, "Micro retail & services": Segment.MICRO_RETAIL}


def classify(profile: Profile) -> tuple[Segment, list[Note]]:
    """Precedence: manufacturer > multi-site (locations>=MIN) > professional > micro."""
    notes: list[Note] = []
    known = {k.lower(): v for k, v in get_data().business_type_segments().items()}
    bt = (profile.business_type or "").strip().lower()
    base = _SEG_MAP.get(known.get(bt)) if bt in known else None
    if base is None:
        # unknown business type: generic keywords first (clinic, factory...), then size only
        if any(k in bt for k in MANUFACTURING_KEYWORDS):
            base = Segment.MANUFACTURER
        elif any(k in bt for k in PROFESSIONAL_KEYWORDS):
            base = Segment.PROFESSIONAL
        else:
            base = Segment.MICRO_RETAIL if profile.employees <= 6 else Segment.PROFESSIONAL
            notes.append(Note(key="business_type_unknown", params={"employees": profile.employees},
                              text=f"We could not match your business type, so we sized you by team ({profile.employees} people)."))
    if base == Segment.MANUFACTURER:
        return base, notes
    if profile.locations >= MULTI_SITE_MIN_LOCATIONS:
        return Segment.MULTI_SITE, notes
    if base == Segment.MULTI_SITE:  # chain type but only 1-2 locations declared
        base = Segment.PROFESSIONAL if profile.employees > 6 else Segment.MICRO_RETAIL
    return base, notes


def is_assisted(segment: Segment, profile: Profile) -> tuple[bool, str | None]:
    if segment == Segment.MANUFACTURER:
        return True, "needs_site_survey"
    if profile.locations > MULTI_SITE_MAX_LOCATIONS:
        return True, "needs_site_survey"
    return False, None
