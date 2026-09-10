#!/usr/bin/env python3
"""
Convert the four onboarding Gantt Excel templates into JSON step lists.

Each Excel template has one sheet with a header row:
  Category | Action # | Task | Owner | Start | Due | Days | Status | Notes | <daily gantt columns...>

The daily Gantt columns are derived from Start/Due, so they are NOT kept.
Dates are converted to *offsets in days from the earliest Start* so the
dashboard can re-anchor a template on any brand's Date Signed.

Usage:
    python3 scripts/convert_templates.py          # writes templates/*.json + templates/index.json
Requires: pip install openpyxl
"""
import json
import re
from datetime import datetime
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-templates"
OUT = ROOT / "templates"

# file stem -> metadata. `asanaBrandTypes` are the exact "Brand Type" enum
# values on the Onboarding 2026 project (lower-cased, matched with `includes`).
TEMPLATES = {
    "3p-new-shop": {
        "label": "3P – New Shop Create",
        "asanaBrandTypes": ["3p"],           # plain "3P"
        "externalDoc": "https://docs.google.com/spreadsheets/d/1PIOtAY0U9dq3F3emFTSd7BqDuQgi8P1XUzRQZMSmgQo/edit?usp=sharing",
    },
    "3p-existing-ein-transfer": {
        "label": "3P – Existing Shop (EIN Transfer)",
        "asanaBrandTypes": ["ein transfer", "3p - existing"],
        "externalDoc": "https://docs.google.com/spreadsheets/d/1lOGoQUyYiUDp05cZZmloU5_TWlBW-iNjdaxZwtKGNBs/edit?gid=1345937647#gid=1345937647",
    },
    "1p-new-shop": {
        "label": "1P – New Shop Create",
        "asanaBrandTypes": ["new shop"],
        "externalDoc": "https://docs.google.com/spreadsheets/d/1eydWNyl_A4WcpZI0a5fK5EYr9Fo80S_4u8J76yoZHcE/edit?gid=802827587#gid=802827587",
    },
    "1p-existing-subaccount": {
        "label": "1P – Existing Shop (Subaccount Access)",
        "asanaBrandTypes": ["existing shop", "hybrid"],
        "externalDoc": "https://docs.google.com/spreadsheets/d/1S5im6ljrQ5QXRgGdfeWESrOx0k2phriREoRRIvnzTWA/edit?usp=sharing",
    },
}

HEADER = ["Category", "Action #", "Task", "Owner", "Start", "Due", "Days", "Status", "Notes"]
PIPELINE_CATEGORY = "Onboarding pipeline"
SOP = json.loads((SRC / "sop-pipeline.json").read_text())  # RACI tables from the Internal Onboarding SOP

# Steps/categories removed per the Internal Onboarding SOP (07/31/2026). The source Excel
# files are kept as Catherine shared them; these rules are applied at conversion time.
#   1P flows: Pattern does not buy/hold inventory (the "waiting" stage is a test order via the
#   brand's own fulfillment platform) and does not build the catalog in Shelf. 1P Existing
#   inherits CQ/BA, so the Operations "re-approval" steps contradict the SOP. The Operations
#   BA/CQ steps also duplicate the first-category steps in every template.
DROP = {
    "1p-new-shop": {
        "categories": ["Inventory"],
        "steps": ["operations-2", "operations-3", "operations-4", "operations-5",      # Shelf catalog / Connect (3P)
                  "operations-6", "operations-7", "operations-8",                      # BA/CQ duplicates of Shop Build 12-13
                  "operations-10"],                                                    # Map SKUs to Shelf (3P)
    },
    "1p-existing-subaccount": {
        "categories": ["Inventory"],
        "steps": ["operations-2", "operations-3", "operations-4", "operations-5",      # Shelf catalog / Connect (seller record already in Subaccount Access 10)
                  "operations-6", "operations-7", "operations-8",                      # re-approval: CQ/BA are inherited per SOP
                  "operations-9", "operations-10"],                                    # products already live; Shelf SKU mapping (3P)
    },
    "3p-existing-ein-transfer": {
        "categories": [],
        "steps": ["operations-6", "operations-7", "operations-8"],                     # duplicates of EIN Transfer 13-14
    },
}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def to_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str) and v.strip():
        return datetime.fromisoformat(v.strip()[:10]).date()
    return None


