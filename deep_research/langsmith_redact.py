"""Redact raw fetched content from payloads before sending to LangSmith.

Only values that hold web-fetched content (from Tavily, Exa, Gensee, or any
search provider) are replaced. LLM inputs/outputs (e.g. messages with "role"
and "content") are not redacted.
"""

# Keys that are only ever used for search/fetch content — safe to always redact
SEARCH_ONLY_KEYS = frozenset({
    "snippet",
    "raw_content",
    "body",
    "excerpt",
    "highlights",
})
# Keys that appear in both search results and LLM messages — redact only inside search-result-like dicts (have "url")
CONTENT_KEYS_IN_SEARCH_RESULTS = frozenset({"content", "text"})
MAX_DEPTH = 30


def _placeholder(s: str) -> str:
    """Single placeholder for a redacted string."""
    return f"[REDACTED, {len(s)} chars]" if s else ""


def _is_search_result_like(obj: dict) -> bool:
    """True if this dict looks like a search hit (has url), not an LLM message (has role)."""
    if not isinstance(obj, dict):
        return False
    return "url" in obj and "role" not in obj


def redact_raw_content_in_payload(payload, depth: int = 0):
    """Return a deep copy with raw search/fetch content redacted; LLM content is left as-is.

    - Always redacts: snippet, raw_content, body, excerpt, highlights (search-only keys).
    - Redacts content/text only when inside a dict that has "url" (search result), not in messages.
    """
    if depth > MAX_DEPTH:
        return payload
    if isinstance(payload, dict):
        out = {}
        is_search_like = _is_search_result_like(payload)
        for k, v in payload.items():
            if k in SEARCH_ONLY_KEYS:
                if isinstance(v, str):
                    out[k] = _placeholder(v)
                elif k == "highlights" and isinstance(v, list):
                    out[k] = [_placeholder(x) if isinstance(x, str) else redact_raw_content_in_payload(x, depth + 1) for x in v]
                else:
                    out[k] = redact_raw_content_in_payload(v, depth + 1)
            elif is_search_like and k in CONTENT_KEYS_IN_SEARCH_RESULTS and isinstance(v, str):
                out[k] = _placeholder(v)
            else:
                out[k] = redact_raw_content_in_payload(v, depth + 1)
        return out
    if isinstance(payload, list):
        return [redact_raw_content_in_payload(x, depth + 1) for x in payload]
    if isinstance(payload, tuple):
        return tuple(redact_raw_content_in_payload(x, depth + 1) for x in payload)
    return payload
