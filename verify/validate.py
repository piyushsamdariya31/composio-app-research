"""Loop A: deterministic consistency checks (spec/rubric.md, rules 1-10).

Cheap, runs on every row of every pass, catches self-contradicting rows
before any money is spent on fetching docs.

    python -m verify.validate pass1
"""
from __future__ import annotations

import json
import sys

from agent.schema import (ACCESS, API_TYPE, AUTH, BLOCKER, BREADTH, CONFIDENCE, MCP, VERDICT,
                          derive, load_pass, on_vendor_domain)

ENUMS = {"access": ACCESS, "api_type": API_TYPE, "api_breadth": BREADTH, "mcp": MCP,
         "verdict": VERDICT, "blocker": BLOCKER, "confidence": CONFIDENCE, "primary_auth": AUTH}


def check(row: dict) -> list[str]:
    r = derive(dict(row))
    f: list[str] = []
    for k, allowed in ENUMS.items():
        if r.get(k) not in allowed:
            f.append(f"enum:{k}={r.get(k)!r}")
    if not r.get("auth") or any(a not in AUTH for a in r["auth"]):
        f.append(f"enum:auth={r.get('auth')!r}")
    if len((r.get("what_it_does") or "").split()) > 14:
        f.append("what_it_does>14 words")
    # rule 1
    if r["verdict"] == "ready" and (r["self_serve"] != "self-serve" or r["blocker"] not in ("none", "local only")):
        f.append("R1: ready but gated or blocked")
    # rule 2
    if r["access"] == "partner" and (r["verdict"] != "blocked" or r["blocker"] not in ("partnership", "no public API")):
        f.append("R2: partner access must be blocked/partnership")
    # rule 3
    if r["access"] == "approval" and (r["verdict"] not in ("friction", "blocked") or r["blocker"] not in ("app review", "partnership")):
        f.append("R3: approval access needs friction|blocked + app review|partnership")
    # rule 4
    if r["access"] == "paid" and r["blocker"] != "paid plan":
        f.append("R4: paid access must name paid plan as blocker")
    # rule 6
    if r["api_type"] == "None public" and (r["verdict"] != "blocked" or r["blocker"] != "no public API"):
        f.append("R6: no public API must be blocked")
    # rule 7
    if r["api_type"] == "CLI/Library" and (r["blocker"] != "local only" or r["auth"] != ["None"]):
        f.append("R7: CLI/Library must be local only with auth None")
    if r["blocker"] == "local only" and r["api_type"] != "CLI/Library":
        f.append("R7b: local only blocker but not a CLI/Library")
    # rule 8
    if r["primary_auth"] not in r["auth"]:
        f.append("R8: primary_auth not in auth list")
    # rule 9
    ev = r.get("evidence") or []
    if not ev:
        f.append("R9: no evidence")
    elif not on_vendor_domain(r["id"], ev[0]["url"]):
        f.append(f"R9: first evidence not on vendor domain ({ev[0]['url']})")
    # rule 11 (added after the audit): OAuth2 offered but primary is not OAuth2 -> needs a stated reason
    if "OAuth2" in r["auth"] and r["primary_auth"] != "OAuth2" and not r.get("primary_reason"):
        f.append("R11: OAuth2 offered but primary_auth is not OAuth2 and no primary_reason given")
    # rule 10
    if r["confidence"] == "low":
        f.append("R10: low confidence, needs a human/browser check")
    return f


def run(pass_name: str) -> dict[int, list[str]]:
    rows = load_pass(pass_name)
    return {r["id"]: fl for r in rows if (fl := check(r))}


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "final"
    flags = run(name)
    print(json.dumps({"pass": name, "rows_flagged": len(flags), "flags": flags}, indent=1))
