#!/usr/bin/env python3
"""Validates a list of JSON file paths passed as arguments. Used by the pre-commit hook."""

import json
import sys
from pathlib import Path


def _make_dup_key_hook(dup_collector):
    def hook(pairs):
        seen = set()
        result = {}
        for key, value in pairs:
            if key in seen:
                dup_collector.append(key)
            seen.add(key)
            result[key] = value
        return result
    return hook


def validate(path: Path) -> list[str]:
    errors = []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        return [f"{path}: cannot read: {e}"]

    dup_keys: list[str] = []
    try:
        json.loads(text, object_pairs_hook=_make_dup_key_hook(dup_keys))
    except json.JSONDecodeError as e:
        return [f"{path}: invalid JSON: {e}"]

    if dup_keys:
        errors.append(f"{path}: duplicate JSON keys: {sorted(set(dup_keys))}")
    return errors


def main() -> int:
    files = sys.argv[1:]
    if not files:
        return 0
    errors = []
    for f in files:
        errors.extend(validate(Path(f)))
    if errors:
        print(f"JSON validation FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"  {e}")
        return 1
    print(f"JSON validation OK ({len(files)} file(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
