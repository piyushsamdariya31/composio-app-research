"""The research agent: one tool-using loop per app.

Claude (via the Anthropic API) gets Composio tools for web search and page reading
(TAVILY_SEARCH, TAVILY_EXTRACT, FIRECRAWL_SCRAPE) plus one local tool, `submit_research`,
whose JSON schema is the rubric (spec/rubric.md). The loop enforces the one rule that
matters most for accuracy:

    every evidence URL must be a page the agent actually opened in this run.

A submission that cites an unopened URL, breaks a consistency rule (verify/validate.py)
or leaves a field empty is rejected and sent back with the reason, up to MAX_REPAIRS times.
After that the row is saved with confidence=low so a human looks at it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from agent.schema import ACCESS, API_TYPE, AUTH, BLOCKER, BREADTH, CONFIDENCE, MCP, ROOT, VERDICT, derive
from verify.validate import check

COMPOSIO_TOOLS = ["TAVILY_SEARCH", "TAVILY_EXTRACT", "FIRECRAWL_SCRAPE"]
MAX_STEPS = 14
MAX_REPAIRS = 2
URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")

SUBMIT_TOOL = {
    "name": "submit_research",
    "description": "Submit the finished research row for this app. Call exactly once, at the end.",
    "input_schema": {
        "type": "object",
        "required": ["what_it_does", "auth", "primary_auth", "access", "api_type", "api_breadth",
                     "mcp", "verdict", "blocker", "evidence", "confidence"],
        "properties": {
            "what_it_does": {"type": "string", "description": "One line, at most 14 words."},
            "auth": {"type": "array", "items": {"enum": AUTH}, "minItems": 1},
            "primary_auth": {"enum": AUTH},
            "primary_reason": {"type": "string", "description": "Required when OAuth2 is offered but not primary."},
            "access": {"enum": ACCESS},
            "api_type": {"enum": API_TYPE},
            "api_breadth": {"enum": BREADTH},
            "mcp": {"enum": MCP},
            "verdict": {"enum": VERDICT},
            "blocker": {"enum": BLOCKER},
            "confidence": {"enum": CONFIDENCE},
            "notes": {"type": "string"},
            "evidence": {
                "type": "array", "minItems": 1,
                "items": {"type": "object", "required": ["field", "url", "quote"],
                          "properties": {"field": {"type": "string"}, "url": {"type": "string"},
                                         "quote": {"type": "string", "description": "Short phrase copied from the page."}}},
            },
        },
    },
}


def system_prompt() -> str:
    rubric = (ROOT / "spec" / "rubric.md").read_text()
    return (
        "You research one SaaS app so Composio can decide whether to build an agent toolkit for it.\n"
        "Work like a careful analyst:\n"
        "1. Find the vendor's own developer docs (prefer the hint domain). Read the authentication page.\n"
        "2. Find how a developer gets credentials: free plan, developer account, trial, paid plan, approval, or sales. "
        "Read the pricing page's API row: a free plan existing does NOT mean the API is free.\n"
        "3. Check for an MCP server published by the vendor. A docs-search MCP that cannot touch the user's account "
        "does not count as official.\n"
        "4. Only cite pages you opened with a tool in this conversation, each with a short quote copied from it.\n"
        "5. If the docs are gated, missing or contradictory, say so in notes and lower confidence. "
        "A gate with evidence is a correct finding, not a failure.\n\n"
        f"RUBRIC (closed sets, follow exactly):\n{rubric}"
    )


class LLM(Protocol):
    def create(self, **kw: Any) -> Any: ...


class ToolRunner(Protocol):
    def tools(self) -> list[dict]: ...
    def execute(self, tool_call: Any) -> dict: ...


@dataclass
class Trace:
    opened_urls: set[str] = field(default_factory=set)
    steps: list[dict] = field(default_factory=list)
    repairs: int = 0


def _norm(url: str) -> str:
    return url.split("#")[0].rstrip("/").lower().replace("://www.", "://")


def urls_opened_by(tool_name: str, tool_input: dict, result: dict) -> set[str]:
    """A page counts as opened if we scraped/extracted it, or a search returned its content."""
    found: set[str] = set()
    if tool_name in ("FIRECRAWL_SCRAPE", "TAVILY_EXTRACT"):
        for k in ("url", "urls"):
            v = tool_input.get(k)
            for u in ([v] if isinstance(v, str) else v or []):
                found.add(u)
    if tool_name in ("TAVILY_SEARCH", "TAVILY_EXTRACT") and result.get("successful"):
        found.update(URL_RE.findall(json.dumps(result.get("data", ""))))
    return {_norm(u) for u in found}


def review_submission(app: dict, sub: dict, trace: Trace) -> list[str]:
    problems = []
    for e in sub.get("evidence", []):
        if _norm(e["url"]) not in trace.opened_urls:
            problems.append(f"evidence URL was not opened in this run: {e['url']}")
    row = derive({**app, **sub})
    problems += check(row)
    problems = [p for p in problems if not p.startswith("R10")]  # low confidence is allowed, it routes to a human
    return problems


def research_app(app: dict, llm: LLM, runner: ToolRunner, model: str = "claude-opus-5-5") -> tuple[dict, Trace]:
    trace = Trace()
    tools = runner.tools() + [SUBMIT_TOOL]
    messages: list[dict] = [{"role": "user", "content":
                             f"App #{app['id']}: {app['name']} (category: {app['category']}; hint: {app['hint']}). "
                             "Research it and call submit_research."}]
    for _ in range(MAX_STEPS):
        resp = llm.create(model=model, max_tokens=4000, system=system_prompt(), tools=tools, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        submitted = None
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            if block.name == "submit_research":
                problems = review_submission(app, block.input, trace)
                if problems and trace.repairs < MAX_REPAIRS:
                    trace.repairs += 1
                    results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                                    "content": "Rejected, fix and resubmit:\n- " + "\n- ".join(problems)})
                else:
                    submitted = dict(block.input)
                    if problems:
                        submitted["confidence"] = "low"
                        submitted["notes"] = (submitted.get("notes", "") + " | unresolved: " + "; ".join(problems)).strip(" |")
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": "Saved."})
            else:
                out = runner.execute(block)
                trace.opened_urls |= urls_opened_by(block.name, block.input, out)
                trace.steps.append({"tool": block.name, "input": block.input, "ok": out.get("successful")})
                results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": not out.get("successful"),
                                "content": json.dumps(out.get("data") or out.get("error"))[:20000]})
        if submitted is not None:
            row = derive({**app, **submitted})
            return row, trace
        if not results:  # model answered in text without tools: nudge it
            messages.append({"role": "user", "content": "Use the tools, then call submit_research."})
        else:
            messages.append({"role": "user", "content": results})
    row = derive({**app, "what_it_does": "", "auth": ["Other"], "primary_auth": "Other", "access": "partner",
                  "api_type": "None public", "api_breadth": "narrow", "mcp": "none found", "verdict": "blocked",
                  "blocker": "no public API", "confidence": "low", "evidence": [],
                  "notes": f"agent ran out of steps after {MAX_STEPS}; needs a human"})
    return row, trace


class ComposioRunner:
    """Real tool runner: Composio executes Tavily / Firecrawl for the given user."""

    def __init__(self, user_id: str):
        from composio import Composio
        from composio_anthropic import AnthropicProvider
        self.user_id = user_id
        self.composio = Composio(provider=AnthropicProvider())

    def tools(self) -> list[dict]:
        return list(self.composio.tools.get(self.user_id, tools=COMPOSIO_TOOLS))

    def execute(self, tool_call: Any) -> dict:
        try:
            return self.composio.provider.execute_tool_call(user_id=self.user_id, tool_call=tool_call)
        except Exception as e:  # surface the failure to the model instead of crashing the batch
            return {"successful": False, "error": f"{type(e).__name__}: {e}", "data": None}


class AnthropicLLM:
    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic()

    def create(self, **kw: Any) -> Any:
        return self.client.messages.create(**kw)
