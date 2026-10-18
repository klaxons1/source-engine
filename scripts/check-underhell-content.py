#!/usr/bin/env python3
"""Audit loose Underhell resources on a case-sensitive filesystem (read-only).

Usage: python3 scripts/check-underhell-content.py /path/to/srceng/underhell
Optional --base paths add unpacked hl2/ep2/episodic search roots. VPK contents
cannot be inspected by this checker; missing loose files are reported separately
and are not assumed absent from the game. No files are renamed or lowercased.
"""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
ASSET = re.compile(r'"((?:models|materials|resource|scripts|sound)/[^"\r\n]+)"')


def audit(content, bases=()):
    errors = []
    if content.name != "underhell":
        errors.append("Game directory must be exactly 'underhell', not " + repr(content.name))
    if not content.is_dir():
        return errors + ["Content directory does not exist: " + str(content)], []
    if not (content / "gameinfo.txt").is_file():
        errors.append("Missing exact lowercase underhell/gameinfo.txt")
    indexes = []
    for base in (content, *bases):
        index = {}
        for path in sorted(base.rglob("*")):
            if path.is_file():
                relative = path.relative_to(base).as_posix()
                index.setdefault(relative.casefold(), []).append(relative)
        for names in index.values():
            if len(names) > 1:
                errors.append("Case-colliding paths in " + str(base) + ": " + ", ".join(names))
        indexes.append((base, index))

    references = set()
    for side in ("client", "server", "shared"):
        for path in (ROOT / "game" / side).rglob("*"):
            if path.suffix not in (".cpp", ".h"):
                continue
            # Only imported Underhell files and modified Underhell call sites.
            text = path.read_text(encoding="utf-8", errors="replace")
            if "underhell" not in str(path) and "Underhell" not in text:
                continue
            for match in ASSET.finditer(text):
                asset = match.group(1)
                if "%" not in asset and "*" not in asset and Path(asset).suffix:
                    references.add(asset)
    unresolved = []
    for reference in sorted(references):
        found = False
        for base, index in indexes:
            names = index.get(reference.casefold(), [])
            if names:
                if reference not in names:
                    errors.append("Case mismatch: code requests " + reference +
                                  "; on disk: " + str(base / names[0]))
                found = True
                break
        if not found:
            unresolved.append(reference)
    return errors, unresolved


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("content", type=Path)
    parser.add_argument("--base", action="append", type=Path, default=[])
    args = parser.parse_args()
    errors, unresolved = audit(args.content, args.base)
    for error in errors:
        print("ERROR: " + error, file=sys.stderr)
    for asset in unresolved:
        print("NOT VERIFIED (possibly in VPK/base content): " + asset)
    print("Case audit: {} errors, {} unresolved loose-file references".format(len(errors), len(unresolved)))
    sys.exit(1 if errors else 0)
