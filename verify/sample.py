"""Draw the audit sample: seeded, stratified 2 apps per category (20 of 100).

The seed is fixed and committed, so anyone can re-draw the same sample.
    python -m verify.sample
"""
import json
import random

from agent.schema import DATA, load_apps

SEED = 20261123
PER_CATEGORY = 2


def draw() -> list[int]:
    rng = random.Random(SEED)
    by_cat: dict[str, list[int]] = {}
    for a in load_apps():
        by_cat.setdefault(a["category"], []).append(a["id"])
    picked = []
    for cat in sorted(by_cat):
        picked += sorted(rng.sample(by_cat[cat], PER_CATEGORY))
    return sorted(picked)


if __name__ == "__main__":
    ids = draw()
    names = {a["id"]: a["name"] for a in load_apps()}
    (DATA / "audit_sample.json").write_text(json.dumps({"seed": SEED, "ids": ids}, indent=1))
    print([(i, names[i]) for i in ids])


def draw_holdout_b(n: int = 8, seed: int = SEED + 1) -> list[int]:
    """Second, post-loop holdout: rows never in sample A and never edited by the audit-driven fixes.
    Measures residual error in rows the loops considered clean."""
    import json as _j
    a = set(draw())
    touched = {c["id"] for c in _j.loads((DATA / "loopC_corrections.json").read_text())}
    pool = [x["id"] for x in load_apps() if x["id"] not in a and x["id"] not in touched]
    return sorted(random.Random(seed).sample(pool, n))
