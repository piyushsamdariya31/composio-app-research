"""Apply a loop's corrections to the previous pass and write the next pass.

Every change is logged with the field, old value, new value, reason and the URL behind it,
so the page can show exactly what each loop changed and why.

    python -m verify.apply_corrections pass1 data/loopB_corrections.json pass2 loopB
"""
from __future__ import annotations

import copy
import json
import sys

from agent.schema import DATA, derive, load_pass, save_pass


def evidence_from_log(app_id: int) -> list[dict]:
    """Every page the agent actually read for this app (ok=true) becomes evidence."""
    out, seen = [], set()
    for line in (DATA / "grounding_log.jsonl").read_text().splitlines():
        e = json.loads(line)
        if e["id"] == app_id and e.get("ok") and e["url"] not in seen:
            seen.add(e["url"])
            fields = sorted((e.get("supports") or {}).keys()) or ["context"]
            out.append({"field": ",".join(fields), "url": e["url"], "note": e["note"]})
    return out


def apply(prev: str, corrections_path: str, nxt: str, loop: str) -> list[dict]:
    rows = {r["id"]: copy.deepcopy(r) for r in load_pass(prev)}
    corrections = json.loads(open(corrections_path).read())
    changes = []
    for c in corrections:
        r = rows[c["id"]]
        old = r.get(c["field"])
        if old == c["to"]:
            continue
        r[c["field"]] = c["to"]
        changes.append({"loop": loop, "id": c["id"], "name": r["name"], "field": c["field"],
                        "from": old, "to": c["to"], "reason": c["reason"], "src": c["src"]})
        if c["src"] and all(e["url"] != c["src"] for e in r["evidence"]):
            r["evidence"].append({"field": c["field"], "url": c["src"], "note": c["reason"]})
    for r in rows.values():
        # grounded evidence replaces the pass-1 guess when we actually read pages
        read = evidence_from_log(r["id"])
        if read:
            extra = [e for e in r["evidence"] if all(e["url"] != x["url"] for x in read)]
            r["evidence"] = read + [e for e in extra if e.get("note")]
        derive(r)
    save_pass(nxt, [rows[i] for i in sorted(rows)])
    log = DATA / "changelog.jsonl"
    existing = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    existing = [x for x in existing if x["loop"] != loop] + changes
    log.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in existing))
    return changes


if __name__ == "__main__":
    ch = apply(*sys.argv[1:5])
    print(f"{len(ch)} field changes across {len({c['id'] for c in ch})} apps")
