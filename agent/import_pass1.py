"""Turn the frozen pass-1 draft (data/pass1_raw.psv) into data/pass1.json."""
from agent.schema import derive, load_apps, save_pass

COLS = ["id", "what_it_does", "auth", "primary_auth", "access", "api_type", "api_breadth",
        "mcp", "verdict", "blocker", "evidence_url", "confidence"]


def main() -> None:
    apps = {a["id"]: a for a in load_apps()}
    rows = []
    for line in open("data/pass1_raw.psv"):
        if not line.strip() or line.startswith("#"):
            continue
        v = dict(zip(COLS, line.rstrip("\n").split("|")))
        a = apps[int(v["id"])]
        row = {"id": a["id"], "name": a["name"], "category": a["category"], "hint": a["hint"],
               "what_it_does": v["what_it_does"], "auth": v["auth"].split(","), "primary_auth": v["primary_auth"],
               "access": v["access"], "api_type": v["api_type"], "api_breadth": v["api_breadth"], "mcp": v["mcp"],
               "verdict": v["verdict"], "blocker": v["blocker"], "confidence": v["confidence"],
               "evidence": [{"field": "auth", "url": v["evidence_url"]}], "notes": ""}
        rows.append(derive(row))
    assert len(rows) == 100 and [r["id"] for r in rows] == list(range(1, 101))
    print("wrote", save_pass("pass1", rows))


if __name__ == "__main__":
    main()
