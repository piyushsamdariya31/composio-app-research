"""Run the research agent over the app list.

    python -m agent.run --only 41            # one app (Shopify)
    python -m agent.run --ids 1-100 --out agent_run
    python -m agent.run --ids 1-100 --model claude-opus-5-5 --user-id me

Needs COMPOSIO_API_KEY and ANTHROPIC_API_KEY, and a Tavily (and/or Firecrawl)
connection for --user-id in your Composio project. Each app's row and tool trace are
written to data/runs/<out>/<id>.json, then merged into data/<out>.json and checked by
verify.validate. Rows the agent could not settle come back with confidence=low: those
are the ones that need a human.
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor

from agent.research import AnthropicLLM, ComposioRunner, research_app
from agent.schema import DATA, load_apps, save_pass


def parse_ids(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="1-100")
    ap.add_argument("--only", type=int)
    ap.add_argument("--out", default="agent_run")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--user-id", default="default")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    ids = [a.only] if a.only else parse_ids(a.ids)
    apps = [x for x in load_apps() if x["id"] in ids]
    run_dir = DATA / "runs" / a.out
    run_dir.mkdir(parents=True, exist_ok=True)
    llm, runner = AnthropicLLM(), ComposioRunner(a.user_id)

    def one(app: dict) -> dict:
        t0 = time.time()
        row, trace = research_app(app, llm, runner, model=a.model)
        (run_dir / f"{app['id']}.json").write_text(json.dumps(
            {"row": row, "opened_urls": sorted(trace.opened_urls), "steps": trace.steps,
             "repairs": trace.repairs, "seconds": round(time.time() - t0, 1)}, indent=1))
        print(f"#{app['id']:>3} {app['name']:<28} {row['verdict']:<9} conf={row['confidence']:<6} "
              f"pages={len(trace.opened_urls)} repairs={trace.repairs}")
        return row

    with ThreadPoolExecutor(a.workers) as pool:
        rows = list(pool.map(one, apps))
    save_pass(a.out, sorted(rows, key=lambda r: r["id"]))
    low = [r["name"] for r in rows if r["confidence"] == "low"]
    print(f"\n{len(rows)} rows -> data/{a.out}.json; needs a human: {low or 'none'}")
    print(f"next: python -m verify.validate {a.out} && python -m verify.score {a.out}")


if __name__ == "__main__":
    main()
