"""Shared LLM-as-judge infrastructure for evals."""

import json

from langchain_openai import ChatOpenAI


def judge_call(rubric: str, context: str) -> tuple[float, str]:
    """Call gpt-4o-mini with rubric + context, parse JSON, return (score 0-1, reasoning).

    On API/parse failure, returns (0.5, "eval unavailable: <error>").
    """
    system = "You are an evaluation judge. Output only valid JSON: {\"score\": 0-10, \"reasoning\": \"brief explanation\"}."
    user = f"RUBRIC:\n{rubric}\n\nCONTEXT:\n{context}"
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        resp = llm.invoke([{"role": "system", "content": system}, {"role": "user", "content": user}])
        text = resp.content if hasattr(resp, "content") else str(resp)
        parsed = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
        score_raw = float(parsed.get("score", 5))
        reasoning = str(parsed.get("reasoning", "No reasoning provided"))
        score = min(1.0, max(0.0, score_raw / 10.0))
        return round(score, 2), reasoning
    except Exception as e:
        return 0.5, f"eval unavailable: {e}"
