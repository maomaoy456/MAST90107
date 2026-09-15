"""Conservative redaction for anonymous comments and representative issue titles."""
import html
import re


PATTERNS = (
    (r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email removed]"),
    (r"\b(?:https?://|www\.)\S+", "[link removed]"),
    (r"(?i)\b(?:student\s*(?:id|number)|id)\s*[:#-]?\s*[A-Za-z0-9-]{5,}\b", "[student ID removed]"),
    (r"\b\d{6,12}\b", "[number removed]"),
    (r"(?<!\w)(?:\+?\d[\s().-]*){8,15}(?!\w)", "[phone removed]"),
    (r"(?i)\b(?:my name is|name\s*:|student name\s*:)[ ]+[A-Za-z][A-Za-z .'-]{1,60}", "[name removed]"),
    (r"(?<!\w)@[A-Za-z0-9_]{2,30}\b", "[handle removed]"),
)


def anonymous_text(value, limit=800):
    """Remove direct identifiers, markup and controls from display text."""
    if value is None:
        return None
    text = re.sub(r"<[^>]+>", " ", html.unescape(str(value)))
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    for pattern, replacement in PATTERNS:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip() or None
