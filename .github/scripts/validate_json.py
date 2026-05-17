#!/usr/bin/env python3
"""
Validates all JSON files in the DynamicShops mod.

Checks:
  1. Every .json file is syntactically valid
  2. No duplicate keys within a single JSON object
  3. Shop def files are root-level arrays whose entries each have an 'items' field
  4. Faction shop (fshops/) entries also have a 'factions' field
  5. System shop (sshops/) conditions only use known keys: tag, owner, rep
  6. mod.json has 'Name' when manifest keys are present

Exit code 0 = clean, non-zero = failures found.
"""

import json
import sys
from pathlib import Path

MOD_JSON_MANIFEST_KEYS = {"Name", "Enabled", "Active", "DLL", "Manifest", "DependsOn"}
VALID_CONDITION_KEYS = {"tag", "owner", "rep"}

# Source directory contains C# code, not game data.
SKIP_DIRS = {"source"}


def _make_dup_key_hook(dup_collector: list[str]):
    def hook(pairs: list[tuple[str, object]]) -> dict:
        seen: set[str] = set()
        result: dict = {}
        for key, value in pairs:
            if key in seen:
                dup_collector.append(key)
            seen.add(key)
            result[key] = value
        return result
    return hook


def shop_type(path: Path) -> str | None:
    """Return 'sshop', 'fshop', or 'bmshop' if the file is in a shop directory, else None."""
    parts_lower = [p.lower() for p in path.parts]
    if "fshops" in parts_lower:
        return "fshop"
    if "sshops" in parts_lower:
        return "sshop"
    if "bmshops" in parts_lower:
        return "bmshop"
    return None


def validate_file(path: Path, errors: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        errors.append(f"{path}: cannot read: {e}")
        return

    dup_keys: list[str] = []
    try:
        data = json.loads(text, object_pairs_hook=_make_dup_key_hook(dup_keys))
    except json.JSONDecodeError as e:
        errors.append(f"{path}: invalid JSON: {e}")
        return

    if dup_keys:
        errors.append(f"{path}: duplicate JSON keys: {sorted(set(dup_keys))}")

    name = path.name.lower()

    if name == "mod.json":
        if isinstance(data, dict) and data.keys() & MOD_JSON_MANIFEST_KEYS:
            if "Name" not in data:
                errors.append(f"{path}: mod.json missing required field 'Name'")
        return

    stype = shop_type(path)
    if stype is None:
        return

    if not isinstance(data, list):
        errors.append(f"{path}: expected a root-level array, got {type(data).__name__}")
        return

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            errors.append(f"{path}: entry [{i}] is not an object")
            continue
        if "items" not in entry:
            errors.append(f"{path}: entry [{i}] missing 'items'")
        if stype == "fshop" and "factions" not in entry:
            errors.append(f"{path}: entry [{i}] missing 'factions'")
        if stype == "sshop" and "conditions" in entry:
            cond = entry["conditions"]
            if isinstance(cond, dict):
                unknown = set(cond.keys()) - VALID_CONDITION_KEYS
                if unknown:
                    errors.append(f"{path}: entry [{i}] unknown condition key(s): {sorted(unknown)}")


def main() -> int:
    root = Path(__file__).parent.parent.parent
    errors: list[str] = []
    total = 0

    for json_file in sorted(root.rglob("*.json")):
        parts_lower = [p.lower() for p in json_file.parts]
        if any(part.startswith(".") for part in json_file.parts):
            continue
        if any(skip in parts_lower for skip in SKIP_DIRS):
            continue
        total += 1
        validate_file(json_file, errors)

    if errors:
        print(f"FAILED — {len(errors)} error(s) across {total} files:\n")
        for err in errors:
            print(f"  {err}")
        return 1

    print(f"OK — {total} JSON files passed validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
