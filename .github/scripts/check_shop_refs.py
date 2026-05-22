#!/usr/bin/env python3
"""
Cross-reference + coverage checks for DynamicShops vs. RogueTech.

Two independent checks run by default:

1. Item-collection references (original check).
   Each shop entry's "items" field is an itemCollection ID. DynamicShops expects
   that ID to exist as a CSV file (e.g. RT_List_Clan_Major.csv) in RogueTech's
   DynamicShops data directories.

   Items that are not in RogueTech's CSV files are checked against two allowlists:
     known_vanilla_collections.txt — vanilla BattleTech game IDs, resolved at runtime
     known_missing_collections.txt — known broken references (bugs to fix later)

2. Faction shop coverage (W7B).
   Walks `<rt_root>/Core/DynamicShops/fshops/*.json` and asserts every faction
   recorded in `faction_shop_baseline.txt` still has at least one entry. Catches
   silent deletion of an entire faction's shop file — the regression class that
   produced bug W7A (Periphery.json wiped in upstream PR #10895). New factions
   appearing in the data are reported as INFO; refresh the baseline with
   `--update-coverage-baseline`.

   A secondary informational check warns if any starsystemdef ownerID has no
   matching (prefix) faction in fshops — fuzzy, since fshop factions are
   era-keyed (e.g. Liao / Liao3031 / Liao3150) while ownerIDs are not.

Exit code 0 = no NEW unknown item refs AND no missing baseline factions.
Non-zero = either check failed.

Usage:
  python check_shop_refs.py <roguetech-root>
  python check_shop_refs.py --update-coverage-baseline <roguetech-root>
"""

import sys
import json
from pathlib import Path

UPDATE_BASELINE_FLAG = "--update-coverage-baseline"
update_baseline = UPDATE_BASELINE_FLAG in sys.argv
args = [a for a in sys.argv[1:] if a != UPDATE_BASELINE_FLAG]

if not args:
    print(f"Usage: check_shop_refs.py [{UPDATE_BASELINE_FLAG}] <roguetech-root>")
    sys.exit(2)

# Resolve to absolute paths up front. A relative rt_root like "../RogueTech"
# (the documented local invocation) otherwise carries a ".." component, and the
# dotfile-skip filters below would treat *every* path as hidden — collecting zero
# valid IDs and reporting all refs as broken. (Lanner 2026-05-21)
rt_root = Path(args[0]).resolve()
scripts_dir = Path(__file__).resolve().parent
ds_root = scripts_dir.parent.parent
baseline_path = scripts_dir / "faction_shop_baseline.txt"

# ── Collect valid itemCollection IDs from RogueTech CSV stems ─────────────────

valid_ids: set[str] = set()
for csv_file in rt_root.rglob("*.csv"):
    # Skip dot-dirs (e.g. .git) — check parts *relative to rt_root* so an
    # absolute prefix or a dotted parent of the repo can't trip the filter.
    if any(part.startswith(".") for part in csv_file.relative_to(rt_root).parts):
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
    rel_parts = f.relative_to(ds_root).parts
    if any(part.startswith(".") for part in rel_parts):
        continue
    if any(part in SKIP_DIRS for part in rel_parts):
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


# ── Faction shop coverage check (W7B) ─────────────────────────────────────────

print()
print("=== Faction shop coverage ===")

rt_fshops_dir = rt_root / "Core" / "DynamicShops" / "fshops"
if not rt_fshops_dir.is_dir():
    print(f"WARN: {rt_fshops_dir} not found — skipping coverage check")
    sys.exit(0)

current_factions: set[str] = set()
for f in sorted(rt_fshops_dir.glob("*.json")):
    try:
        d = json.loads(f.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"WARN: could not parse {f.name}: {exc}")
        continue
    if not isinstance(d, list):
        continue
    for entry in d:
        if not isinstance(entry, dict):
            continue
        v = entry.get("factions")
        if isinstance(v, str):
            current_factions.add(v)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, str):
                    current_factions.add(x)

if update_baseline:
    header = [
        "# faction_shop_baseline.txt",
        "# Baseline of `factions` values present in RogueTech/Core/DynamicShops/fshops/.",
        "# Regenerate after intentional faction add/remove with:",
        f"#   python check_shop_refs.py {UPDATE_BASELINE_FLAG} <roguetech-root>",
        "# Any faction listed here must keep at least one entry in RT fshops/ —",
        "# silent deletion fails CI (W7B; class of bug demonstrated by W7A/Periphery).",
        "",
    ]
    body = sorted(current_factions)
    baseline_path.write_text("\n".join(header + body) + "\n", encoding="utf-8")
    print(f"OK — baseline written: {baseline_path.name} ({len(body)} factions)")
    sys.exit(0)


def load_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")}


baseline_factions = load_baseline(baseline_path)
if not baseline_factions:
    print(f"WARN: baseline {baseline_path.name} missing or empty.")
    print(f"      Run: python check_shop_refs.py {UPDATE_BASELINE_FLAG} <rt_root>")
    sys.exit(1)

missing = sorted(baseline_factions - current_factions)
added = sorted(current_factions - baseline_factions)

if missing:
    print(f"ERROR: {len(missing)} faction(s) in baseline but missing from RT fshops/:")
    for name in missing:
        print(f"  - {name}")
    print(f"\nThis means a faction shop file was deleted or its `factions` value changed.")
    print(f"If intentional: update {baseline_path.name} via "
          f"`{UPDATE_BASELINE_FLAG}` and commit. Otherwise, restore the missing entry.")
    sys.exit(1)

if added:
    print(f"INFO: {len(added)} new faction(s) appear in RT fshops/ not yet in baseline:")
    for name in added:
        print(f"  + {name}")
    print(f"     Refresh baseline with `{UPDATE_BASELINE_FLAG}` if intentional.")

# Secondary informational: starsystem ownership coverage (lenient).
TRIVIAL_OWNERS = {"NoFaction", "Locals", "", None}
owner_ids: set[str] = set()
for ssd in (rt_root / "Core").rglob("starsystemdef_*.json"):
    try:
        d = json.loads(ssd.read_text(encoding="utf-8-sig"))
    except Exception:
        continue
    owner = d.get("ownerID") if isinstance(d, dict) else None
    if owner and owner not in TRIVIAL_OWNERS:
        owner_ids.add(owner)

uncovered = []
for owner in sorted(owner_ids):
    if not any(f == owner or f.startswith(owner) for f in current_factions):
        uncovered.append(owner)

if uncovered:
    print(f"\nWARN: {len(uncovered)} starsystem ownerID(s) have no matching faction shop entry:")
    for o in uncovered:
        print(f"  ? {o}")
    print("     (Lenient prefix match: Liao would match Liao3031. These owners have"
          " no shop coverage for any era variant.)")

present = baseline_factions & current_factions
print(f"\nOK — {len(current_factions)} faction(s) in RT fshops/; "
      f"baseline coverage: {len(present)}/{len(baseline_factions)} baseline entries present.")
