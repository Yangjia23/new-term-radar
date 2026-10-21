"""Signal ① templates: the trends TikTok's template makers are selling, by the hashtags they use.

A trend reaches TikTok's trending searches once many people search it; the accounts that sell
its AI template (CapCut's "Pioneer" creators and the like) post it days before. "dime dime baby"
was a trending search on 19 October 2026, its first #ai version on the 14th; toc toc's AI
tutorials ran from 3 October, its trending search on the 20th. Their captions are copied and
pasted, often in Spanish or Vietnamese, and say little; their hashtags name the trend:
#dimedimebaby, #bailedimedimebaby, #toctoctrend, #broomridingtrend.

Each run searches TikTok's videos of the last day for a few phrases those accounts use
(about $0.001 a search), cuts each hashtag to its name (#toctoctrend -> toctoc,
#tendenciadimedimebaby -> dimedimebaby), and drops the hashtags every such video carries
(#capcut, #fyp, #aidance). A name `min_authors` accounts used within `days` is reported once,
written as the captions write it ("dime dime baby"). Like the trending searches, these names
are not pushed on their own: they join the watch list (radar/watch.py), which pushes a name
once its AI versions spread on TikTok or Google completes it with "ai".
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from . import aisa, snap
from .i18n import t

TOOL = "get_tikhub_tiktok_app_v3_fetch_video_search_result"
QUERIES = ["#pioneertemplate", "#capcutpioneer ai", "ai trend template", "ai dance tutorial", "ai trend tutorial",
           "capcut ai template", "new ai trend"]
MIN_LEN = 5
# Words glued around a trend's name in a hashtag, in the languages these accounts post in.
PREFIXES = ("tendencia", "trend", "baile", "capcut", "ai", "ia", "new", "the", "original")
SUFFIXES = ("aidancetutorial", "aidanceeffect", "aidance", "aitrend", "aivideo", "aifilter", "aieffect", "tutorial",
            "template", "challenge", "trends", "trend", "dance", "effect", "filter", "video", "edit", "original",
            "ai", "ia")
# A hashtag of the platform or the reach, whatever follows: #capcutforus, #fyp🎵, #trendingtiktok, #nhachaymoingay.
PLATFORM = re.compile(r"^(capcut|pioneer|fyp|foryou|viral|trending|tiktok|xyz|parati|pourtoi|fürdich|explore|reels|nhac)")
# A name that names no trend: the kind of video, a common word.
GENERIC = {"dance", "baile", "tutorial", "template", "filter", "effect", "photo", "video", "funny", "meme", "halloween",
           "aesthetic", "love", "baby", "couple", "cute", "motivation", "motivasi", "reminder", "overlay", "window",
           "possible", "music", "lyrics", "song", "edits", "editing", "photoediting", "trend", "trends", "viral",
           "musicwithlyrics", "lyricssong", "aestheticlyrics", "foryoupage", "million", "views", "millionviews"}


def core(tag: str) -> str:
    """The name in a hashtag, without the words glued around it: "tendenciadimedimebaby" -> "dimedimebaby"."""
    c = re.sub(r"[^a-z0-9]", "", tag.lower())
    cut = True
    while cut:
        cut = False
        for p in PREFIXES:
            if c.startswith(p) and len(c) - len(p) >= MIN_LEN:
                c, cut = c[len(p):], True
        for s in SUFFIXES:
            if c.endswith(s) and len(c) - len(s) >= MIN_LEN:
                c, cut = c[:-len(s)], True
    return c


def named(tag: str, c: str) -> bool:
    """Whether a hashtag, cut to `c`, names a trend."""
    return len(c) >= MIN_LEN and not c.isdigit() and c not in GENERIC and not PLATFORM.match(tag.lower())


def written(c: str, captions: list[str]) -> str:
    """The name as the captions write it: "dimedimebaby" -> "dime dime baby"; the hashtag's letters when none does."""
    pattern = re.compile(r"(?<![a-z0-9])" + r"[\s'-]*".join(map(re.escape, c)) + r"(?![a-z0-9])")
    seen = Counter(" ".join(m.group(0).replace("-", " ").replace("'", "").split())
                   for text in captions for m in pattern.finditer(re.sub(r"#\w+", " ", text.lower())))
    spaced = [(n, k) for n, k in seen.items() if " " in n]
    return max(spaced, key=lambda x: x[1])[0] if spaced else c


def _videos(answer: dict) -> list[dict]:
    data = answer.get("data", answer) if isinstance(answer, dict) else {}
    out = []
    for it in data.get("search_item_list") or data.get("aweme_list") or []:
        a = it.get("aweme_info", it) if isinstance(it, dict) else {}
        if not a.get("create_time"):
            continue
        out.append({"author": (a.get("author") or {}).get("unique_id") or "", "desc": a.get("desc") or "",
                    "plays": (a.get("statistics") or {}).get("play_count") or 0,
                    "tags": [x["hashtag_name"] for x in a.get("text_extra") or [] if x.get("hashtag_name")]})
    return out


def trending(cfg: dict, state: Path, today: date | None = None) -> dict:
    c = cfg["templates"]
    if not c.get("on"):
        return {"skipped": True}
    today = today or date.today()
    calls = [{"call_id": f"q{i}", "tool": TOOL, "arguments": {"keyword": q, "offset": 0, "count": 20, "sort_type": 0,
                                                             "publish_time": 1}}
             for i, q in enumerate(c.get("queries") or QUERIES)]
    data, cost = aisa.call_all(calls)
    if not data:
        raise aisa.AisaError("no video search answered")
    videos = {(v["author"], v["desc"]): v for a in data.values() for v in _videos(a)}.values()
    path = state / "templates.json.gz"
    kept: dict[str, dict] = snap.load(path) or {}
    since = (today - timedelta(days=c["days"])).isoformat()
    keep = (today - timedelta(days=60)).isoformat()      # a reported name is not reported again for 60 days
    kept = {k: v for k, v in kept.items() if v["first"] >= since or (v.get("reported") or "") >= keep}
    for v in videos:
        for k in {core(tg) for tg in v["tags"] if named(tg, core(tg))}:
            row = kept.setdefault(k, {"first": today.isoformat(), "authors": [], "plays": 0, "tags": [], "captions": []})
            if row.get("reported"):
                continue
            if v["author"] not in row["authors"]:
                row["authors"].append(v["author"])
                row["plays"] += v["plays"]
            row["tags"] = sorted(set(row["tags"]) | {tg.lower() for tg in v["tags"] if core(tg) == k})[:5]
            if v["desc"] and len(row["captions"]) < 5 and v["desc"] not in row["captions"]:
                row["captions"].append(v["desc"][:300])
    terms = []
    for k, row in kept.items():
        if row.get("reported") or len(row["authors"]) < c["min_authors"]:
            continue
        row["reported"] = today.isoformat()
        term = written(k, row["captions"])
        terms.append({"term": term, "recent": len(row["authors"]), "lift": 0, "examples": row["captions"][:2],
                      "variants": list(dict.fromkeys([term, f"{term} ai"])),
                      "note": t("note_templates", n=len(row["authors"]), tags=" ".join("#" + x for x in row["tags"][:3]))})
    snap.save(path, kept)
    return {"read": len(videos), "new": len(terms), "terms": terms, "cost_micros": cost}
