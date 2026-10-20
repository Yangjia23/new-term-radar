"""One look at the watch list's freshness check on names whose answer is known: Google Trends
over 90 days, read as radar/watch.py reads it. Writes probe/report.md.

    python scripts/probe_fresh.py [name ...]      # needs AISA_API_KEY
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import watch  # noqa: E402

NAMES = ["hotel lobby", "bulin 47", "burning bridges", "zombie couple", "ozil goal", "reporter voice", "letter k"]


def main() -> int:
    names = sys.argv[1:] or NAMES
    curves, cost = watch.fresh(names, date.today())
    lines = ["# Freshness check, known names", "", "| name | read | verdict | started | now | base | peak day |", "|---|---|---|---|---|---|---|"]
    for n in names:
        c = curves.get(n)
        if c is None:
            lines.append(f"| {n} | | lookup failed | | | | |")
            continue
        verdict = "too small, pushed" if c.get("no_data") else "new, pushed" if c.get("new") else "old, not pushed"
        lines.append(f"| {n} | {c.get('asked', '')} | {verdict} | {c.get('started', '')} | {c.get('now', '')} | {c.get('base', '')} | {c.get('peak_day', '')} |")
    lines += ["", f"AIsa cost: ${cost / 1e6:.4f}"]
    Path("probe").mkdir(exist_ok=True)
    Path("probe/report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
