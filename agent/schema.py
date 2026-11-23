"""Shared schema for the research agent, the verifiers and the site builder.

Every field is a closed set (see spec/rubric.md) so that rows can be scored
right/wrong against vendor docs.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

AUTH = ["OAuth2", "API key", "Token", "Basic", "Other", "None"]
ACCESS = ["open", "free", "trial", "paid", "approval", "partner"]
SELF_SERVE = {"open", "free", "trial"}
API_TYPE = ["REST", "GraphQL", "REST+GraphQL", "RPC/Other", "MCP only", "CLI/Library", "None public"]
BREADTH = ["broad", "moderate", "narrow"]
MCP = ["official", "community", "none found"]
VERDICT = ["ready", "friction", "blocked"]
BLOCKER = ["none", "paid plan", "app review", "partnership", "no public API", "local only"]
CONFIDENCE = ["high", "medium", "low"]

# Fields scored in the audit (spec/rubric.md, "Scoring").
SCORED_FIELDS = ["auth", "primary_auth", "access", "api_type", "mcp", "verdict"]

# Official domains per app: evidence[0] must live on one of these (rule 9).
VENDOR_DOMAINS: dict[int, list[str]] = {
    1: ["salesforce.com"], 2: ["hubspot.com"], 3: ["pipedrive.com", "pipedrive.readme.io"], 4: ["attio.com"],
    5: ["twenty.com", "github.com/twentyhq"], 6: ["podio.com"], 7: ["zoho.com"], 8: ["close.com"],
    9: ["copper.com"], 10: ["dealcloud.com", "intapp.com"], 11: ["zendesk.com"], 12: ["intercom.com"],
    13: ["freshdesk.com", "freshworks.com"], 14: ["frontapp.com", "front.com"], 15: ["usepylon.com"],
    16: ["liveagent.com"], 17: ["plain.com"], 18: ["helpscout.com", "helpscout.net"], 19: ["gorgias.com"],
    20: ["gladly.com"], 21: ["slack.com", "slack.dev"], 22: ["twilio.com"], 23: ["zoho.com"],
    24: ["larksuite.com", "github.com/larksuite"], 25: ["pumble.com", "cake.com"], 26: ["discord.com"], 27: ["telegram.org"],
    28: ["facebook.com", "meta.com"], 29: ["aircall.io"], 30: ["vonage.com"], 31: ["developers.google.com", "google.com"],
    32: ["facebook.com", "meta.com"], 33: ["learn.microsoft.com", "linkedin.com"], 34: ["stoplight.io", "gohighlevel.com", "highlevel.com"],
    35: ["mailchimp.com"], 36: ["klaviyo.com"], 37: ["systeme.io"], 38: ["pinterest.com"],
    39: ["facebook.com", "meta.com", "threads.com"], 40: ["twilio.com", "sendgrid.com"], 41: ["shopify.dev", "shopify.com"],
    42: ["woocommerce.com", "woocommerce.github.io", "developer.woocommerce.com"], 43: ["bigcommerce.com"],
    44: ["salesforce.com"], 45: ["adobe.com"], 46: ["squarespace.com"], 47: ["ecwid.com"], 48: ["gumroad.com"],
    49: ["amazon.com", "developer-docs.amazon"], 50: ["fanbasis.com", "fan.tech"], 51: ["dataforseo.com"], 52: ["seranking.com"],
    53: ["ahrefs.com"], 54: ["mrscraper.com"], 55: ["apify.com"], 56: ["firecrawl.dev"], 57: ["brightdata.com"],
    58: ["github.com/sherlock-project", "sherlockproject.xyz"], 59: ["waterfall.io"], 60: ["clay.com"],
    61: ["github.com"], 62: ["vercel.com"], 63: ["netlify.com"], 64: ["cloudflare.com"], 65: ["supabase.com"],
    66: ["neo4j.com"], 67: ["snowflake.com"], 68: ["mongodb.com"], 69: ["datadoghq.com"], 70: ["sentry.io"],
    71: ["notion.com", "notion.so"], 72: ["airtable.com"], 73: ["linear.app"], 74: ["atlassian.com"],
    75: ["asana.com"], 76: ["monday.com"], 77: ["clickup.com"], 78: ["coda.io"], 79: ["smartsheet.com"],
    80: ["getharvest.com", "harvestapp.com"], 81: ["stripe.com"], 82: ["plaid.com"], 83: ["binance.com", "binance-docs.github.io"],
    84: ["nmi.com", "paygent"], 85: ["ipayx.ai"], 86: ["intuit.com", "github.com/intuit"], 87: ["xero.com"], 88: ["brex.com"],
    89: ["ramp.com"], 90: ["pitchbook.com"], 91: ["cloud.google.com", "google.com"], 92: ["otter.ai"],
    93: ["fathom.video", "fathom.ai"], 94: ["consensus.app"], 95: ["reducto.ai"], 96: ["devin.ai", "cognition.ai"],
    97: ["higgsfield.ai"], 98: ["github.com/mermaid-js", "mermaid.js.org"], 99: ["transcriptapi.com"],
    100: ["grain.com"],
}


def load_apps() -> list[dict]:
    with open(DATA / "apps.csv", newline="") as f:
        return [{**r, "id": int(r["id"])} for r in csv.DictReader(f)]


def derive(row: dict) -> dict:
    """Fill derived fields. Pure function, used by every pass."""
    row["self_serve"] = "self-serve" if row["access"] in SELF_SERVE else "gated"
    return row


def on_vendor_domain(app_id: int, url: str) -> bool:
    p = urlparse(url)
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.lower().lstrip("/")
    for d in VENDOR_DOMAINS.get(app_id, []):
        if "/" in d:  # e.g. github.com/sherlock-project -> host + path prefix
            dhost, dpath = d.split("/", 1)
            if host == dhost and path.startswith(dpath.lower()):
                return True
        elif host == d or host.endswith("." + d):
            return True
    return False


def load_pass(name: str) -> list[dict]:
    return json.loads((DATA / f"{name}.json").read_text())


def save_pass(name: str, rows: list[dict]) -> Path:
    path = DATA / f"{name}.json"
    path.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    return path
