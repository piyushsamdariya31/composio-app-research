"""Offline tests: no network, no API keys. Run with `python -m pytest -q`."""
import json
from types import SimpleNamespace as NS

from agent.research import research_app
from agent.schema import load_pass, on_vendor_domain
from verify import score as S
from verify.sample import draw, draw_holdout_b
from verify.validate import check

GOOD = {"id": 81, "name": "Stripe", "category": "Finance and Fintech", "hint": "stripe.com/docs/api",
        "what_it_does": "Online payments infrastructure", "auth": ["API key"], "primary_auth": "API key",
        "access": "free", "api_type": "REST", "api_breadth": "broad", "mcp": "official", "verdict": "ready",
        "blocker": "none", "confidence": "high",
        "evidence": [{"field": "auth", "url": "https://docs.stripe.com/api/authentication"}]}


def test_validator_accepts_good_row():
    assert check(GOOD) == []


def test_validator_catches_contradictions():
    bad = {**GOOD, "access": "partner"}                      # partner but 'ready'
    assert any(f.startswith("R2") for f in check(bad))
    bad = {**GOOD, "evidence": [{"field": "auth", "url": "https://medium.com/some-blog"}]}
    assert any(f.startswith("R9") for f in check(bad))
    bad = {**GOOD, "auth": ["API key", "OAuth2"]}             # OAuth offered, primary not OAuth, no reason
    assert any(f.startswith("R11") for f in check(bad))


def test_vendor_domain_matching():
    assert on_vendor_domain(98, "https://github.com/mermaid-js/mermaid-cli")
    assert not on_vendor_domain(98, "https://github.com/someone-else/mermaid-cli")
    assert on_vendor_domain(49, "https://developer-docs.amazon/sp-api/docs/x")


def test_samples_are_deterministic_and_disjoint():
    a, b = draw(), draw_holdout_b()
    assert len(a) == 20 and len(b) == 8 and not set(a) & set(b)
    assert a == draw()


def test_final_dataset_is_clean():
    rows = load_pass("final")
    assert len(rows) == 100
    flagged = {r["id"]: check(r) for r in rows if check(r)}
    # only the two rows deliberately left for a human may be flagged, and only for low confidence
    assert set(flagged) <= {50, 84} and all(f[0].startswith("R10") for f in flagged.values())


def test_scores_match_published_numbers():
    assert S.score("pass1")["hits"] == 103 and S.score("pass2")["hits"] == 112
    assert S.score("final")["accuracy"] == 1.0
    assert S.score("final", "gold_holdout_b.json")["hits"] == 48


# ---------- agent loop with a fake model and fake Composio tools ----------
class FakeRunner:
    def tools(self):
        return [{"name": "TAVILY_SEARCH", "description": "search", "input_schema": {"type": "object"}}]

    def execute(self, call):
        return {"successful": True, "data": {"results": [{"url": "https://docs.stripe.com/api/authentication",
                                                         "content": "The Stripe API uses API keys"}]}}


def tool_use(name, inp, i):
    return NS(type="tool_use", name=name, input=inp, id=f"t{i}")


class ScriptedLLM:
    def __init__(self, turns):
        self.turns, self.seen = turns, []

    def create(self, **kw):
        self.seen.append(kw["messages"][-1])
        return NS(content=self.turns.pop(0))


SUB = {k: GOOD[k] for k in ["what_it_does", "auth", "primary_auth", "access", "api_type", "api_breadth",
                            "mcp", "verdict", "blocker", "confidence"]}
APP = {k: GOOD[k] for k in ["id", "name", "category", "hint"]}


def test_agent_rejects_unopened_evidence_then_accepts_fix():
    bad = {**SUB, "evidence": [{"field": "auth", "url": "https://stripe.com/made-up", "quote": "x"}]}
    good = {**SUB, "evidence": [{"field": "auth", "url": "https://docs.stripe.com/api/authentication",
                                 "quote": "uses API keys"}]}
    llm = ScriptedLLM([[tool_use("TAVILY_SEARCH", {"query": "stripe auth"}, 1)],
                       [tool_use("submit_research", bad, 2)],
                       [tool_use("submit_research", good, 3)]])
    row, trace = research_app(APP, llm, FakeRunner())
    assert trace.repairs == 1 and row["confidence"] == "high"
    rejected = json.dumps(llm.seen[2], default=str)
    assert "not opened in this run" in rejected


def test_agent_marks_low_confidence_when_it_cannot_fix():
    bad = {**SUB, "evidence": [{"field": "auth", "url": "https://stripe.com/made-up", "quote": "x"}]}
    llm = ScriptedLLM([[tool_use("submit_research", bad, i)] for i in range(3)])
    row, _ = research_app(APP, llm, FakeRunner())
    assert row["confidence"] == "low" and "unresolved" in row["notes"]
