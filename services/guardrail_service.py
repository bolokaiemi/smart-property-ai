import re

# Simple list of prohibited words (case‑insensitive). Extend as needed.
PROHIBITED_WORDS = [
    "damn",
    "shit",
    "fuck",
    "crap",
    "bastard",
    "stupid",
]

def _censor_text(text: str) -> str:
    """Replace prohibited words with asterisks while preserving length.
    Example: "damn" -> "****".
    """
    def repl(match):
        word = match.group(0)
        return "*" * len(word)

    pattern = re.compile(r"\b(" + "|".join(map(re.escape, PROHIBITED_WORDS)) + r")\b", re.IGNORECASE)
    return pattern.sub(repl, text)

def _titlecase_headings(text: str) -> str:
    """Convert fully‑uppercase headings to title case.
    Handles lines that start with optional markdown heading markers (#, ##, etc.)
    or lines that are entirely uppercase.
    """
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        # Detect markdown heading markers
        heading_match = re.match(r"^(#+\s*)(.*)", stripped)
        if heading_match:
            marker, content = heading_match.groups()
            # If content is all caps, title‑case it
            if content.isupper():
                content = content.title()
            lines.append(f"{marker}{content}")
        elif line.isupper():
            lines.append(line.title())
        else:
            lines.append(line)
    return "\n".join(lines)

def apply_professional_guardrails(text: str) -> str:
    """Apply a simple professional‑tone guardrail to AI output.

    The guardrail performs two steps:
    1. Censor prohibited vocabulary.
    2. Convert headings that are written in all caps to title case.
    """
    cleaned = _censor_text(text)
    cleaned = _titlecase_headings(cleaned)
    return cleaned
