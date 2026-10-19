"""Signal ① searchwords: what people search on TikTok today, new since the last run.

TikTok's web search lists the day's trending searches (read through AIsa, TikHub behind it,
$0.001 a call). On 19 October 2026 half of its 93 were memes, trends and challenges
("Hell Nah Cuh TikTok Meme", "foam mirror tiktok trend", "Bulin 47's Freestyle Surpasses
50M Views"), the rest news and sports for the judge to drop. A search is reported the run
it first shows, cut to its name ("foam mirror tiktok trend" -> "foam mirror"). The first
run reports them all: they are the watch list's first names (radar/watch.py).

These names are not pushed on their own: TikTok shows what is viral, not what anyone wants
an AI tool for. The watch list asks Google that, and pushes a name once people search it
with "ai".
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from . import aisa, snap
from .i18n import t

TOOL = "get_tikhub_tiktok_web_fetch_trending_searchwords"
SEEN_DAYS = 60
MIN_LEN = 4
# The words a trending search carries around its name: "foam mirror tiktok trend", "fish sweater TikTok goes viral".
TAILS = ("goes viral", "go viral", "tiktok", "trend", "trends", "trending", "meme", "memes", "challenge", "viral",
         "original", "videos", "video", "clips")


def name(word: str) -> str:
    """The name in a trending search: tail words off both ends, a possessive off the name."""
    w = re.sub(r"[’']s\b", "", word.lower())
    w = re.sub(r"[^\w\s/-]", " ", w)
    w = " ".join(w.split())
    cut = True
    while cut:
        cut = False
        for tail in TAILS:
            if w.endswith(" " + tail) or w == tail:
                w, cut = w[:-len(tail)].strip(), True
            elif w.startswith(tail + " "):
                w, cut = w[len(tail):].strip(), True
    return w


def words() -> tuple[list[str], int]:
    data, cost = aisa.call([{"call_id": "w", "tool": TOOL, "arguments": {}}])
    items = (((data.get("w") or {}).get("data") or {}).get("trending_search_words")) or []
    out = [it["trendingSearchWord"].strip() for it in items if (it.get("trendingSearchWord") or "").strip()]
    if not out:
        raise aisa.AisaError("no trending search words")
    return out, cost


def trending(cfg: dict, state: Path, today: date | None = None) -> dict:
    if not cfg["searchwords"]["on"]:
        return {"skipped": True}
    today = today or date.today()
    path = state / "searchwords.json.gz"
    stored = snap.load(path)
    seen: dict[str, str] = stored or {}
    got, cost = words()
    rows: dict[str, dict] = {}
    new = 0
    for w in got:
        key = " ".join(w.lower().split())
        if key in seen:
            seen[key] = today.isoformat()
            continue
        seen[key] = today.isoformat()
        new += 1
        term = name(w)
        if len(term.replace(" ", "")) < MIN_LEN:
            continue
        row = rows.setdefault(term, {"term": term, "examples": [], "variants": [term, f"{term} ai"], "recent": 0,
                                     "note": t("note_searchwords", word=w)})
        row["examples"].append(w)
        row["recent"] += 1
    cutoff = (today - timedelta(days=SEEN_DAYS)).isoformat()
    snap.save(path, {k: d for k, d in seen.items() if d >= cutoff})
    return {"read": len(got), "new": new, "first_run": stored is None, "cost_micros": cost, "terms": list(rows.values())}
