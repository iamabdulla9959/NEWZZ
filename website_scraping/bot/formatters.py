import html
import re
from typing import Dict, Any

# All characters that require escaping in Telegram MarkdownV2 text outside and inside formatting
MARKDOWN_V2_SPECIAL_CHARS = r"([_*\[\]()~`>#+\-=|{}.!])"


def escape_markdown_v2(text: str) -> str:
    """Escapes all Telegram MarkdownV2 reserved characters."""
    if not text:
        return ""
    return re.sub(MARKDOWN_V2_SPECIAL_CHARS, r"\\\1", str(text))


def escape_markdown_v2_url(url: str) -> str:
    """Inside inline link parentheses (...), only ')' and '\\' must be escaped."""
    if not url:
        return ""
    return url.replace("\\", "\\\\").replace(")", "\\)")


def strip_html(raw_html: str) -> str:
    """Strips embedded HTML tags and decodes HTML entities commonly found in RSS descriptions."""
    if not raw_html:
        return ""
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    # Decode entities like &amp;, &quot;, &#39;
    clean = html.unescape(clean)
    # Normalize multiple whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def format_article_markdown_v2(article: Dict[str, Any]) -> str:
    """
    Renders an article into Telegram MarkdownV2 format strictly matching the specification:
      *<title>*
      _<source> — <published_date>_
      <summary, truncated to 300 chars>
      [Read more](<link>)
    """
    title = article.get("title", "Untitled").strip()
    source = article.get("source", "News").strip()
    pub_date = article.get("published_date", "").strip() or "Recent"
    raw_summary = article.get("summary", "") or ""
    link = article.get("link", "").strip()

    # Clean HTML tags and truncate summary to 300 characters
    clean_summary = strip_html(raw_summary)
    if len(clean_summary) > 300:
        clean_summary = clean_summary[:297].rstrip() + "..."
    if not clean_summary:
        clean_summary = "No summary available."

    # Escape individual components
    esc_title = escape_markdown_v2(title)
    esc_source = escape_markdown_v2(source)
    esc_pub_date = escape_markdown_v2(pub_date)
    esc_summary = escape_markdown_v2(clean_summary)
    esc_link = escape_markdown_v2_url(link)

    # Note the en-dash in the metadata line
    en_dash = escape_markdown_v2("—")

    message = (
        f"*{esc_title}*\n"
        f"_{esc_source} {en_dash} {esc_pub_date}_\n\n"
        f"{esc_summary}\n\n"
        f"[Read more]({esc_link})"
    )
    return message
