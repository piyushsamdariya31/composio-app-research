# Research rubric (v1, frozen before the first pass)

Every field has a closed set of values, so a row can be scored right/wrong against the docs instead of "sort of right".
The agent prompt, the validators and the audit all use this file.

## Fields

| Field | Values | Rule |
|---|---|---|
| `what_it_does` | one line, ≤ 14 words | What the product is, not marketing copy. |
| `auth` | list of `OAuth2`, `API key`, `Token`, `Basic`, `Other`, `None` | Use the vendor's own word. `Token` = a static secret the vendor calls a token (personal access token, bot token, access token, private-app token). `API key` = the vendor calls it a key. `Other` = JWT/service-account signing, HMAC request signing, signed cookies, wallet signatures. `None` = no credential needed (local or open-source tool). The transport does not count: an API key or token sent as the HTTP Basic username is still `API key`/`Token`; `Basic` means a login/password pair (e.g. DataForSEO login + API password, Twilio Account SID + Auth Token). |
| `primary_auth` | one of the above | What a multi-tenant agent toolkit should use: OAuth2 if third-party apps can use it, otherwise the key/token a user can paste. |
| `access` | `open`, `free`, `trial`, `paid`, `approval`, `partner` | How a developer gets **working credentials for development**. `open` = nothing to sign up for. `free` = free plan/developer account, no human in the loop. `trial` = only via a time-limited free trial. (Free starter credits on a pay-as-you-go account count as `free`, not `trial`, because nothing expires.) `paid` = API needs a paid plan you can buy yourself. `approval` = self-serve signup, but the vendor must approve the app, developer token, business or scope before you can do real work. `partner` = contact sales / partnership / customer contract before any API access. |
| `self_serve` | derived | `open`, `free`, `trial` → **self-serve**. `paid`, `approval`, `partner` → **gated** (this is the split the brief asks for). |
| `api_type` | `REST`, `GraphQL`, `REST+GraphQL`, `RPC/Other`, `MCP only`, `CLI/Library`, `None public` | Documented, public interface. Any HTTP+JSON method API (e.g. Slack Web API) counts as `REST`. `RPC/Other` = form-post gateways, gRPC-only, websocket-only. `MCP only` = the vendor exposes an MCP server but no public REST/GraphQL API. |
| `api_breadth` | `broad`, `moderate`, `narrow` | broad = most product objects are exposed (roughly 10+ resource groups); moderate = 4 to 9; narrow = 1 to 3. |
| `mcp` | `official`, `community`, `none found` | official = hosted or published by the vendor. community = third-party only. |
| `verdict` | `ready`, `friction`, `blocked` | ready = a toolkit can be built and tested today with self-serve credentials. friction = buildable, but a review, paid plan, or business verification sits between you and production. blocked = cannot be built without a deal, or there is no usable public API. |
| `blocker` | `none`, `paid plan`, `app review`, `partnership`, `no public API`, `local only` | Main thing in the way. `local only` = a CLI/library with no hosted API (build it as a sandboxed skill, not an OAuth toolkit). |
| `evidence` | list of `{field, url}` | Every non-derived field needs a URL on the vendor's own docs. Third-party pages are allowed only as a second source. |
| `confidence` | `high`, `medium`, `low` | low means a human must look before the row is used. |

## Consistency rules (checked by `verify/validate.py`)

1. `verdict = ready` requires `self_serve = self-serve`, `blocker = none` or `local only`.
2. `access = partner` requires `verdict = blocked` and `blocker = partnership` (or `no public API` when the partner-only API has no public docs).
3. `access = approval` requires `verdict` in {friction, blocked} and `blocker = app review` or `partnership`.
4. `access = paid` requires `blocker = paid plan`.
5. `api_type = MCP only` is allowed with any verdict (the MCP server is the integration surface).
6. `api_type = None public` requires `verdict = blocked` and `blocker = no public API`.
7. `api_type = CLI/Library` requires `blocker = local only` and `auth = [None]`.
8. `primary_auth` must be one of `auth`.
9. Each of `auth`, `access`, `api_type`, `mcp` has at least one evidence URL, and the first URL is on the vendor's own domain (allow-list per app).
10. `confidence = low` blocks publishing until a human or browser check clears it.
11. *(added after the audit)* If `OAuth2` is offered but `primary_auth` is not `OAuth2`, the row must state why in `primary_reason` (e.g. OAuth is partner-gated).

## Rules added because the audit caught them

- A free plan existing is not evidence that the API is free. Check the plan table's API row (Help Scout, Smartsheet, Freshdesk).
- A vendor MCP that only searches documentation is not an official MCP for the product (Twilio, Mailchimp, Vonage).
- Evidence URLs must be pages the agent actually opened. Pass 1 cited an Otter help-center URL with an invented article id (404).

## Scoring (for the audit)

A field is **correct** if it equals the gold label made by reading the vendor's docs in a real browser.
`auth` is scored on the **auth family** set: OAuth2 / static secret (`API key` or `Token`, which differ only in the vendor's wording) / Basic / Other / None. The stricter vendor-wording match is reported separately. `primary_auth` is scored on family too. `api_breadth` and `what_it_does` are not scored (subjective).
`mcp` is scored as **official vs not** (community-vs-none is weakly evidenced and does not change buildability). A documentation-only MCP (answers questions about the docs, cannot act on the product) does not count as official.
Scored fields: `auth (family set)`, `primary_auth (family)`, `access`, `api_type`, `mcp (official?)`, `verdict`. 6 fields × sample size.
