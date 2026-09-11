# P&G Onboarding Tracker

Dedicated TikTok Shop onboarding tracker for Procter & Gamble brands.

- **Asana** (Onboarding 2026 project) supplies the live stage, blockers and days-in-pipeline per brand.
- **Templates** (`templates/*.json`) supply the planned step list per brand type, re-anchored on each brand's Date Signed.
- A Google Sheet (optional) holds per-brand overrides: changed dates, step status, notes.
- **＋ Add brand** (header) searches every task in Onboarding 2026 and pins one to the tracker when
  P&G detection misses it (e.g. Farmacy Beauty: no Parent Company field, not in the brand registry).
  Picked brands show a `manual` pill. On Cloudflare Pages the list is shared through
  `functions/api/manual-brands.js` (same `OVERRIDES` KV namespace, key `manual:brands`); elsewhere it
  lives in the viewer's localStorage.

## Layout

```
index.html              single-file dashboard (no build step)
templates/              generated JSON step lists, one per brand type + index.json
source-templates/       the Excel Gantt templates the JSON is generated from
scripts/convert_templates.py
```

## Regenerating the templates

Edit the Excel files in `source-templates/`, then:

```
pip install openpyxl
python3 scripts/convert_templates.py
```

Dates in the JSON are stored as **day offsets from the template's first Start date**, so a brand
signed on any date gets a full planned timeline automatically.

Each template's checklist is **only** the onboarding pipeline defined by the SOP; it is generated from `source-templates/sop-pipeline.json`, a transcription of the RACI
tables in the Internal Onboarding SOP (Lark, 07/31/2026 update) — one step per bullet, owner =
Sales / Brand / Operations / SCM / TikTok, and every step in a stage shares the stage's window
(upper bound of the SOP estimate). Update that JSON when the SOP changes. The commercial workstreams in the Excel files (Operations,
Inventory, Merchandising, Affiliate, Advertising, Brand Handles) are not part of the SOP and are
excluded (`SOP_ONLY = True` in the converter); each JSON lists them under `removedPerSOP`.

The `DROP` table in the script removes steps that contradict the Internal Onboarding SOP
(07/31/2026): the Inventory category and Shelf-catalog steps for both 1P flows, the CQ/BA
re-approval steps for 1P Existing (qualifications are inherited), and Operations steps that
duplicate the first-category BA/CQ steps. The source Excel files are left exactly as shared;
each template JSON lists what was removed under `removedPerSOP`.

## Asana token

The dashboard never ships with a token. Each viewer pastes their own Asana Personal Access Token
once; it is kept in the browser's localStorage only.

## Hosting on Cloudflare Pages (no token prompt for viewers)

`functions/api/asana/[[path]].js` is a read-only proxy. When the site is served from Cloudflare
Pages with an `ASANA_TOKEN` secret set, the dashboard detects the proxy and skips the token
screen. Viewer access is enforced with Cloudflare Access (pattern.com emails only).

Setup: Workers & Pages → Create → Pages → Connect to Git → this repo. Build command empty,
output directory `/`. Then Settings → Variables and Secrets → add `ASANA_TOKEN` (encrypt) and
redeploy. Then Zero Trust → Access → Applications → add the `*.pages.dev` hostname with an
Allow policy for emails ending in `@pattern.com`.

Served from anywhere else (GitHub Pages, local), it falls back to the paste-once token screen.

## Editing timelines (Cloudflare KV)

Edits made in the app (step dates, status, notes, plan start date, blocker note) are stored per
brand in a KV namespace via `functions/api/overrides/[brand].js`. One-time setup:

1. Cloudflare dashboard → **Storage & databases → KV** → **Create namespace** → name `pg-overrides`.
2. Pages project → **Settings → Bindings → Add → KV namespace**: variable name `OVERRIDES`,
   namespace `pg-overrides`. Save.
3. **Deployments → Retry deployment** so the binding is picked up.

Until the binding exists the app shows the plan read-only with a notice. Every edit records who
made it (from the Cloudflare Access login) and when.
