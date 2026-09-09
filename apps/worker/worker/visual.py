from __future__ import annotations

from typing import Any

# Color templates matching Figma specification
CATEGORY_PALETTES: dict[str, dict[str, str]] = {
    "district": {
        "primary": "#FF7A00",  # Orange
        "secondary": "#E05300",
        "accent": "#FFA94D",
        "text": "#FFFFFF",
        "name": "Local / District",
    },
    "local": {
        "primary": "#FF7A00",
        "secondary": "#E05300",
        "accent": "#FFA94D",
        "text": "#FFFFFF",
        "name": "Local / District",
    },
    "state": {
        "primary": "#00A896",  # Teal
        "secondary": "#028090",
        "accent": "#7CDBD5",
        "text": "#FFFFFF",
        "name": "State",
    },
    "national": {
        "primary": "#0267C1",  # Blue
        "secondary": "#1D2D44",
        "accent": "#4EA8DE",
        "text": "#FFFFFF",
        "name": "National",
    },
    "international": {
        "primary": "#7209B7",  # Purple
        "secondary": "#3A0CA3",
        "accent": "#B5179E",
        "text": "#FFFFFF",
        "name": "International",
    },
    "tech": {
        "primary": "#06D6A0",  # Green
        "secondary": "#0B525B",
        "accent": "#52B788",
        "text": "#0B0F14",
        "name": "Technology",
    },
    "science": {
        "primary": "#F72585",  # Pink
        "secondary": "#7209B7",
        "accent": "#FF70A6",
        "text": "#FFFFFF",
        "name": "Science",
    },
}

DEFAULT_PALETTE = CATEGORY_PALETTES["national"]


def get_category_palette(category: str) -> dict[str, str]:
    normalized = (category or "").strip().lower()
    return CATEGORY_PALETTES.get(normalized, DEFAULT_PALETTE)


def generate_card_visual(category: str, headline: str) -> dict[str, Any]:
    """Generates visual configuration for a typographic category card without external images."""
    palette = get_category_palette(category)
    return {
        "type": "typographic_gradient",
        "category": category,
        "headline": headline,
        "colors": {
            "primary": palette["primary"],
            "secondary": palette["secondary"],
            "accent": palette["accent"],
            "text": palette["text"],
        },
    }


def render_card_visual_svg(category: str, headline: str, width: int = 800, height: int = 500) -> str:
    """Renders a pure SVG typographic card: headline text overlaid on a category-colored gradient."""
    palette = get_category_palette(category)
    safe_headline = (
        headline.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    # Word wrapping into lines for SVG display
    words = safe_headline.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        if sum(len(x) for x in cur) + len(cur) + len(w) > 32:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))

    tspan_elements = ""
    y_start = height // 2 - (len(lines) * 20)
    for i, line in enumerate(lines):
        tspan_elements += f'<tspan x="48" y="{y_start + (i * 46)}">{line}</tspan>\n'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{palette['primary']}" />
      <stop offset="100%" stop-color="{palette['secondary']}" />
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#grad)" rx="16" />
  <rect x="48" y="48" width="110" height="32" rx="16" fill="{palette['accent']}" fill-opacity="0.3" />
  <text x="103" y="69" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="700" fill="{palette['text']}" text-transform="uppercase" letter-spacing="1">
    {category.upper()}
  </text>
  <text font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="34" font-weight="800" fill="{palette['text']}" letter-spacing="-0.5">
    {tspan_elements}
  </text>
</svg>"""
