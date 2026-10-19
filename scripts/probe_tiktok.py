"""One look at TikTok's other charts, before any becomes a signal: Creator Search Insights
(by tab), the daily trending search words, and the music charts (Top 50, Viral 50).

Each call goes through AIsa's tool router; the raw answer of each is saved under probe/,
failed ones with the router's message. The names found in the answers (titles, keywords,
hashtags, songs) are judged like any lead, and probe/report.md lists them per chart.

    python scripts/probe_tiktok.py      # needs AISA_API_KEY; DEEPSEEK_API_KEY for a deepseek judge
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import aisa, config, judge  # noqa: E402

OUT = Path("probe")
SI = "get_tikhub_tiktok_app_v3_fetch_creator_search_insights"
CALLS = [
    *[{"call_id": f"insights_{tab}", "tool": SI, "arguments": {"offset": 0, "limit": 50, "tab": tab, "language_filters": "en"}}
      for tab in ("all", "topics", "content_gap", "challenges", "hashtags", "sounds")],
    {"call_id": "searchwords", "tool": "get_tikhub_tiktok_web_fetch_trending_searchwords", "arguments": {}},
    {"call_id": "music_top50", "tool": "get_tikhub_tiktok_app_v3_fetch_music_chart_list", "arguments": {"scene": 0, "cursor": 0, "count": 50}},
    {"call_id": "music_viral50", "tool": "get_tikhub_tiktok_app_v3_fetch_music_chart_list", "arguments": {"scene": 1, "cursor": 0, "count": 50}},
]
# Keys whose string values name something: a query, a hashtag, a song.
NAME_KEYS = re.compile(r"^(title|keyword|keywords|word|query|query_text|search_word|hashtag_name|hashtagName|"
                       r"cha_name|challenge_name|music_name|song_name|name|display_name|author)$", re.I)
MAX_PER_CHART = 60


def harvest(node, out: list[str], key: str = "") -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            harvest(v, out, k)
    elif isinstance(node, list):
        for v in node:
            harvest(v, out, key)
    elif isinstance(node, str) and NAME_KEYS.match(key) and 2 <= len(node) <= 80 and not node.startswith("http"):
        out.append(node.strip())


def main() -> int:
    cfg = config.load(Path("config.json"))
    OUT.mkdir(exist_ok=True)
    results, cost = [], 0
    for i in range(0, len(CALLS), aisa.BATCH):
        body = aisa._post(aisa.ROUTER, {"calls": CALLS[i:i + aisa.BATCH]}, aisa.TIMEOUT)
        results += body.get("results", [])
        if "error" in body:
            results.append({"call_id": f"batch{i}", "successful": False, "error": body["error"]})
    lines = ["# TikTok charts, one look", ""]
    for r in results:
        cid = r.get("call_id", "?")
        cost += int(r.get("customer_cost_micros_usd") or 0)
        (OUT / f"{cid}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
        if not r.get("successful"):
            lines += [f"## {cid}: failed", "", f"`{json.dumps(r.get('error') or r, ensure_ascii=False)[:400]}`", ""]
            continue
        names: list[str] = []
        harvest(r.get("data") or {}, names)
        names = list(dict.fromkeys(names))[:MAX_PER_CHART]
        rows = [{"term": n.lower(), "examples": [n]} for n in names]
        status = judge.score(rows, cfg["judge"]["model"], cfg["judge"].get("focus", "names")) if rows else {"judged": 0}
        lines += [f"## {cid}: {len(names)} names, judge {status}", "", "| # | name | score | kept |", "|---|---|---|---|"]
        for j, row in enumerate(rows, 1):
            sc = row.get("named")
            kept = "✅" if sc is not None and sc >= cfg["judge"]["min_score"] else ""
            lines.append(f"| {j} | {row['examples'][0]} | {sc if sc is not None else '—'} | {kept} |")
        lines.append("")
    lines.append(f"AIsa cost: ${cost / 1e6:.4f} (the judge's model calls apart)")
    (OUT / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
