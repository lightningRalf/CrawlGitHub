#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

from __future__ import annotations

"""Remove blank lines inside Markdown tables under the ## Overview section."""

import argparse
from pathlib import Path


def _fix_content(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    in_overview = False
    in_table = False

    for line in lines:
        if line.startswith("## Overview"):
            in_overview = True
            in_table = False
            output.append(line)
            continue

        if in_overview:
            if line.startswith("|"):
                in_table = True
                output.append(line)
                continue
            if in_table and not line.strip():
                # Drop empty lines inside the table block.
                continue
            if in_table and line.strip() and not line.startswith("|"):
                # End of table block.
                in_table = False
                in_overview = False
                output.append(line)
                continue

        output.append(line)

    return "\n".join(output) + ("\n" if text.endswith("\n") else "")


def _process_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = _fix_content(original)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove blank lines between table rows after ## Overview."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(
            r"C:\Users\mjpa\Documents\Obsidian\20-29_Input\23_Schriftliches\23.03_Code"
        ),
        help="Root directory containing 23.03.*.md files.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Process a single file instead of scanning the root.",
    )
    args = parser.parse_args()

    if args.file:
        _process_file(args.file)
        return 0

    for path in args.root.glob("23.03.*.md"):
        _process_file(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
