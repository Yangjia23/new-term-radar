"""When a trend started, for names whose first sites are known: Google Trends over a year, and the
earliest TikTok videos a search finds. Writes probe/report.md, the raw answers under probe/.

    python scripts/probe_timeline.py ["phrase one, phrase two"]    # needs AISA_API_KEY
    PROBE_ARGS="dime dime baby, dime dime baby ai" python scripts/probe_timeline.py

The phrases, when given, are both read in Trends and searched on TikTok.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import aisa, review  # noqa: E402

TRENDS = ["thriller dance ai", "thriller ai", "thriller dance", "zombie dance ai", "toc toc ai", "toc toc dance",
          "crazy frog ai", "flying car ai"]
SEARCHES = ["thriller dance ai", "thriller ai trend", "zombie dance ai", "toc toc ai", "toc toc dance", "crazy frog ai"]
PAGES = 3
VIDEO = "get_tikhub_tiktok_app_v3_fetch_video_search_result"


def _videos(answer: dict) -> list[dict]:
    """(create_time, plays, author, desc) of each video in a search answer, wherever TikHub put the list."""
    data = answer.get("data", answer)
    items = data.get("search_item_list") or data.get("data") or data.get("aweme_list") or []
    out = []
    for it in items:
        a = it.get("aweme_info", it) if isinstance(it, dict) else {}
        if not a.get("create_time"):
            continue
        out.append({"day": datetime.fromtimestamp(a["create_time"], timezone.utc).date().isoformat(),
                    "plays": (a.get("statistics") or {}).get("play_count"),
                    "author": (a.get("author") or {}).get("unique_id"), "desc": (a.get("desc") or "")[:90],
                    "id": a.get("aweme_id")})
    return out


def main() -> int:
    global TRENDS, SEARCHES
    given = [p.strip() for p in (" ".join(sys.argv[1:]) or os.environ.get("PROBE_ARGS", "")).split(",") if p.strip()]
    if given:
        TRENDS = SEARCHES = given
    today = date.today()
    out = Path("probe")
    out.mkdir(exist_ok=True)
    window = {"date_from": (today - timedelta(days=365)).isoformat(), "date_to": today.isoformat()}
    calls = [{"call_id": f"t{i}", "tool": review.TOOL, "arguments": {"body": [{"keywords": [p], **window}]}}
             for i, p in enumerate(TRENDS)]
    # sort_type 0 relevance; publish_time 0 any time
    calls += [{"call_id": f"v{i}_{page}", "tool": VIDEO,
               "arguments": {"keyword": k, "offset": page * 20, "count": 20, "sort_type": 0, "publish_time": 0}}
              for i, k in enumerate(SEARCHES) for page in range(PAGES)]
    # the same, of the last week only: the earliest of a young trend, which relevance may rank low
    calls += [{"call_id": f"w{i}_{page}", "tool": VIDEO,
               "arguments": {"keyword": k, "offset": page * 20, "count": 20, "sort_type": 0, "publish_time": 7}}
              for i, k in enumerate(SEARCHES) for page in range(PAGES)]
    data, cost = aisa.call_all(calls)
    (out / "raw.json").write_text(json.dumps(data, ensure_ascii=False)[:5_000_000])
    lines = ["# Trend timelines", "", "## Google Trends, worldwide, 365 days (weekly; first week over 10, peak)", ""]
    for i, p in enumerate(TRENDS):
        pts = review._series(((data.get(f"t{i}") or {}).get("tasks") or [{}])[0])
        if not pts:
            lines.append(f"- **{p}**: no answer")
            continue
        peak = max(pts, key=lambda x: x[1])
        first = next((d for d, v in pts if v >= 10), None)
        recent = [(d.isoformat()[5:], v) for d, v in pts if d >= today - timedelta(days=60) and v]
        lines.append(f"- **{p}**: first ≥10 {first}, peak {peak[1]} on {peak[0]}; last 60 days {recent}")
    lines += ["", "## TikTok video search, earliest first", ""]
    for i, k in enumerate(SEARCHES):
        vids, err = [], []
        for page in range(PAGES):
            for pre in ("v", "w"):
                a = data.get(f"{pre}{i}_{page}")
                if a is None:
                    err.append(f"{pre} page {page}: no answer")
                    continue
                vids += _videos(a)
        vids = sorted({v["id"]: v for v in vids}.values(), key=lambda v: v["day"])
        lines.append(f"### {k} ({len(vids)} videos{'; ' + '; '.join(err) if err else ''})")
        lines += [f"- {v['day']} · {v['plays']} plays · @{v['author']} · {v['desc']}" for v in vids[:15]]
        lines.append("")
    lines.append(f"AIsa cost: ${cost / 1e6:.4f}")
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
