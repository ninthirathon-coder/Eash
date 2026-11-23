#!/usr/bin/env python3
"""Save a Surge Scanner result into scans/surge/ with a timestamped name.

Usage:
    python3 scripts/save_scan.py result.txt [--note "..."] [--name surge]
    some_command | python3 scripts/save_scan.py - --note "..."
"""
import argparse
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", help="result file, or - for stdin")
    p.add_argument("--note", default="", help="short note for the index")
    p.add_argument("--name", default="surge", help="scanner folder under scans/")
    p.add_argument("--time", help="override timestamp, e.g. 2026-11-23T09:30")
    a = p.parse_args()

    text = sys.stdin.read() if a.source == "-" else pathlib.Path(a.source).read_text(encoding="utf-8")
    if not text.strip():
        sys.exit("empty result, nothing saved")

    now = dt.datetime.fromisoformat(a.time) if a.time else dt.datetime.now()
    folder = ROOT / "scans" / a.name
    folder.mkdir(parents=True, exist_ok=True)
    fname = now.strftime("%Y-%m-%d_%H%M") + ".md"
    out = folder / fname
    if out.exists():
        sys.exit(f"{out} already exists")

    header = f"# {a.name} scan – {now:%Y-%m-%d %H:%M}\n\n"
    if a.note:
        header += f"หมายเหตุ: {a.note}\n\n"
    body = text if a.source != "-" and a.source.endswith(".md") else f"```\n{text.rstrip()}\n```\n"
    out.write_text(header + body, encoding="utf-8")
    (folder / "LATEST.md").write_text(header + body, encoding="utf-8")

    index = folder / "INDEX.md"
    if not index.exists():
        index.write_text(f"# {a.name} – รายการผล\n\n| วันเวลา | ไฟล์ | หมายเหตุ |\n|---|---|---|\n", encoding="utf-8")
    lines = index.read_text(encoding="utf-8").splitlines(keepends=True)
    sep = next(i for i, l in enumerate(lines) if l.startswith("|---"))
    note = a.note.replace("|", "\\|")
    lines.insert(sep + 1, f"| {now:%Y-%m-%d %H:%M} | [{fname}]({fname}) | {note} |\n")
    index.write_text("".join(lines), encoding="utf-8")
    print(out.relative_to(ROOT))


if __name__ == "__main__":
    main()
