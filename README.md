# Composio app research: 100 apps, can each ship as an agent toolkit today?

**Case study (live page):** https://piyushsamdariya31.github.io/composio-app-research/  (source: `docs/index.html`)

For each of 100 apps: category, what it does, auth methods, self-serve vs gated access, API surface, MCP,
buildability verdict, main blocker, and evidence URLs, plus the patterns across all 100 and an accuracy audit.

| | |
|---|---|
| Ready to build today | **71** · friction 22 · blocked 7 |
| Self-serve vs gated credentials | **72 / 28** |
| Primary auth | OAuth2 50 · static key/token 45 · 45 apps offer both |
| Most common blocker | app review (11) and paid plan (11), tied |
| Accuracy, 20-app audit sample (120 fields) | **85.8% (pass 1) → 93.3% (automated loops)** → audit misses fixed |
| Post-loop holdout (8 fresh apps, 48 fields) | **48/48** |

## Run the research agent

```bash
pip install -r requirements.txt
export COMPOSIO_API_KEY=...  ANTHROPIC_API_KEY=...
# In Composio, connect Tavily and/or Firecrawl for the user id you pass below.
python -m agent.run --only 41 --user-id me          # one app (41 = Shopify)
python -m agent.run --ids 1-100 --out agent_run     # all 100, 4 in parallel
python -m verify.validate agent_run                 # Loop A rules
python -m verify.score agent_run                    # grade against the gold labels
```

Or use the **runnable trigger**: *Actions → "Research one app" → Run workflow* (needs the two keys as repo secrets).
It researches one app, checks the row against the rules, and diffs it against the published row.

### What the agent does (`agent/research.py`)

One tool-using loop per app. The model (Claude, via the Anthropic API) gets Composio tools for search and
page reading (`TAVILY_SEARCH`, `TAVILY_EXTRACT`, `FIRECRAWL_SCRAPE`, executed through the Composio SDK) and one
local tool, `submit_research`, whose JSON schema *is* the rubric. The loop enforces:

1. **Evidence must be a page the agent opened in this run.** Citing an unopened URL gets the submission rejected.
2. **Closed answer sets** (`spec/rubric.md`), so every field can be scored right or wrong.
3. **The consistency rules** from `verify/validate.py`. A violation is sent back for repair (up to 2 times), then the row
   is saved as `confidence=low`, which routes it to a human.

## Verify everything offline (no keys)

```bash
python -m pytest -q                 # 8 tests, incl. the agent loop with a scripted model
python -m verify.validate final     # Loop A: 11 consistency rules
python -m verify.crosscheck_catalog final   # Loop A2: second source (Composio catalog)
python -m verify.score              # every accuracy number on the page
python page/build.py                # rebuild docs/ from data/ (CI fails if it drifts)
```

## How the 100 rows were produced and verified

| Stage | What it does | Output |
|---|---|---|
| Pass 1 | Model-only draft from the hint and model knowledge, frozen as a baseline | `data/pass1_raw.psv`, `data/pass1.json` |
| Loop A | 11 deterministic consistency rules | `verify/validate.py` |
| Loop A2 | Cross-check with two independent sources: Composio's catalog (auth per toolkit) and the official MCP Registry (domain-verified publishers) | `data/composio_catalog_2026-11-23.json`, `data/mcp_registry_2026-11-23.json` |
| Loop B | Open the vendor's auth, pricing and MCP pages for every app; correct contradicted claims | `data/grounding_log.jsonl`, `data/loopB_corrections.json` → `data/pass2.json` |
| Loop C | Real-browser audit of a seeded sample (2 per category) plus every flagged row; misses become rules applied to all rows | `data/gold_sample.json`, `data/loopC_corrections.json` → `data/final.json` |
| Holdout | 8 rows no loop touched, checked after everything was frozen | `data/gold_holdout_b.json` |

Every correction is in `data/changelog.jsonl` with old value, new value, reason and source URL.

**How this run was produced.** For the submitted dataset, Claude acted as the research agent. It used web search,
page fetch and a real browser pane, with this repo's rubric, validators and scorers as its checks.
`agent/research.py` packages the same loop headless on Composio's SDK.

**Where a human was needed:** Help Scout (free plan exists, but no API on it), Twilio and Mailchimp (their "MCP servers"
only search docs), Waterfall.io (API key by request form), Paygent Connect (no product page; researched the NMI gateway it
runs on), fanbasis (rebranded to Commas, enterprise-only API), and primary-auth judgement calls (now rule 11).

## Repo map

```
spec/rubric.md            field definitions, closed sets, rules, scoring
data/apps.csv             the 100 apps
data/pass1.json → pass2.json → final.json   each pass, frozen
data/changelog.jsonl      every change with reason + source
data/gold_*.json          browser-verified labels (audit sample, holdout)
agent/                    research agent (Composio + Claude), schema, CLI
verify/                   validate, cross-check, sample, score, apply corrections
page/                     page template + builder
docs/                     the published page, results.json, results.csv, llms.txt
```

## Known limits

- Two rows stay low-confidence: Paygent Connect and fanbasis/Commas.
- The holdout is small (8 apps). A perfect 48/48 still allows a true field accuracy of about 93% (Wilson 95% lower bound).
- "Community MCP" vs "none found" is weakly evidenced, so MCP is scored only as official or not.
- Facts move: several rows changed during 2025-26 (Shopify tokens, Zendesk tokens, Xero pricing, Salesforce connected apps). Re-run before relying on them.
