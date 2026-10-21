"""Today's TikTok videos that sell an AI template: can the names of new trends be read from them?

On TikTok, CapCut's template creators post a trend's template days before the first site for it
(toc toc on 4 October 2026, its first site on the 9th; crazy frog on 11 October, its sites on the
16th), with #capcutpioneer #pioneertemplate and "how to make the ... ai trend". This reads the
videos of the last day for those tags and phrases, cuts candidate names from their captions,
and ranks them by authors and plays. Writes probe/report.md, the raw answers under probe/.

    python scripts/probe_templates.py      # needs AISA_API_KEY
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import aisa  # noqa: E402

SEARCH = "get_tikhub_tiktok_app_v3_fetch_video_search_result"
CHALLENGE = "get_tikhub_tiktok_app_v3_fetch_challenge_info"
POSTS = "get_tikhub_tiktok_app_v3_fetch_challenge_post_list"
TAGS = ["pioneertemplate", "capcutpioneer", "aitrend", "capcuttemplate"]
QUERIES = ["#pioneertemplate", "#capcutpioneer ai", "ai trend template", "ai dance tutorial", "ai trend tutorial",
           "capcut ai template", "new ai trend"]
PAGES = 2
# "how to make the toc toc ai dance", "the viral crazy frog trend", "toc toc ai dance tutorial"
NAMED = [re.compile(p) for p in (
    r"(?:the|this|viral|new)\s+([a-z0-9][a-z0-9' ]{2,30}?)\s+(?:ai\s+)?(?:dance|video|filter|effect)?\s*trend\b",
    r"\b([a-z0-9][a-z0-9' ]{2,30}?)\s+ai\s+(?:dance|video|filter|effect|template|trend|tutorial|edit)\b",
    r"how to (?:make|do|create)\s+(?:the|this)?\s*([a-z0-9][a-z0-9' ]{2,30}?)\s+(?:ai|trend|video|dance)\b",
)]
STOP = {"ai", "the", "this", "new", "viral", "capcut", "tiktok", "trend", "trending", "video", "how to make", "make", "free",
        "easy", "best", "cute", "funny", "my", "your", "a", "an", "dance", "template", "photo", "picture"}
GENERIC_TAGS = {"fyp", "foryou", "foryoupage", "viral", "trend", "trending", "capcut", "capcutpioneer", "pioneertemplate",
                "capcuttemplate", "template", "ai", "aitrend", "aivideo", "aiart", "aidance", "dance", "tutorial", "edit",
                "fy", "fypシ", "xyzbca", "capcutedit", "capcut_edit", "aiedit", "aifilter", "aieffect", "newtrend",
                "trendingtemplate", "pioneer", "capcutvelocity", "ia", "parati", "pourtoi", "fürdich", "fypage"}


def _items(answer: dict) -> list[dict]:
    data = answer.get("data", answer) if isinstance(answer, dict) else {}
    items = data.get("search_item_list") or data.get("aweme_list") or data.get("data") or []
    return [it.get("aweme_info", it) for it in items if isinstance(it, dict)]


def _video(a: dict) -> dict | None:
    if not a.get("create_time"):
        return None
    tags = [x.get("hashtag_name", "").lower() for x in a.get("text_extra") or [] if x.get("hashtag_name")]
    return {"id": a.get("aweme_id"), "day": datetime.fromtimestamp(a["create_time"], timezone.utc).isoformat()[:16],
            "plays": (a.get("statistics") or {}).get("play_count") or 0,
            "author": (a.get("author") or {}).get("unique_id"), "desc": a.get("desc") or "", "tags": tags}


def names(v: dict) -> set[str]:
    text = re.sub(r"#\w+", " ", v["desc"].lower())
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    out = set()
    for p in NAMED:
        for m in p.finditer(text):
            n = " ".join(w for w in m.group(1).split() if w not in {"the", "this", "viral", "new", "a"})
            if n and n not in STOP and len(n.replace(" ", "")) >= 4:
                out.add(n)
    return out


def each(calls: list[dict]) -> tuple[dict, dict, int]:
    """Every call alone, so one bad call says why instead of failing the batch."""
    data, errors, cost = {}, {}, 0
    for c in calls:
        try:
            d, n = aisa.call([c])
        except aisa.AisaError as exc:
            errors[c["call_id"]] = str(exc)[:300]
            continue
        cost += n
        if c["call_id"] in d:
            data[c["call_id"]] = d[c["call_id"]]
        else:
            errors[c["call_id"]] = "failed"
    return data, errors, cost


def main() -> int:
    out = Path("probe")
    out.mkdir(exist_ok=True)
    first = [{"call_id": f"c_{t}", "tool": CHALLENGE, "arguments": {"challenge_name": t}} for t in TAGS]
    first += [{"call_id": f"q{i}_{p}", "tool": SEARCH,
               "arguments": {"keyword": q, "offset": p * 20, "count": 20, "sort_type": 0, "publish_time": 1}}
              for i, q in enumerate(QUERIES) for p in range(PAGES)]
    data, errors, cost = each(first)
    ids = {}
    for t in TAGS:
        info = (data.get(f"c_{t}") or {}).get("data", data.get(f"c_{t}") or {})
        ch = info.get("ch_info") or info.get("challenge_info") or info.get("challengeInfo") or {}
        cid = ch.get("cid") or ch.get("id") or info.get("cid")
        if cid:
            ids[t] = cid
        elif f"c_{t}" in data:
            errors[f"c_{t}"] = "no id in " + json.dumps(data[f"c_{t}"])[:300]
    second = [{"call_id": f"p_{t}_{p}", "tool": POSTS, "arguments": {"ch_id": cid, "cursor": p * 20, "count": 20}}
              for t, cid in ids.items() for p in range(PAGES)]
    more, errors2, cost2 = each(second)
    data.update(more)
    errors.update(errors2)
    (out / "raw.json").write_text(json.dumps(data, ensure_ascii=False)[:8_000_000])

    lines = ["# Template videos of the last day", "", "## Answers", ""]
    for c in first + second:
        a = data.get(c["call_id"])
        lines.append(f"- {c['call_id']} ({c['tool'].rsplit('_', 3)[-3:]}): {errors.get(c['call_id'], 'no answer') if a is None else f'{len(_items(a))} videos'}")
    lines.append(f"- hashtag ids: {ids}")
    videos = {}
    for k, a in data.items():
        if k.startswith(("q", "p_")):
            for it in _items(a):
                v = _video(it)
                if v:
                    v["from"] = k
                    videos.setdefault(v["id"], v)
    recent = sorted(videos.values(), key=lambda v: v["day"], reverse=True)
    by_name: dict[str, dict] = defaultdict(lambda: {"authors": set(), "plays": 0, "videos": 0, "examples": []})
    by_tag: dict[str, dict] = defaultdict(lambda: {"authors": set(), "plays": 0, "videos": 0})
    for v in recent:
        for n in names(v):
            r = by_name[n]
            r["authors"].add(v["author"])
            r["plays"] += v["plays"]
            r["videos"] += 1
            if len(r["examples"]) < 2:
                r["examples"].append(f"{v['day']} @{v['author']}: {v['desc'][:80]}")
        for tg in set(v["tags"]) - GENERIC_TAGS:
            r = by_tag[tg]
            r["authors"].add(v["author"])
            r["plays"] += v["plays"]
            r["videos"] += 1
    lines += ["", f"## {len(videos)} videos, newest {recent[0]['day'] if recent else '-'}, oldest {recent[-1]['day'] if recent else '-'}", "",
              "## Names cut from captions (authors, videos, plays)", ""]
    for n, r in sorted(by_name.items(), key=lambda x: (-len(x[1]["authors"]), -x[1]["plays"]))[:40]:
        lines.append(f"- **{n}** · {len(r['authors'])} authors · {r['videos']} videos · {r['plays']:,} plays — {' | '.join(r['examples'])}")
    lines += ["", "## Hashtags past the generic ones (authors, videos, plays)", ""]
    for n, r in sorted(by_tag.items(), key=lambda x: (-len(x[1]["authors"]), -x[1]["plays"]))[:40]:
        lines.append(f"- #{n} · {len(r['authors'])} authors · {r['videos']} videos · {r['plays']:,} plays")
    lines += ["", "## Every video, newest first", ""]
    lines += [f"- {v['day']} · {v['plays']:,} · @{v['author']} · [{v['from']}] {v['desc'][:120]}" for v in recent[:200]]
    lines += ["", f"AIsa cost: ${(cost + cost2) / 1e6:.4f}"]
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
