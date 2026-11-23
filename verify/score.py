"""Score a pass against the browser-verified gold sample (data/gold_sample.json).

Auth is compared on *family* (OAuth2 / static secret / Basic / Other / None) because
'API key' vs 'Token' is the vendor's wording, not a different integration. The stricter
vendor-wording match is reported too. MCP is scored as official vs not.

    python -m verify.score pass1 pass2 final
"""
from __future__ import annotations

import json
import sys

from agent.schema import DATA, load_pass

FAMILY = {"OAuth2": "OAuth2", "API key": "static secret", "Token": "static secret",
          "Basic": "Basic", "Other": "Other", "None": "None"}
FIELDS = ["auth", "primary_auth", "access", "api_type", "mcp", "verdict"]


def fam(xs):
    return sorted({FAMILY[x] for x in xs})


def compare(row: dict, gold: dict) -> dict[str, tuple[bool, str, str]]:
    out = {
        "auth": (fam(row["auth"]) == fam(gold["auth"]), "/".join(fam(row["auth"])), "/".join(fam(gold["auth"]))),
        "primary_auth": (FAMILY[row["primary_auth"]] == FAMILY[gold["primary_auth"]], row["primary_auth"], gold["primary_auth"]),
        "access": (row["access"] == gold["access"], row["access"], gold["access"]),
        "api_type": (row["api_type"] == gold["api_type"], row["api_type"], gold["api_type"]),
        "mcp": ((row["mcp"] == "official") == gold["mcp_official"], row["mcp"], "official" if gold["mcp_official"] else "not official"),
        "verdict": (row["verdict"] == gold["verdict"], row["verdict"], gold["verdict"]),
    }
    return out


def score(pass_name: str, gold_file: str = "gold_sample.json") -> dict:
    gold = json.loads((DATA / gold_file).read_text())["labels"]
    rows = {r["id"]: r for r in load_pass(pass_name)}
    per_field = {f: [0, 0] for f in FIELDS}
    strict_auth = [0, 0]
    misses = []
    for gid, g in gold.items():
        r = rows[int(gid)]
        for f, (ok, got, want) in compare(r, g).items():
            per_field[f][0] += ok
            per_field[f][1] += 1
            if not ok:
                misses.append({"id": r["id"], "name": r["name"], "field": f, "got": got, "want": want})
        strict_auth[0] += sorted(r["auth"]) == sorted(g["auth"])
        strict_auth[1] += 1
    hits = sum(v[0] for v in per_field.values())
    total = sum(v[1] for v in per_field.values())
    rows_all_correct = len({m for m in gold}) - len({m["id"] for m in misses})
    return {"pass": pass_name, "gold": gold_file, "accuracy": round(hits / total, 4), "hits": hits, "total": total,
            "rows_fully_correct": rows_all_correct, "rows": len(gold),
            "per_field": {f: round(a / b, 4) for f, (a, b) in per_field.items()},
            "auth_vendor_wording_exact": round(strict_auth[0] / strict_auth[1], 4),
            "misses": misses}


if __name__ == "__main__":
    results = [score(p) for p in (sys.argv[1:] or ["pass1", "pass2", "final"])]
    results += [score(p, "gold_holdout_b.json") for p in ("pass1", "pass2", "final")]
    for s in results:
        print(f"[{s['gold']}] {s['pass']}: {s['hits']}/{s['total']} = {s['accuracy']:.1%}  rows fully right {s['rows_fully_correct']}/{s['rows']}  "
              f"per-field {s['per_field']}  auth-wording-exact {s['auth_vendor_wording_exact']:.0%}")
        for m in s["misses"]:
            print(f"   miss #{m['id']} {m['name']}: {m['field']} got={m['got']} want={m['want']}")
    (DATA / "scores.json").write_text(json.dumps(results, indent=1))
