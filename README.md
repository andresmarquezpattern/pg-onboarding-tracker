# P&G Onboarding Tracker

Dedicated TikTok Shop onboarding tracker for Procter & Gamble brands.

- **Asana** (Onboarding 2026 project) supplies the live stage, blockers and days-in-pipeline per brand.
- **Templates** (`templates/*.json`) supply the planned step list per brand type, re-anchored on each brand's Date Signed.
- A Google Sheet (optional) holds per-brand overrides: changed dates, step status, notes.

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

## Asana token

The dashboard never ships with a token. Each viewer pastes their own Asana Personal Access Token
once; it is kept in the browser's localStorage only.
