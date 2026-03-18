"""Section completeness eval: each planned section should be addressed."""

import json

from langchain_openai import ChatOpenAI

RUBRIC = """Score 0-10: Does the report address every planned section from the outline?
- For each section check: is the topic present, is it substantive (>2 sentences), or is it missing/superficial?
- 10 = all sections covered substantively; 0 = most sections missing or trivial."""

RUBRIC_WITH_SECTIONS = """You are an evaluation judge. For each planned section, score 0-10 how well the report addresses it (present, substantive, or missing/superficial). Also give an overall score 0-10.
Output only valid JSON with this exact shape:
{"overall_score": 0-10, "reasoning": "brief overall explanation", "section_scores": [{"section_id": "id", "title": "section title", "score": 0-10, "reason": "one line per section"}]}
Section IDs and titles must match the PLANNED SECTIONS list. Include one entry per planned section."""


def _parse_section_completeness_response(text: str, outline: list[dict]):
    """Parse judge JSON into (overall 0-1, reasoning, list of per-section dicts)."""
    try:
        parsed = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
    except Exception:
        return 0.5, "Parse failed", []
    overall_raw = float(parsed.get("overall_score", 5))
    overall = min(1.0, max(0.0, overall_raw / 10.0))
    reasoning = str(parsed.get("reasoning", "No reasoning provided"))
    section_scores = []
    for s in parsed.get("section_scores") or []:
        if not isinstance(s, dict):
            continue
        raw = float(s.get("score", 5))
        section_scores.append({
            "section_id": str(s.get("section_id", "")),
            "title": str(s.get("title", "")),
            "score": round(min(1.0, max(0.0, raw / 10.0)), 2),
            "reason": str(s.get("reason", "")),
        })
    # If judge omitted sections, fill from outline so we always have one entry per section
    outline_ids = {(x.get("id") or "", x.get("title") or "") for x in outline[:20]}
    seen = {(x["section_id"], x["title"]) for x in section_scores}
    for sid, title in outline_ids:
        if (sid, title) not in seen:
            section_scores.append({"section_id": sid, "title": title, "score": 0.5, "reason": "Not scored by judge"})
    return round(overall, 2), reasoning, section_scores


def eval_section_completeness(
    report_markdown: str, report_outline: list[dict]
) -> tuple[float, str, list[dict]]:
    """Check whether each planned section is addressed. Returns (overall_score, reasoning, section_scores)."""
    if not report_markdown:
        return 0.5, "No report to compare", []
    if not report_outline:
        return 0.5, "No outline to compare", []

    outline_str = "\n".join(
        f"- {s.get('id', '')}: {s.get('title', '')}"
        for s in report_outline[:20]
    )
    report_trunc = report_markdown[:4000] + ("..." if len(report_markdown) > 4000 else "")
    context = f"PLANNED SECTIONS:\n{outline_str}\n\nREPORT:\n{report_trunc}"

    system = f"Output only valid JSON. {RUBRIC_WITH_SECTIONS}"
    user = f"CONTEXT:\n{context}"
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        resp = llm.invoke([{"role": "system", "content": system}, {"role": "user", "content": user}])
        text = resp.content if hasattr(resp, "content") else str(resp)
        return _parse_section_completeness_response(text, report_outline)
    except Exception as e:
        return 0.5, f"eval unavailable: {e}", []


async def async_eval_section_completeness(
    report_markdown: str, report_outline: list[dict]
) -> tuple[float, str, list[dict]]:
    """Async: same as eval_section_completeness, returns (overall_score, reasoning, section_scores)."""
    if not report_markdown:
        return 0.5, "No report to compare", []
    if not report_outline:
        return 0.5, "No outline to compare", []

    outline_str = "\n".join(
        f"- {s.get('id', '')}: {s.get('title', '')}"
        for s in report_outline[:20]
    )
    report_trunc = report_markdown[:4000] + ("..." if len(report_markdown) > 4000 else "")
    context = f"PLANNED SECTIONS:\n{outline_str}\n\nREPORT:\n{report_trunc}"

    system = f"Output only valid JSON. {RUBRIC_WITH_SECTIONS}"
    user = f"CONTEXT:\n{context}"
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        resp = await llm.ainvoke([{"role": "system", "content": system}, {"role": "user", "content": user}])
        text = resp.content if hasattr(resp, "content") else str(resp)
        return _parse_section_completeness_response(text, report_outline)
    except Exception as e:
        return 0.5, f"eval unavailable: {e}", []
