from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    trust_tier: str | int
    name: str = ""
    verified_local_source: bool = False
    wire_attribution: str | None = None
    text: str = ""
    headline: str = ""
    url: str = ""


def canonical_publisher_entity(name: str, url: str = "") -> str:
    """Resolves name/URL to canonical publisher entity identifier.

    Prevents artificial inflation of source counts from:
    - Multiple RSS feeds from the same news organization (e.g. "The Hindu National", "The Hindu Tamil Nadu")
    - Different subdomains/URLs from the same outlet (e.g. "bbc.com", "bbc.co.uk", "BBC News")
    - Syndicated reprint portals or news aggregator links (e.g. Google News)
    - Unresolved sentinel citations (marked as unresolved)
    """
    clean_name = (name or "").strip().lower()
    clean_url = (url or "").strip().lower()

    if not clean_name and not clean_url:
        return "unknown"

    # Sentinel / unresolved provenance
    if (
        "unresolved" in clean_name
        or "legacy unresolved" in clean_name
        or "unknown" in clean_name
    ):
        return "unresolved"

    # Known publisher entity mappings
    if "hindu" in clean_name or "thehindu.com" in clean_url:
        return "the_hindu"
    if "bbc" in clean_name or "bbci.co.uk" in clean_url or "bbc.com" in clean_url:
        return "bbc"
    if "times of india" in clean_name or "indiatimes.com" in clean_url or clean_name == "toi":
        return "times_of_india"
    if "hindustan times" in clean_name or "hindustantimes.com" in clean_url:
        return "hindustan_times"
    if "indian express" in clean_name or "indianexpress.com" in clean_url:
        return "indian_express"
    if "ndtv" in clean_name or "ndtv.com" in clean_url:
        return "ndtv"
    if "reuters" in clean_name or "reuters.com" in clean_url or "reutersagency.com" in clean_url:
        return "reuters"
    if "associated press" in clean_name or "ap news" in clean_name or "apnews.com" in clean_url or clean_name == "ap":
        return "associated_press"
    if "press trust of india" in clean_name or clean_name == "pti":
        return "wire_pti"
    if "asian news international" in clean_name or clean_name == "ani":
        return "wire_ani"
    if "guardian" in clean_name or "theguardian.com" in clean_url:
        return "the_guardian"
    if "amar ujala" in clean_name or "amarujala.com" in clean_url:
        return "amar_ujala"
    if "oneindia" in clean_name or "oneindia.com" in clean_url:
        return "oneindia"
    if "techcrunch" in clean_name or "techcrunch.com" in clean_url:
        return "techcrunch"
    if "the verge" in clean_name or "theverge.com" in clean_url:
        return "the_verge"
    if "nature" in clean_name or "nature.com" in clean_url:
        return "nature"
    if "sciencedaily" in clean_name or "sciencedaily.com" in clean_url:
        return "sciencedaily"

    # If domain can be parsed from URL
    if clean_url:
        try:
            netloc = urlparse(clean_url).netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            if netloc == "news.google.com":
                return "aggregator_unresolved"
            if netloc:
                return f"domain:{netloc}"
        except Exception:
            pass

    return f"name:{clean_name}"


def extract_wire_attribution(text: str) -> str | None:
    """Detect common wire agencies (PTI, AP, Reuters, ANI, IANS, etc.)"""
    if not text:
        return None
    prefix = text[:200]
    match = re.search(r'\b(Reuters|PTI|AP|Associated Press|ANI|IANS|AFP|Bloomberg)\b', prefix, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def _is_independent(s1: SourceRef, s2: SourceRef) -> bool:
    pub1 = canonical_publisher_entity(s1.name, getattr(s1, "url", ""))
    pub2 = canonical_publisher_entity(s2.name, getattr(s2, "url", ""))

    # 1. Unresolved/sentinel or unverified aggregator sources cannot be deemed independent
    if pub1 in ("unresolved", "unknown", "aggregator_unresolved") or pub2 in ("unresolved", "unknown", "aggregator_unresolved"):
        return False

    # 2. Same publisher entity (e.g. two feeds or articles from The Hindu or BBC)
    if pub1 == pub2:
        return False

    # 3. Same source ID
    if s1.source_id and s2.source_id and s1.source_id == s2.source_id:
        return False

    # 4. Same wire service attribution (e.g. both cite PTI or ANI or Reuters wire copy)
    if s1.wire_attribution and s2.wire_attribution and s1.wire_attribution == s2.wire_attribution:
        return False

    # 5. High textual similarity (>= 70% cosine similarity indicates syndicated copy or press release reuse)
    if s1.text and s2.text:
        from worker.cluster import cosine_sim
        if cosine_sim(s1.text, s2.text) >= 0.70:
            return False

    return True


def count_independent_sources(sources: list[SourceRef]) -> list[list[SourceRef]]:
    valid_sources = [
        s for s in sources
        if canonical_publisher_entity(s.name, getattr(s, "url", "")) not in ("unresolved", "unknown", "aggregator_unresolved")
    ]
    groups: list[list[SourceRef]] = []
    for s in valid_sources:
        found_group = False
        for g in groups:
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

    # Filter out unresolved sentinel/unknown citations
    valid_sources = [
        s for s in sources
        if canonical_publisher_entity(s.name, getattr(s, "url", "")) not in ("unresolved", "unknown", "aggregator_unresolved")
    ]
    if len(valid_sources) < 2:
        return False

    independent_groups = count_independent_sources(valid_sources)
    if len(independent_groups) < 2:
        return False

    # At least one independent group must contain a trusted source (Tier 1 or Tier 2)
    has_trusted = any(
        str(s.trust_tier).strip() in ("1", "2", "2.0") or s.trust_tier in (1, 2)
        for s in valid_sources
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

    valid_sources = [
        s for s in sources
        if canonical_publisher_entity(s.name, getattr(s, "url", "")) not in ("unresolved", "unknown", "aggregator_unresolved")
    ]
    independent_groups = count_independent_sources(valid_sources)
    if len(independent_groups) < 2:
        return "single_source"

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
