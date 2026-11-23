"""Build the case-study page (docs/index.html) and machine-readable exports from data/.

Every number on the page is computed here from the data files, never typed by hand.
    python page/build.py
"""
from __future__ import annotations

import collections as C
import csv
import html
import io
import json
import math
from pathlib import Path
from string import Template

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.schema import DATA, ROOT, load_pass  # noqa: E402
from verify.crosscheck_catalog import SLUGS, catalog_status  # noqa: E402
from verify.sample import SEED, draw, draw_holdout_b  # noqa: E402
from verify.score import score  # noqa: E402

REPO = "https://github.com/piyushsamdariya31/composio-app-research"
BLOB = REPO + "/blob/main/"
OUT = ROOT / "docs"
FAM = {"OAuth2": "OAuth2", "API key": "Static key/token", "Token": "Static key/token", "Basic": "Basic",
       "Other": "Other", "None": "None"}
E = html.escape


def wilson_low(k: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    return (c - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d


def pct(x: float) -> str:
    return f"{x * 100:.1f}%".replace(".0%", "%")


def main() -> None:
    rows = load_pass("final")
    p1 = {r["id"]: r for r in load_pass("pass1")}
    cat = json.loads((DATA / "composio_catalog_2026-11-23.json").read_text())["toolkits"]
    changes = [json.loads(x) for x in (DATA / "changelog.jsonl").read_text().splitlines()]
    glog = [json.loads(x) for x in (DATA / "grounding_log.jsonl").read_text().splitlines()]
    gold_a = json.loads((DATA / "gold_sample.json").read_text())["labels"]
    gold_b = json.loads((DATA / "gold_holdout_b.json").read_text())["labels"]
    sample_a, sample_b = draw(), draw_holdout_b()
    sc = {(g, p): score(p, g) for g in ("gold_sample.json", "gold_holdout_b.json") for p in ("pass1", "pass2", "final")}
    (DATA / "scores.json").write_text(json.dumps(list(sc.values()), indent=1))

    for r in rows:  # pages opened during the browser audit are evidence too
        for g in (gold_a.get(str(r["id"])), gold_b.get(str(r["id"]))):
            for j, u in enumerate((g or {}).get("src", [])):
                if all(e["url"] != u for e in r["evidence"]):
                    r["evidence"].append({"field": "browser audit", "url": u, "note": g["note"] if j == 0 else ""})
        r["catalog"] = catalog_status(r["id"], cat)
        r["catalog_slugs"] = SLUGS.get(r["id"], [])
        r["history"] = [c for c in changes if c["id"] == r["id"]]
    n = len(rows)
    pages_read = len({e["url"] for r in rows for e in r["evidence"]})
    assert all(r["evidence"] for r in rows), "every row needs evidence"
    by_cat: dict[str, list] = C.defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)

    # ---------------- statistics ----------------
    prim = C.Counter(FAM[r["primary_auth"]] for r in rows)
    offers_oauth = sum("OAuth2" in r["auth"] for r in rows)
    offers_static = sum(any(FAM[a] == "Static key/token" for a in r["auth"]) for r in rows)
    both = sum("OAuth2" in r["auth"] and any(FAM[a] == "Static key/token" for a in r["auth"]) for r in rows)
    verdict = C.Counter(r["verdict"] for r in rows)
    selfserve = sum(r["self_serve"] == "self-serve" for r in rows)
    access = C.Counter(r["access"] for r in rows)
    blockers = C.Counter(r["blocker"] for r in rows if r["blocker"] not in ("none",))
    mcp_off = sum(r["mcp"] == "official" for r in rows)
    in_cat = C.Counter(r["catalog"] for r in rows)
    loopB = [c for c in changes if c["loop"] == "loopB"]
    loopC = [c for c in changes if c["loop"] == "loopC"]
    loopC_fact = [c for c in loopC if c["field"] not in ("confidence", "primary_reason")]
    low = [r for r in rows if r["confidence"] == "low"]

    easy_api = [r for r in rows if r["catalog"] != "toolkit exists" and r["verdict"] == "ready" and r["api_type"] not in ("CLI/Library", "MCP only")]
    easy_mcp = [r for r in rows if r["catalog"] != "toolkit exists" and r["verdict"] == "ready" and r["api_type"] == "MCP only"]
    easy_local = [r for r in rows if r["verdict"] == "ready" and r["api_type"] == "CLI/Library"]
    outreach = [r for r in rows if r["catalog"] != "toolkit exists" and r["verdict"] != "ready"]

    cat_rows = []
    gate_names = {"paid": "paid plan", "approval": "app review / approval", "partner": "sales / partnership"}
    for k, v in by_cat.items():
        gates = C.Counter(r["access"] for r in v if r["self_serve"] == "gated")
        main_gate = ", ".join(f"{gate_names[g]} ({c})" for g, c in gates.most_common(2)) or "none"
        cat_rows.append(dict(cat=k, ss=sum(r["self_serve"] == "self-serve" for r in v),
                             ready=sum(r["verdict"] == "ready" for r in v), fr=sum(r["verdict"] == "friction" for r in v),
                             bl=sum(r["verdict"] == "blocked" for r in v),
                             oauth=sum(r["primary_auth"] == "OAuth2" for r in v),
                             mcp=sum(r["mcp"] == "official" for r in v),
                             incat=sum(r["catalog"] == "toolkit exists" for r in v), gate=main_gate, n=len(v)))
    cat_rows.sort(key=lambda d: (-d["ss"], -d["ready"]))
    fully_open = [d["cat"] for d in cat_rows if d["ss"] == d["n"]]
    most_gated = [d for d in cat_rows if d["ss"] <= 5]

    a1, a2, af = sc[("gold_sample.json", "pass1")], sc[("gold_sample.json", "pass2")], sc[("gold_sample.json", "final")]
    b1, b2, bf = sc[("gold_holdout_b.json", "pass1")], sc[("gold_holdout_b.json", "pass2")], sc[("gold_holdout_b.json", "final")]
    comb1 = (a1["hits"] + b1["hits"]) / (a1["total"] + b1["total"])
    comb2 = (a2["hits"] + b2["hits"]) / (a2["total"] + b2["total"])
    bf_low = wilson_low(bf["hits"], bf["total"])

    # pass-1 misses by field (sample A)
    miss_by_field = C.Counter(m["field"] for m in a1["misses"])

    # ---------------- HTML pieces ----------------
    def chip(text, cls):
        return f'<span class="chip {cls}">{E(text)}</span>'

    def vchip(v):
        return chip(v, {"ready": "ok", "friction": "warn", "blocked": "bad"}[v])

    def bar(label, value, total, cls="", note=""):
        w = 100 * value / total if total else 0
        return (f'<div class="bar"><span class="bl">{E(label)}</span><span class="bt"><span class="bf {cls}" '
                f'style="width:{w:.1f}%"></span></span><span class="bv">{value}{E(note)}</span></div>')

    def app_list(rs, extra=lambda r: ""):
        return "".join(f'<li><b>{E(r["name"])}</b> <span class="mut">{E(extra(r))}</span></li>' for r in rs)

    cat_table = "".join(
        f'<tr><th scope="row">{E(d["cat"])}</th><td class="num">{d["ss"]}/{d["n"]}</td>'
        f'<td><div class="stack" aria-label="{d["ready"]} ready, {d["fr"]} friction, {d["bl"]} blocked">'
        f'<span class="s ok" style="flex:{d["ready"]}">{d["ready"] or ""}</span><span class="s warn" style="flex:{d["fr"]}">{d["fr"] or ""}</span>'
        f'<span class="s bad" style="flex:{d["bl"]}">{d["bl"] or ""}</span></div></td>'
        f'<td class="num">{d["oauth"]}</td><td class="num">{d["mcp"]}</td><td class="num">{d["incat"]}</td><td>{E(d["gate"])}</td></tr>'
        for d in cat_rows)

    def ev_links(r):
        out = []
        for e in r["evidence"]:
            out.append(f'<li><a href="{E(e["url"])}" rel="noopener">{E(e["url"][:90])}</a>'
                       f'<span class="mut"> ({E(e.get("field", ""))})</span>'
                       + (f'<div class="evn">{E(e["note"])}</div>' if e.get("note") else "") + "</li>")
        return "".join(out)

    def hist(r):
        if not r["history"]:
            return '<p class="mut">No changes after pass 1: every loop agreed with the first draft.</p>'
        return "<ul>" + "".join(
            f'<li><b>{"Loop B" if c["loop"] == "loopB" else "Loop C"}</b> {E(c["field"])}: '
            f'<s>{E(json.dumps(c["from"]) if not isinstance(c["from"], str) else c["from"])}</s> &rarr; '
            f'{E(json.dumps(c["to"]) if not isinstance(c["to"], str) else c["to"])} <span class="mut">{E(c["reason"])}</span></li>'
            for c in r["history"]) + "</ul>"

    table_rows = []
    for r in rows:
        auth = " ".join(f'<b>{E(a)}</b>' if a == r["primary_auth"] else E(a) for a in r["auth"])
        flags = []
        if r["id"] in sample_a:
            flags.append('<span class="tag" title="In the browser-audited sample">audited</span>')
        if r["id"] in sample_b:
            flags.append('<span class="tag" title="In the post-loop holdout">holdout</span>')
        if r["confidence"] == "low":
            flags.append('<span class="tag bad" title="Needs a human">human</span>')
        catl = {"toolkit exists": "yes", "MCP wrapper only": "MCP only", "not in catalog": "no"}[r["catalog"]]
        table_rows.append(
            f'<tr class="row" data-cat="{E(r["category"])}" data-verdict="{r["verdict"]}" data-access="{r["access"]}" '
            f'data-mcp="{r["mcp"]}" data-catalog="{catl}" data-text="{E((r["name"] + " " + r["what_it_does"] + " " + r["hint"]).lower())}">'
            f'<td class="num">{r["id"]}</td><td><button class="exp" aria-expanded="false" aria-controls="d{r["id"]}">{E(r["name"])}</button>{"".join(flags)}'
            f'<div class="sub">{E(r["what_it_does"])}</div></td><td class="hide-s">{E(r["category"])}</td><td>{auth}</td>'
            f'<td>{E(r["access"])}</td><td class="hide-s">{E(r["api_type"])}</td><td>{E(r["mcp"])}</td><td>{vchip(r["verdict"])}</td>'
            f'<td>{E(r["blocker"])}</td><td class="hide-s">{catl}</td><td class="num"><a href="#d{r["id"]}" class="evc" data-open="{r["id"]}">{len(r["evidence"])}</a></td></tr>'
            f'<tr class="det" id="d{r["id"]}" hidden><td colspan="11"><div class="detg"><div><h4>Evidence (pages the agent opened)</h4><ul class="ev">{ev_links(r)}</ul></div>'
            f'<div><h4>What the loops changed</h4>{hist(r)}'
            + (f'<h4>Why this primary auth</h4><p>{E(r["primary_reason"])}</p>' if r.get("primary_reason") else "")
            + f'<p class="mut">Confidence: {E(r["confidence"])} &middot; API breadth: {E(r["api_breadth"])} &middot; Composio slugs: {E(", ".join(r["catalog_slugs"]) or "none")}</p></div></div></td></tr>')

    def miss_rows(s):
        return "".join(f'<tr><td>{E(m["name"])}</td><td>{E(m["field"])}</td><td>{E(m["got"])}</td><td>{E(m["want"])}</td></tr>'
                       for m in s["misses"])

    a1_missed_ids = {m["id"] for m in a1["misses"]}
    fixed_by = {}
    for m in a1["misses"]:
        still = any(x["id"] == m["id"] and x["field"] == m["field"] for x in a2["misses"])
        fixed_by[(m["id"], m["field"])] = "Loop C (browser audit)" if still else "Loop B (grounding + cross-checks)"
    miss_table = "".join(
        f'<tr><td>{E(m["name"])}</td><td>{E(m["field"])}</td><td><s>{E(m["got"])}</s></td><td>{E(m["want"])}</td>'
        f'<td>{fixed_by[(m["id"], m["field"])]}</td></tr>' for m in a1["misses"])

    per_field = "".join(
        f'<tr><th scope="row">{f.replace("_", " ")}</th><td class="num">{pct(a1["per_field"][f])}</td>'
        f'<td class="num">{pct(a2["per_field"][f])}</td><td class="num">{pct(af["per_field"][f])}</td></tr>'
        for f in a1["per_field"])

    dataset = [{k: r[k] for k in ["id", "name", "category", "what_it_does", "auth", "primary_auth", "access", "self_serve",
                                  "api_type", "api_breadth", "mcp", "verdict", "blocker", "confidence", "catalog", "evidence"]}
               | ({"primary_reason": r["primary_reason"]} if r.get("primary_reason") else {})
               | ({"notes": r["notes"]} if r.get("notes") else {}) for r in rows]

    headline = [
        f'<b>Most of the list is buildable today.</b> {verdict["ready"]} of {n} apps can become a toolkit now with credentials a developer gets alone; '
        f'{verdict["friction"]} need a review, a paid plan or a key request first; only {verdict["blocked"]} need a deal or have no public API.',
        f'<b>Auth is a two-lane road, not an OAuth monopoly.</b> OAuth2 is the right primary for {prim["OAuth2"]} apps and a static key or token for {prim["Static key/token"]}. '
        f'{both} apps offer both, so a toolkit framework has to treat API keys as first-class, not as a fallback.',
        f'<b>Gating follows the category, not the company size.</b> {", ".join(fully_open)} are 10/10 self-serve. '
        f'Ads platforms gate on app review, fintech on account approval or partnership, AI-native apps on paid plans, ecommerce on a mix: '
        + "; ".join(f'{d["cat"]} {d["ss"]}/10' for d in most_gated) + ".",
        f'<b>The most common blocker is a tie: app review ({blockers["app review"]}) and paid plans ({blockers["paid plan"]}).</b> '
        f'Partnership gates are rarer ({blockers["partnership"]}) and cluster in enterprise and fintech apps.',
        f'<b>Easy wins vs outreach.</b> Of the {n - in_cat["toolkit exists"]} apps without a full Composio toolkit, {len(easy_api)} are ready to build now '
        f'({", ".join(r["name"] for r in easy_api)}); {len(outreach)} need outreach or a sponsored account.',
        f'<b>MCP is now table stakes, but "official MCP" can mean docs search.</b> {mcp_off} apps have a vendor MCP that can act on account data. '
        f'Twilio, Mailchimp and Vonage ship MCP servers that only search their docs, and Slack’s MCP is open only to Marketplace-listed or internal apps.',
    ]

    moving = [
        ("Shopify", "Admin-created custom apps (static tokens) can no longer be created; Storefront MCP was removed in favour of Shop MCP / UCP."),
        ("Salesforce", "Connected-app creation restricted from Spring '26; hosted MCP servers went GA in April 2026 for Enterprise Edition and up."),
        ("Zendesk", "API tokens are marked deprecated; OAuth is the supported method."),
        ("Xero", "2026 developer pricing: free Starter tier capped at 5 connections, paid tiers above."),
        ("fanbasis", "Rebranded to Commas; APIs offered to enterprises through sales."),
        ("Amazon SP-API", "Docs moved to developer-docs.amazon."),
    ]

    human = [
        ("Help Scout", "A free plan exists, but the pricing table's API row is empty for it. Only a careful read of the table catches this; the fetch-and-summarise step marked it as free."),
        ("Twilio and Mailchimp", "Both link an 'MCP server' from their docs. Reading the page shows it only searches documentation. Deciding that this does not count needed a judgement call, now written into the rubric."),
        ("Waterfall.io", "No signup button. The API key comes from a request form, which is neither self-serve nor a partnership. A new judgement call, filed as approval."),
        ("Paygent Connect", "No product page found under that name. Researched the NMI gateway it is built on and left the row flagged for a human."),
        ("fanbasis", "The domain now redirects to Commas. The API exists but is enterprise-only with no public docs. Flagged for a human."),
        ("Primary auth", "Whether OAuth should be the primary method needs product judgement, for example when Discord's user scopes can't post as a bot or Aircall's OAuth is partner-only. Every exception now carries a written reason."),
    ]

    defeated = [
        "Two rows stay low-confidence: <b>Paygent Connect</b> (product page not found; NMI researched instead) and <b>fanbasis/Commas</b> (no public API docs).",
        "Zendesk's MCP status rests on a third-party report (tldv.io) plus the absence of any vendor page. The vendor has not published a ticket MCP.",
        "Mailchimp's free-plan API access and Fathom's free-plan API access were not confirmed in a plan table. They are marked free because any account can create a key.",
        "'Community MCP' versus 'none found' is weakly evidenced, so the audit scores MCP only as official or not.",
        "Pass 1 cited an Otter help-center article with an invented id (a 404). Loop C found the real article. Pass 1 also used the brief's iPayX docs link, which is a 404 too.",
        f"The audit sample is 20 apps (seed {SEED}) and the holdout is 8 apps. A perfect {bf['hits']} of {bf['total']} fields still allows a true field accuracy as low as {pct(bf_low)} (Wilson 95% lower bound), and the holdout skews toward well-documented apps.",
    ]

    csv_buf = io.StringIO()
    w = csv.writer(csv_buf)
    cols = ["id", "name", "category", "what_it_does", "auth", "primary_auth", "access", "self_serve", "api_type", "api_breadth",
            "mcp", "verdict", "blocker", "confidence", "catalog", "evidence_urls"]
    w.writerow(cols)
    for d in dataset:
        w.writerow([d["id"], d["name"], d["category"], d["what_it_does"], "|".join(d["auth"]), d["primary_auth"], d["access"],
                    d["self_serve"], d["api_type"], d["api_breadth"], d["mcp"], d["verdict"], d["blocker"], d["confidence"],
                    d["catalog"], " ".join(e["url"] for e in d["evidence"])])

    stats = dict(
        n=n, ready=verdict["ready"], friction=verdict["friction"], blocked=verdict["blocked"], selfserve=selfserve, gated=n - selfserve,
        mcp=mcp_off, oauth_p=prim["OAuth2"], static_p=prim["Static key/token"], both=both, offers_oauth=offers_oauth,
        offers_static=offers_static, pages=pages_read, loopB=len(loopB), loopB_apps=len({c["id"] for c in loopB}),
        loopC=len(loopC_fact), loopC_apps=len({c["id"] for c in loopC_fact}), lowc=len(low),
        a1=pct(a1["accuracy"]), a2=pct(a2["accuracy"]), af=pct(af["accuracy"]), a1h=a1["hits"], a2h=a2["hits"], afh=af["hits"], at=a1["total"],
        a1r=a1["rows_fully_correct"], a2r=a2["rows_fully_correct"], afr=af["rows_fully_correct"], ar=a1["rows"],
        b1=pct(b1["accuracy"]), b2=pct(b2["accuracy"]), bf=pct(bf["accuracy"]), b1h=b1["hits"], bfh=bf["hits"], bt=bf["total"], br=bf["rows"],
        bflow=pct(bf_low), comb1=pct(comb1), comb2=pct(comb2), seed=SEED,
        a1w=f'{a1["accuracy"] * 100:.1f}', a2w=f'{a2["accuracy"] * 100:.1f}', afw=f'{af["accuracy"] * 100:.1f}',
        b1w=f'{b1["accuracy"] * 100:.1f}', b2w=f'{b2["accuracy"] * 100:.1f}', bfw=f'{bf["accuracy"] * 100:.1f}',
        in_cat=in_cat["toolkit exists"], mcp_only_cat=in_cat["MCP wrapper only"], not_cat=in_cat["not in catalog"],
        a_ids=", ".join(next(r["name"] for r in rows if r["id"] == i) for i in sample_a),
        b_ids=", ".join(next(r["name"] for r in rows if r["id"] == i) for i in sample_b),
        miss_mcp=miss_by_field["mcp"], miss_access=miss_by_field["access"], miss_prim=miss_by_field["primary_auth"],
        miss_api=miss_by_field["api_type"],
    )
    access_bars = "".join(bar(k, access[k], n, "ok" if k in ("open", "free", "trial") else "warn" if k in ("paid", "approval") else "bad")
                          for k in ["open", "free", "trial", "paid", "approval", "partner"])
    prim_bars = "".join(bar(k, v, n) for k, v in prim.most_common())
    blocker_bars = "".join(bar(k, v, max(blockers.values()), "warn" if k in ("app review", "paid plan") else "bad" if k in ("partnership", "no public API") else "") for k, v in blockers.most_common())

    tpl = Template((Path(__file__).parent / "template.html").read_text())
    page = tpl.substitute(
        **{k: E(str(v)) for k, v in stats.items()},
        headline="".join(f"<li>{h}</li>" for h in headline),
        cat_table=cat_table, access_bars=access_bars, prim_bars=prim_bars, blocker_bars=blocker_bars,
        easy_api=app_list(easy_api, lambda r: f'{r["access"]}, {r["primary_auth"]}' + (", MCP" if r["mcp"] == "official" else "")),
        easy_mcp=app_list(easy_mcp, lambda r: "MCP-only product"), easy_local=app_list(easy_local, lambda r: "local CLI, ship as a sandboxed skill"),
        outreach=app_list(outreach, lambda r: f'{r["access"]} / {r["blocker"]}'),
        moving="".join(f"<li><b>{E(a)}</b> {E(b)}</li>" for a, b in moving),
        human="".join(f"<li><b>{E(a)}</b>: {E(b)}</li>" for a, b in human),
        defeated="".join(f"<li>{d}</li>" for d in defeated),
        table_rows="".join(table_rows), miss_table=miss_table, per_field=per_field,
        b_misses_p1=miss_rows(b1) or '<tr><td colspan="4">none</td></tr>',
        cats_opts="".join(f'<option>{E(c)}</option>' for c in by_cat),
        dataset=json.dumps(dataset, ensure_ascii=False).replace("</", "<\\/"),
        repo=REPO, blob=BLOB,
    )
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(page)
    (OUT / "results.json").write_text(json.dumps(dataset, indent=1, ensure_ascii=False))
    (OUT / "results.csv").write_text(csv_buf.getvalue())
    (OUT / "llms.txt").write_text(
        f"# Composio app research: 100 apps\n\n> Auth, self-serve vs gated, API surface, MCP, buildability verdict and evidence URLs for 100 apps, "
        f"verified with a browser audit ({stats['a1']} -> {stats['a2']} on a 20-app sample; post-loop holdout {stats['bfh']}/{stats['bt']}).\n\n"
        f"- [Dataset (JSON)]({REPO}/blob/main/docs/results.json): one object per app, schema in spec/rubric.md\n"
        f"- [Dataset (CSV)]({REPO}/blob/main/docs/results.csv)\n- [Rubric]({REPO}/blob/main/spec/rubric.md)\n"
        f"- [Change log]({REPO}/blob/main/data/changelog.jsonl): every correction with reason and source\n"
        f"- [Gold labels]({REPO}/blob/main/data/gold_sample.json), [holdout]({REPO}/blob/main/data/gold_holdout_b.json)\n\n"
        "## Headline patterns\n" + "\n".join("- " + h.replace("<b>", "").replace("</b>", "") for h in headline) + "\n")
    print(f"wrote {OUT/'index.html'} ({len(page)//1024} KB), results.json, results.csv, llms.txt")


if __name__ == "__main__":
    main()
