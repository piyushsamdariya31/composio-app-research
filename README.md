# Composio app research agent

An agent that researches apps for Composio toolkit buildability: auth, self-serve vs gated access,
API surface, MCP, verdict, main blocker, and evidence URLs. It has been run on 100 apps.

**Case study (live):** https://composio-app-research.vercel.app

## Run the research agent

1. Install:
   ```bash
   git clone https://github.com/piyushsamdariya31/composio-app-research
   cd composio-app-research
   pip install -r requirements.txt
   ```
2. Set keys, and in your Composio dashboard connect **Tavily** (or Firecrawl) for a user id:
   ```bash
   export COMPOSIO_API_KEY=...
   export ANTHROPIC_API_KEY=...
   ```
3. Run it:
   ```bash
   python -m agent.run --only 41 --user-id <your-composio-user-id>   # one app (41 = Shopify)
   python -m agent.run --ids 1-100 --out agent_run --user-id <id>    # all 100 apps
   ```
   Each app's row and tool trace go to `data/runs/<out>/<id>.json`, and all rows to `data/<out>.json`.
   Rows the agent could not settle come back with `confidence: low`; those need a human.
4. Check the output:
   ```bash
   python -m verify.validate agent_run   # 11 consistency rules
   python -m verify.score agent_run      # accuracy vs the browser-verified gold labels
   ```

**No local setup?** Use *Actions → "Research one app" → Run workflow* (add `COMPOSIO_API_KEY` and
`ANTHROPIC_API_KEY` as repo secrets first).

## How it works

`agent/research.py` runs one tool-using loop per app. Claude calls Composio tools (`TAVILY_SEARCH`,
`TAVILY_EXTRACT`, `FIRECRAWL_SCRAPE`) and finishes with `submit_research`, whose schema is the rubric in
`spec/rubric.md`. A submission is rejected and sent back if it cites a page the agent never opened, or if it
breaks a consistency rule. After two failed repairs, the row is saved as low-confidence for a human.

## Verify without keys

```bash
python -m pytest -q        # 8 tests, incl. the agent loop with a scripted model
python -m verify.score     # reproduces every accuracy number on the page
python page/build.py       # rebuilds the page (docs/) from data/
```

`data/` holds every pass (`pass1` → `pass2` → `final`), each correction with its source (`changelog.jsonl`),
and the gold labels.
