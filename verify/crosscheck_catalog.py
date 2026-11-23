"""Loop A2: cross-check against an independent second source, Composio's own toolkit catalog.

data/composio_catalog_2026-11-23.json was scraped from docs.composio.dev/toolkits in a
real browser. For every app that already has a Composio toolkit, the auth schemes Composio
ships with are a second opinion on our `auth` field, and a `<slug>_mcp` toolkit using
DCR OAuth is strong evidence that the vendor runs a remote MCP server.

Disagreements are flags, not verdicts: Composio ships only the schemes it needs, so a
flag sends the row to evidence grounding (Loop B), it never edits the row by itself.

    python -m verify.crosscheck_catalog pass1
"""
from __future__ import annotations

import json
import sys

from agent.schema import DATA, load_pass

# app id -> Composio toolkit slugs (main toolkit first). Missing id = not in catalog.
SLUGS: dict[int, list[str]] = {
    1: ["salesforce"], 2: ["hubspot"], 3: ["pipedrive"], 4: ["attio"], 5: ["twenty"], 6: ["podio"], 7: ["zoho"],
    8: ["close", "close_mcp"], 9: ["copper"], 11: ["zendesk"], 12: ["intercom", "intercom_mcp"], 13: ["freshdesk"],
    14: ["front"], 15: ["pylon_mcp"], 17: ["plain", "plain_mcp"], 18: ["help_scout"], 19: ["gorgias"],
    21: ["slack"], 22: ["twilio"], 23: ["zoho_cliq"], 24: ["lark"], 25: ["pumble"], 26: ["discord", "discordbot"],
    27: ["telegram"], 28: ["whatsapp"], 29: ["aircall"], 31: ["googleads"], 32: ["metaads"], 33: ["linkedin_ads"],
    34: ["highlevel_location", "highlevel_agency", "highlevel_mcp"], 35: ["mailchimp"], 36: ["klaviyo"],
    38: ["pinterest"], 39: ["threads"], 40: ["sendgrid"], 41: ["shopify"], 43: ["bigcommerce"], 48: ["gumroad"],
    49: ["amazon"], 51: ["dataforseo"], 53: ["ahrefs", "ahrefs_mcp"], 54: ["mrscraper"], 55: ["apify", "apify_mcp"],
    56: ["firecrawl"], 57: ["brightdata"], 60: ["clay", "clay_mcp"], 61: ["github", "github_mcp"],
    62: ["vercel", "vercel_mcp"], 63: ["netlify_mcp"], 64: ["cloudflare"], 65: ["supabase", "supabase_mcp"],
    66: ["neo4j"], 67: ["snowflake"], 68: ["mongodb", "mongodb_mcp"], 69: ["datadog", "datadog_mcp"],
    70: ["sentry", "sentry_mcp"], 71: ["notion", "notion_mcp"], 72: ["airtable"], 73: ["linear", "linear_mcp"],
    74: ["jira"], 75: ["asana"], 76: ["monday", "monday_mcp"], 77: ["clickup", "clickup_mcp"], 78: ["coda"],
    79: ["smartsheet"], 80: ["harvest"], 81: ["stripe", "stripe_mcp"], 82: ["plaid", "plaid_mcp"], 86: ["quickbooks"],
    87: ["xero"], 88: ["brex"], 89: ["ramp", "ramp_mcp"], 90: ["pitchbook"], 91: ["notebook_lm"],
    92: ["otter_ai_mcp"], 93: ["fathom"], 94: ["consensus", "consensus_mcp"], 96: ["devin_mcp"],
    97: ["higgsfield", "higgsfield_mcp"], 99: ["youtube_transcript"], 100: ["grain"],
}


def schemes(raw: str) -> set[str]:
    head = raw.split("|")[0]
    out = set()
    if "S2S_OAUTH2" in head:
        out.add("S2S")
        head = head.replace("S2S_OAUTH2", "")
    if "DCR_OAUTH" in head:
        out.add("DCR")
        head = head.replace("DCR_OAUTH", "")
    for k, v in [("OAuth2", "OAuth2"), ("API Key", "API key"), ("BASIC", "Basic"), ("Bearer Token", "Token")]:
        if k in head:
            out.add(v)
    return out


def catalog_status(app_id: int, cat: dict) -> str:
    s = SLUGS.get(app_id, [])
    if not s:
        return "not in catalog"
    if all(x.endswith("_mcp") for x in s):
        return "MCP wrapper only"
    return "toolkit exists"


def run(pass_name: str) -> dict:
    cat = json.loads((DATA / "composio_catalog_2026-11-23.json").read_text())["toolkits"]
    flags: dict[int, list[str]] = {}
    status: dict[int, str] = {}
    for r in load_pass(pass_name):
        i = r["id"]
        status[i] = catalog_status(i, cat)
        slugs = SLUGS.get(i, [])
        main = [s for s in slugs if not s.endswith("_mcp")]
        fl = []
        if main:
            sc = schemes(cat.get(main[0], ""))
            ours = set(r["auth"])
            if "OAuth2" in sc and "OAuth2" not in ours:
                fl.append(f"catalog ships OAuth2 for {main[0]}, row lacks it")
            if sc and not ({"OAuth2", "S2S"} & sc) and ours == {"OAuth2"}:
                fl.append(f"catalog ships only {sorted(sc)} for {main[0]}, row says OAuth2 only")
        mcp_dcr = [s for s in slugs if s.endswith("_mcp") and "DCR" in schemes(cat.get(s, ""))]
        if mcp_dcr and r["mcp"] != "official":
            fl.append(f"catalog wraps a remote vendor MCP ({mcp_dcr[0]}), row says mcp={r['mcp']}")
        if fl:
            flags[i] = fl
    return {"flags": flags, "catalog_status": status}


if __name__ == "__main__":
    out = run(sys.argv[1] if len(sys.argv) > 1 else "final")
    print(json.dumps(out["flags"], indent=1))
    print("flagged:", len(out["flags"]))
