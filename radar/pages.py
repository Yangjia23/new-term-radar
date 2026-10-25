"""Signal ① pages: the trend pages an AI tool site puts up for one viral clip or meme.

Dreamina (CapCut) writes a page per trend under /ai-video/ and /ai-image/, one slug each:
/ai-video/ozil-goal-ai-video-generator went up on 13 October 2026 (its createdAt), four
days before "ozil goal ai" rose in Google Trends. The slug is the name: a page new to the
sitemap since the last run is reported with its tail words cut ("ozil goal"). The first
run only keeps what is there.

    "pages": {
      "dreamina": {"index": "https://dreamina.capcut.com/sitemap/new/513641/article/sitemap_index.xml",
                   "shards": "/default/index\\\\d+\\\\.xml$", "sections": ["ai-video", "ai-image", "create"]}
    }

`index` and `shards` read the sitemap as in "sitemaps"; `sections` are the first path
segments to keep, `skip` the first path segments to drop. tryatrend.com, a hand-picked list of
AI trends since 16 October 2026, keeps each trend at the root (/witch-broom-ai,
/sorry-i-lied-costume-ai) beside its guides, its Spanish and Japanese copies and its pricing:

      "tryatrend": {"index": "https://tryatrend.com/sitemap.xml",
                    "skip": ["guides", "es", "ja", "pricing", "terms", "privacy", "halloween", "pets"]}

The sitemap's lastmod is the day it was built for every URL, so the snapshot, not lastmod,
says what is new. A site whose list is picked by hand (tryatrend) is marked "curated": its new
page is the evidence itself, pushed at once (radar/pushes.py); a site that makes a page for
anything (Dreamina: "fire text", "character reference sheets") only feeds the watch list.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from . import snap
from .i18n import t
from .sitemaps import DEFAULT_PAUSE, site_urls

MAX_TERMS = 30
MIN_LEN = 4
MAX_WORDS = 5     # a trend is named in a few words; a longer slug is a guide ("how small teams scale promo videos")
# The words a trend page's slug carries after (or before) its name: ozil-goal-ai-video-generator.
TAILS = {"ai", "video", "videos", "generator", "image", "images", "photo", "photos", "picture", "prompt", "prompts",
         "template", "templates", "trend", "trending", "filter", "filters", "effect", "effects", "maker", "editor",
         "editing", "free", "online", "creator", "animation", "style", "art", "tool"}


def name(slug: str) -> str:
    """The name in a trend page's slug: "ozil-goal-ai-video-generator" -> "ozil goal"."""
    words = [w for w in slug.lower().split("-") if w]
    while words and words[-1] in TAILS:
        words.pop()
    while words and words[0] in TAILS:
        words.pop(0)
    return " ".join(words)


def new_pages(cfg: dict, state: Path) -> dict:
    if not cfg["pages"]:
        return {"skipped": True}
    sites, rows, errors = {}, {}, []
    for i, (site, s) in enumerate(cfg["pages"].items()):
        path = state / "pages" / f"{re.sub(r'[^A-Za-z0-9._-]', '_', site)}.json.gz"
        stored = snap.load(path)
        old = set(stored) if stored is not None else None
        pause = s.get("pause", DEFAULT_PAUSE)
        try:
            if i:
                time.sleep(pause)
            urls = site_urls(s["index"], s.get("shards"), pause)
        except Exception as exc:  # noqa: BLE001 — one site down must not stop the others
            errors.append(f"{site}: {str(exc)[:120]}")
            continue
        sections, skip = tuple(s.get("sections") or ()), set(s.get("skip") or ())
        first = {u: re.sub(r"^https?://[^/]+/", "", u).split("/")[0] for u in urls}
        now = {u for u, seg in first.items() if seg and (not sections or seg in sections) and seg not in skip}
        if not now:     # blocked, empty or a format the reader misses: say so rather than wait forever
            errors.append(f"{site}: no URLs read")
            continue
        new = sorted(now - old) if old is not None else []
        sites[site] = {"urls": len(now), "new": len(new), "first_run": old is None}
        for u in new:
            slug = u.rstrip("/").rsplit("/", 1)[-1]
            term = name(slug)
            if len(term.replace(" ", "")) < MIN_LEN or term.replace(" ", "").isdigit() or term.count(" ") >= MAX_WORDS:
                continue
            row = rows.setdefault(term, {"term": term, "examples": [], "variants": [term, f"{term} ai"], "recent": 0,
                                         "note": t("note_pages", site=site)})
            if s.get("curated"):
                row["curated"] = site
            row["recent"] += 1
        snap.save(path, sorted(now))
    out = {"sites": sites, "read": sum(v["urls"] for v in sites.values()), "new": sum(v["new"] for v in sites.values()),
           "first_run": bool(sites) and all(v["first_run"] for v in sites.values()), "terms": list(rows.values())[:MAX_TERMS]}
    if errors:
        out["errors"] = errors
        if not sites:
            out["error"] = "; ".join(errors[:2])
    return out