def convert(stem, meta):
    wb = openpyxl.load_workbook(SRC / f"{stem}.xlsx", data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))

    title = str(rows[0][0] or "").strip()
    hdr_i = next(i for i, r in enumerate(rows) if r and r[0] == "Category")
    assert [str(c).strip() for c in rows[hdr_i][:9]] == HEADER, f"{stem}: unexpected header {rows[hdr_i][:9]}"

    steps = []
    for r in rows[hdr_i + 1:]:
        if not r or not r[0] or not r[2]:
            continue  # blank line or category divider row
        start, due = to_date(r[4]), to_date(r[5])
        steps.append({
            "category": str(r[0]).strip(),
            "action": float(r[1]) if r[1] is not None else None,
            "task": str(r[2]).strip(),
            "owner": str(r[3]).strip() if r[3] else None,
            "_start": start,
            "_due": due,
            "days": int(r[6]) if r[6] is not None else ((due - start).days + 1 if start and due else None),
            "status": str(r[7]).strip() if r[7] else "Not Started",
            "notes": str(r[8]).strip() if r[8] else None,
        })

    anchor = min(s["_start"] for s in steps if s["_start"])
    for s in steps:
        s["id"] = f"{slug(s['category'])}-{s['action']:g}" if s["action"] is not None else slug(s["task"])[:40]
    drop = DROP.get(stem, {"categories": [], "steps": []})
    removed = [s for s in steps if s["category"] in drop["categories"] or s["id"] in drop["steps"]]
    missing = set(drop["steps"]) - {s["id"] for s in steps}
    assert not missing, f"{stem}: DROP references unknown steps {missing}"
    steps = [s for s in steps if s not in removed]

    # Replace the Excel's first category (the ops pipeline) with the SOP's stage-by-stage RACI
    # steps. Owners are the SOP's five roles; every step in a stage shares the stage window.
    excel_first = steps[0]["category"]
    replaced_first = [s for s in steps if s["category"] == excel_first]
    steps = [s for s in steps if s["category"] != excel_first]
    sop = SOP[stem]
    pipeline, day, n = [], 0, 0
    for si, st in enumerate(sop["stages"]):
        for owner, task in st["steps"]:
            n += 1
            pipeline.append({
                "category": PIPELINE_CATEGORY, "action": float(n), "task": task, "owner": owner,
                "days": st["days"], "status": "Not Started", "notes": None,
                "id": f"pipeline-{n}", "stage": st["name"], "stageIndex": si + 1,
                "startOffset": day, "dueOffset": day + st["days"] - 1,
            })
        day += st["days"]
    steps = pipeline + steps
    categories = []
    for s in steps:
        if "_start" in s:  # Excel-sourced step; SOP pipeline steps already carry offsets
            s["startOffset"] = (s["_start"] - anchor).days if s["_start"] else None
            s["dueOffset"] = (s["_due"] - anchor).days if s["_due"] else None
            del s["_start"], s["_due"]
        if s["category"] not in categories:
            categories.append(s["category"])

    total_days = max(s["dueOffset"] for s in steps if s["dueOffset"] is not None) + 1
    # The real go-live is the "Live/Active" (or "go-live") step inside the FIRST category;
    # every other category keeps running after it (inventory, affiliate, ...).
    go_live = next((s for s in pipeline if s["task"] == sop["goLive"]), None)
    assert go_live, f"{stem}: go-live step '{sop['goLive']}' not found in SOP pipeline"
    return {
        "goLiveStepId": go_live["id"],
        "goLiveOffset": go_live["dueOffset"],
        "id": stem,
        "label": meta["label"],
        "title": title,
        "asanaBrandTypes": meta["asanaBrandTypes"],
        "externalDoc": meta["externalDoc"],
        "sourceFile": f"source-templates/{stem}.xlsx",
        "sourceAnchorDate": anchor.isoformat(),
        "plannedDurationDays": total_days,
        "categories": categories,
        "stepCount": len(steps),
        "removedPerSOP": [{"id": r["id"], "category": r["category"], "task": r["task"]} for r in removed],
        "replacedExcelCategory": {"name": excel_first, "stepCount": len(replaced_first)},
        "stages": [{"name": st["name"], "days": st["days"]} for st in sop["stages"]],
        "steps": steps,
    }


def main():
    OUT.mkdir(exist_ok=True)
    index = []
    for stem, meta in TEMPLATES.items():
        data = convert(stem, meta)
        (OUT / f"{stem}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        index.append({k: data[k] for k in ("id", "label", "asanaBrandTypes", "plannedDurationDays", "goLiveStepId", "goLiveOffset", "stepCount", "categories")})
        print(f"{stem:28s} {data['stepCount']:3d} steps  {data['plannedDurationDays']:3d} days  {len(data['categories'])} categories")
    (OUT / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
