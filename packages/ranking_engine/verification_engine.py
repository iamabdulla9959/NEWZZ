"""
Verification & Trust Engine.
Calculates reliability confidence (0..100) from source quality and multi-source corroboration.
Strictly separated from Importance: answers 'Is it reliable?', not 'Does it matter?'.
"""

from typing import Any, Dict, List
from .config import RankingConfig


class VerificationEngine:
    @staticmethod
    def calculate_verification(
        sources: List[Dict[str, Any]],
        conflict_detected: bool = False,
    ) -> tuple[float, Dict[str, Any]]:
        """
        Computes verification confidence score (0..100) and metadata.
        Evaluates source authority, multi-outlet confirmation, and reporting conflicts.
        """
        if not sources:
            return 40.0, {
                "status": "unverified",
                "source_count": 0,
                "independent_source_count": 0,
                "tier1_source_count": 0,
                "conflict_detected": conflict_detected,
            }

        # Clean publisher entities to prevent double-counting multiple feeds from same publisher
        unique_publishers = set()
        tier1_count = 0
        tier2_count = 0

        for s in sources:
            name = str(s.get("name", "")).strip().lower()
            tier = str(s.get("tier", s.get("trust_tier", ""))).strip().lower()
            url = str(s.get("url", "")).strip().lower()
            # Explicit guard: Sentinel / unresolved sources never count toward publisher diversity or trust
            if (
                not name
                or tier in ("3", "unresolved", "unknown", "legacy_unresolved")
                or "unresolved" in name
                or "legacy unresolved provenance" in name
                or "news.google.com" in url
            ):
                continue

            # Determine canonical entity key
            pub_key = name
            if "hindu" in name or "thehindu.com" in url:
                pub_key = "the_hindu"
            elif "bbc" in name or "bbc.com" in url or "bbci.co.uk" in url:
                pub_key = "bbc"
            elif "times of india" in name or "indiatimes.com" in url or name == "toi":
                pub_key = "times_of_india"
            elif "hindustan times" in name or "hindustantimes.com" in url:
                pub_key = "hindustan_times"
            elif "indian express" in name or "indianexpress.com" in url:
                pub_key = "indian_express"
            elif "ndtv" in name or "ndtv.com" in url:
                pub_key = "ndtv"
            elif "reuters" in name or "reuters.com" in url:
                pub_key = "reuters"
            elif "associated press" in name or "apnews.com" in url or name == "ap":
                pub_key = "associated_press"
            elif "guardian" in name or "theguardian.com" in url:
                pub_key = "the_guardian"

            if pub_key not in unique_publishers:
                unique_publishers.add(pub_key)
                if any(t in name for t in RankingConfig.TIER_1_SOURCES):
                    tier1_count += 1
                elif any(t in name for t in RankingConfig.TIER_2_SOURCES):
                    tier2_count += 1

        independent_count = len(unique_publishers)

        # Conflict penalty
        if conflict_detected:
            score = 45.0
            status = "flagged_conflict"
        # Multiple Tier-1 sources corroborate
        elif tier1_count >= 2:
            score = min(100.0, 95.0 + (independent_count * 1.0))
            status = "cross_verified_tier1"
        # Single Tier-1 wire or official source
        elif tier1_count == 1 and independent_count >= 2:
            score = 90.0
            status = "cross_verified"
        elif tier1_count == 1:
            score = 88.0
            status = "official_wire_confirmed"
        # Multiple Tier-2 reputable sources
        elif independent_count >= 2:
            score = 82.0
            status = "multi_source_corroborated"
        # Single reputable source
        elif tier2_count == 1:
            score = 70.0
            status = "single_reputable_source"
        else:
            score = 55.0
            status = "single_unconfirmed_source"

        meta = {
            "status": status,
            "source_count": len(sources),
            "independent_source_count": independent_count,
            "tier1_source_count": tier1_count,
            "conflict_detected": conflict_detected,
        }
        return round(score, 2), meta
