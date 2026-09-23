# File: DjangoVerseHub/apps/comments/moderation.py
"""
Shared heuristics used by the comment form and the auto-moderation task.

The form only *rejects* content that is clearly unusable (too short,
shouting); everything else is accepted and, if suspicious, flagged for a
human moderator by ``should_flag``.
"""

import re

SPAM_PATTERNS = [
    re.compile(r"https?://\S+", re.IGNORECASE),  # URLs
    re.compile(r"\bwww\.\S+", re.IGNORECASE),
    re.compile(r"\b(buy now|discount|cheap|prize|casino|lottery)\b", re.IGNORECASE),
    re.compile(r"(.)\1{5,}"),  # the same character repeated 6+ times
]

INAPPROPRIATE_WORDS = ["scam", "stupid", "idiot"]
_INAPPROPRIATE_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in INAPPROPRIATE_WORDS) + r")\b",
    re.IGNORECASE,
)

MAX_CAPS_RATIO = 0.8
MIN_CAPS_CHECK_LENGTH = 20


def caps_ratio(content):
    letters = [c for c in content if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c.isupper()) / len(letters)


def is_shouting(content):
    """More than 80% capital letters in a comment of meaningful length."""
    return len(content) >= MIN_CAPS_CHECK_LENGTH and caps_ratio(content) > MAX_CAPS_RATIO


def should_flag(content):
    """Return True when the content looks like spam or abuse."""
    if any(p.search(content) for p in SPAM_PATTERNS):
        return True
    if _INAPPROPRIATE_RE.search(content):
        return True
    return is_shouting(content)
