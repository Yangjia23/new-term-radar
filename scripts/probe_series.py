"""The raw 90-day worldwide Trends series of each phrase, as watch.fresh reads it. Writes probe/report.md.

    python scripts/probe_series.py "zombie couple ai" "reporter voice ai"      # needs AISA_API_KEY
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import aisa, review  # noqa: E402

PHRASES = ["zombie couple ai", "reporter voice ai", "letter k ai", "bulin 47 ai", "ozil goal ai"]


def main() -> int:
    phrases = sys.argv[1:] or PHRASES
    today = date.today()
    window = {"date_from": (today - timedelta(days=90)).isoformat(), "date_to": today.isoformat()}
    data, cost = aisa.call_all([{"call_id": f"s{i}", "tool": review.TOOL, "arguments": {"body": [{"keywords": [p], **window}]}}
                                for i, p in enumerate(phrases)])
    lines = ["# Raw Trends series, 90 days", ""]
    for i, p in enumerate(phrases):
        pts = review._series(((data.get(f"s{i}") or {}).get("tasks") or [{}])[0])
        nonzero = [(d.isoformat()[5:], v) for d, v in pts if v]
        lines += [f"## {p}", f"{len(pts)} days, {len(nonzero)} non-zero: {nonzero}", ""]
    lines.append(f"AIsa cost: ${cost / 1e6:.4f}")
    Path("probe").mkdir(exist_ok=True)
    Path("probe/report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
