from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from typing import Any

from sqlalchemy.orm import Session

from app.models import Card
from worker.validate import matches_sensitivity

logger = logging.getLogger("newsreels.visuals")

# In-memory query cache to preserve Unsplash rate limits
_UNSPLASH_CACHE: dict[str, list[dict[str, Any]]] = {}

SENSITIVE_WORDS = {
    "kill", "dead", "death", "died", "toll", "collapse", "tragedy",
    "murder", "blast", "bomb", "casualt", "victim", "drown", "fire",
    "accident", "suicide", "shooting", "funeral", "grief"
}


def is_sensitive_story(text: str) -> bool:
    """Checks if a story contains sensitive/tragic themes that should NOT use stock photos."""
    if matches_sensitivity(text):
        return True
    tokens = set(re.findall(r"[a-z']+", (text or "").lower()))
    return bool(tokens & SENSITIVE_WORDS)


class UnsplashClient:
    def __init__(self, access_key: str | None = None) -> None:
        self.access_key = access_key or os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
        self.utm = "utm_source=news_reels&utm_medium=referral"

    def search_photo(self, query: str) -> dict[str, str | None]:
        """Search Unsplash for a portrait photo matching the query.
        Returns dict with keys: 'image_url', 'image_author', 'image_author_url'.
        """
        import random
        
        query_clean = query.strip().lower()
        if not query_clean:
            return {"image_url": None, "image_author": None, "image_author_url": None}

        if query_clean not in _UNSPLASH_CACHE:
            if not self.access_key:
                logger.warning("Unsplash access key not configured")
                return {"image_url": None, "image_author": None, "image_author_url": None}

            encoded_query = urllib.parse.quote(query_clean)
            url = (
                f"https://api.unsplash.com/search/photos"
                f"?query={encoded_query}&per_page=30&orientation=portrait"
            )
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Client-ID {self.access_key}",
                    "Accept-Version": "v1",
                },
            )

            try:
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    data = json.loads(resp.read().decode())
                    _UNSPLASH_CACHE[query_clean] = data.get("results", [])
            except Exception as exc:
                logger.warning("Unsplash search failed for '%s': %s", query_clean, exc)
                _UNSPLASH_CACHE[query_clean] = []

        results = _UNSPLASH_CACHE.get(query_clean, [])
        if not results:
            return {"image_url": None, "image_author": None, "image_author_url": None}

        photo = random.choice(results)
        image_url = photo.get("urls", {}).get("regular") or photo.get("urls", {}).get("small")
        user = photo.get("user", {})
        author_name = user.get("name") or user.get("username")
        author_link = user.get("links", {}).get("html")
        if author_link:
            author_link = f"{author_link}?{self.utm}"

        return {
            "image_url": image_url,
            "image_author": author_name,
            "image_author_url": author_link,
        }


def derive_visual_query(card: Card) -> str:
    """Derives a concise, high-relevance search term for Unsplash."""
    headline = (card.headline or "").lower()
    category = (card.category or "").lower()

    # Topic-specific heuristics from headline
    if "ai" in headline or "openai" in headline or "microsoft" in headline or "tech" in headline:
        return "artificial intelligence technology"
    if "plane" in headline or "aircraft" in headline or "airport" in headline:
        return "airplane runway airport"
    if "france" in headline or "modi" in headline or "diplomacy" in headline:
        return "paris diplomacy international relations"
    if "temple" in headline:
        return "architecture monument temple"
    if "parliament" in headline or "assembly" in headline or "politics" in headline or "election" in headline:
        return "government politics assembly"
    if "court" in headline or "sue" in headline or "lawsuit" in headline:
        return "courtroom law justice"
    if "space" in headline or "isro" in headline or "moon" in headline:
        return "space rocket astronomy"

    # Category fallback queries
    category_fallbacks = {
        "tech": "modern technology digital",
        "science": "science research laboratory",
        "national": "india city architecture",
        "international": "world globe international",
        "state": "india landscape city",
        "district": "indian city street",
    }
    return category_fallbacks.get(category, "editorial modern news")


def assign_card_visuals(card: Card, db: Session | None = None) -> None:
    """Assigns CC0 photography or triggers Editorial Typography for sensitive stories."""
    combined_text = f"{card.headline} {card.summary}"

    # 1. Sensitive story check -> Keep image_url=None for Editorial Typographic Card
    if is_sensitive_story(combined_text):
        logger.info("Card %s flagged as sensitive; using Rich Editorial Typography (no stock photo)", card.id)
        card.image_url = None
        card.image_author = None
        card.image_author_url = None
        return

    # 2. General story -> Query Unsplash
    client = UnsplashClient()
    query = derive_visual_query(card)
    photo_data = client.search_photo(query)

    card.image_url = photo_data.get("image_url")
    card.image_author = photo_data.get("image_author")
    card.image_author_url = photo_data.get("image_author_url")

    if card.image_url:
        logger.info("Assigned Unsplash image to card %s via query '%s'", card.id, query)
    else:
        logger.info("No photo found for card %s via query '%s'; falling back to typography", card.id, query)
