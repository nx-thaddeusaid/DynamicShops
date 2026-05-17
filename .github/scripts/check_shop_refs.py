#!/usr/bin/env python3
"""
Cross-reference check: DynamicShops item collection IDs → RogueTech CSV files.

Each shop entry's "items" field is an itemCollection ID. DynamicShops expects
that ID to exist as a CSV file (e.g. RT_List_Clan_Major.csv) in RogueTech's
DynamicShops data directories.

Items that are not in RogueTech's CSV files are checked against two allowlists:
  known_vanilla_collections.txt — vanilla BattleTech game IDs, resolved at runtime
  known_missing_collections.txt — known broken references (bugs to fix later)

Exit code 0 = no NEW unknown references found.
Non-zero = a reference appeared that is not in RogueTech CSVs or either allowlist.

Usage:
  python check_shop_refs.py <roguetech-root>
"""

import sys
import json
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: check_shop_refs.py <roguetech-root>")
    sys.exit(2)

rt_root = Path(sys.argv[1])
scripts_dir = Path(__file__).parent
ds_root = scripts_dir.parent.parent

# ── Collect valid itemCollection IDs from RogueTech CSV stems ─────────────────

valid_ids: set[str] = set()
for csv_file in rt_root.rglob("*.csv"):
    if any(part.startswith(".") for part in csv_file.parts):
        continue
    valid_ids.add(csv_file.stem)

# ── Load allowlists ────────────────────────────────────────────────────────────

def load_allowlist(name: str) -> set[str]:
    p = scripts_dir / name
    if not p.exists():
        return set()
    return {line.strip() for line in p.read_text().splitlines()
            if line.strip() and not line.startswith("#")}

vanilla_ids = load_allowlist("known_vanilla_collections.txt")
known_missing = load_allowlist("known_missing_collections.txt")

# ── Collect all item references from DynamicShops JSON files ──────────────────

refs: dict[str, list[str]] = {}  # id -> list of source files

SKIP_DIRS = {"bta"}  # wrong-mod directory, not loaded by any mod.json

for f in ds_root.rglob("*.json"):
    if any(part.startswith(".") for part in f.parts):
        continue
    if any(part in SKIP_DIRS for part in f.relative_to(ds_root).parts):
        continue
    if f.name in ("mod.json", "modstate.json"):
        continue
    try:
        d = json.loads(f.read_text(encoding="utf-8-sig"))
    except Exception:
        continue

    if not isinstance(d, list):
        continue

    for entry in d:
        if not isinstance(entry, dict):
            continue
        items = entry.get("items")
        if items is None:
            continue
        item_ids = [items] if isinstance(items, str) else items if isinstance(items, list) else []
        for item_id in item_ids:
            if isinstance(item_id, str):
                refs.setdefault(item_id, []).append(str(f.relative_to(ds_root)))

# ── Classify references ───────────────────────────────────────────────────────

new_unknown: list[tuple[str, list[str]]] = []

for item_id, sources in sorted(refs.items()):
    if item_id in valid_ids:
        continue
    if item_id in vanilla_ids:
        continue
    if item_id in known_missing:
        continue
    new_unknown.append((item_id, sources))

# ── Report known missing (informational) ─────────────────────────────────────

known_found = {k: v for k, v in refs.items()
               if k in known_missing and k not in valid_ids and k not in vanilla_ids}
if known_found:
    print(f"KNOWN ISSUES ({len(known_found)} item IDs not found in RogueTech CSVs):")
    for item_id in sorted(known_found):
        print(f"  {item_id} — referenced in: {', '.join(known_found[item_id][:3])}")
    print()

# ── Fail on truly unknown references ─────────────────────────────────────────

if new_unknown:
    print(f"ERROR: {len(new_unknown)} NEW item collection ID(s) not found in RogueTech or allowlists:")
    for item_id, sources in new_unknown:
        print(f"  {item_id} — {', '.join(sources[:3])}")
    print("\nAdd to known_missing_collections.txt if this is a known issue,")
    print("or to known_vanilla_collections.txt if it is a vanilla game collection.")
    sys.exit(1)

total = len(refs)
resolved = sum(1 for k in refs if k in valid_ids)
print(f"OK — {total} item collection refs checked, {resolved} resolved in RogueTech")
if known_found:
    print(f"     {len(known_found)} known issues (see above) — fix when possible")
