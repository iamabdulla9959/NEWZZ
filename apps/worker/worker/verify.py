from __future__ import annotations

from dataclasses import dataclass


import re

@dataclass(frozen=True)
class SourceRef:
    source_id: str
    trust_tier: str | int
    name: str = ""
    verified_local_source: bool = False
    wire_attribution: str | None = None
    text: str = ""
    headline: str = ""


def extract_wire_attribution(text: str) -> str | None:
    """Detect common wire agencies (PTI, AP, Reuters, ANI, IANS, etc.)"""
    if not text:
        return None
    # Look for tags like "(Reuters)", "PTI -", "By AP", etc in the first 200 chars
    prefix = text[:200]
    match = re.search(r'\b(Reuters|PTI|AP|Associated Press|ANI|IANS|AFP|Bloomberg)\b', prefix, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None

def _is_independent(s1: SourceRef, s2: SourceRef) -> bool:
    if s1.wire_attribution and s2.wire_attribution and s1.wire_attribution == s2.wire_attribution:
        return False
    from worker.cluster import cosine_sim
    # Overlap >= 80% is considered same syndicated copy
    if cosine_sim(s1.text, s2.text) >= 0.8:
        return False
    return True

def count_independent_sources(sources: list[SourceRef]) -> list[list[SourceRef]]:
    groups: list[list[SourceRef]] = []
    for s in sources:
        found_group = False
        for g in groups:
            # If it matches any source in the group, it belongs to that group
            if not _is_independent(s, g[0]):
                g.append(s)
                found_group = True
                break
        if not found_group:
            groups.append([s])
    return groups

def is_publish_eligible(sources: list[SourceRef], scope: str = "") -> bool:
    """
    VERIFIED = >= 2 truly independent sources AND at least one source meets minimum trust threshold
    OFFICIAL = 1 recognized official/government source
    """
    is_local = scope.strip().lower() in ("district", "local")

    official_local_count = sum(
        1
        for s in sources
        if str(s.trust_tier).strip().lower() in ("official_local", "official")
        and getattr(s, "verified_local_source", False) is True
    )
    if is_local and official_local_count >= 1:
        return True
        
    independent_groups = count_independent_sources(sources)
    if len(independent_groups) < 2:
        return False
        
    # At least one independent group must contain a trusted source (Tier 1 or Tier 2)
    has_trusted = any(
        str(s.trust_tier).strip() in ("1", "2", "2.0") or s.trust_tier in (1, 2)
        for s in sources
    )
    return has_trusted


def determine_verification_type(
    sources: list[SourceRef],
    scope: str = "",
    flagged_conflict: bool = False,
) -> str:
    """Determine card verification type:
    'cross_verified' | 'official_source' | 'flagged_conflict'
    """
    if flagged_conflict:
        return "flagged_conflict"

    is_local = scope.strip().lower() in ("district", "local")
    official_local_count = sum(
        1
        for s in sources
        if str(s.trust_tier).strip().lower() in ("official_local", "official")
        and getattr(s, "verified_local_source", False) is True
    )

    if is_local and official_local_count == 1 and len(sources) == 1:
        return "official_source"

    return "cross_verified"


def relative_difference(a: float, b: float) -> float:
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom


def detect_numeric_conflicts(
    facts_by_key: dict[str, list[float]],
    threshold: float = 0.20,
) -> list[str]:
    """FR4: if key numeric facts differ >20%, flag conflict."""
    notes: list[str] = []
    for key, values in facts_by_key.items():
        if len(values) < 2:
            continue
        lo, hi = min(values), max(values)
        if relative_difference(lo, hi) > threshold:
            notes.append(f"Reports differ on {key}")
    return notes
