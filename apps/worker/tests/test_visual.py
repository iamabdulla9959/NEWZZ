from __future__ import annotations

import re
from worker.visual import (
    CATEGORY_PALETTES,
    generate_card_visual,
    get_category_palette,
    render_card_visual_svg,
)


def test_category_palettes_figma_match():
    """Verify category colors match Figma specifications:
    orange=local, teal=state, blue=national, purple=international, green=tech, pink=science
    """
    assert CATEGORY_PALETTES["district"]["primary"] == "#FF7A00"  # Orange
    assert CATEGORY_PALETTES["local"]["primary"] == "#FF7A00"     # Orange
    assert CATEGORY_PALETTES["state"]["primary"] == "#00A896"     # Teal
    assert CATEGORY_PALETTES["national"]["primary"] == "#0267C1"  # Blue
    assert CATEGORY_PALETTES["international"]["primary"] == "#7209B7"  # Purple
    assert CATEGORY_PALETTES["tech"]["primary"] == "#06D6A0"      # Green
    assert CATEGORY_PALETTES["science"]["primary"] == "#F72585"   # Pink


def test_render_card_visual_svg():
    """DoD: A test card renders a category-colored gradient with headline text and nothing else."""
    svg = render_card_visual_svg(
        category="district",
        headline="Chennai City Corporation Initiates Pre-Monsoon Drainage Infrastructure Upgrades",
    )
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "#FF7A00" in svg  # Orange gradient stop
    assert "Chennai City Corporation" in svg
    # Must NOT contain any image tags, image src, or image extensions
    assert "<image" not in svg
    assert "<img" not in svg
    assert "src=" not in svg
    assert "href=" not in svg
    assert not re.search(r"\.(jpg|png|webp|jpeg|gif)", svg, re.IGNORECASE)


def test_generate_card_visual():
    visual = generate_card_visual("tech", "Quantum Chip Breakthrough Announced")
    assert visual["type"] == "typographic_gradient"
    assert visual["colors"]["primary"] == "#06D6A0"
    assert visual["headline"] == "Quantum Chip Breakthrough Announced"
