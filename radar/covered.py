"""Whether a big AI tool site already has a page for a name about to be pushed.

"my ride is here", a broom-riding Halloween template on TikTok on 21 October 2026, had no site of
its own, and Dreamina had /ai-video/my-ride-is-here-ai-broom-trend since the 10th: a trend the
big sites serve already is a harder one to build for. The push says so.

Dreamina's pages are looked for in the sitemap the `pages` signal keeps, then at the slugs its
trend pages take ("closed-on-sunday-ai-video", "toc-toc-dance-ai-video-trend"): the sitemap is
rebuilt now and then (on 21 October it was the one of the 19th), the pages go up every day.
One GET a slug, free.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import UA, snap
from .pages import name

BASE = "https://dreamina.capcut.com/ai-video/"
SLUGS = ("{}-ai-video", "{}-ai-video-trend", "{}-ai-trend", "{}-ai-video-generator", "{}-video", "ai-{}-video",
         "{}-trend")
TIMEOUT = 10
WORKERS = 16


def _flat(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def live(url: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return res.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def dreamina(state: Path, terms: list[str]) -> dict[str, str]:
    """{term: the Dreamina page for it} for the terms Dreamina has one for."""
    urls = snap.load(state / "pages" / "dreamina.json.gz") or []
    by_name = {}
    for u in urls:
        key = _flat(name(u.rstrip("/").rsplit("/", 1)[-1]))
        if len(key) >= 5:
            by_name.setdefault(key, u)
    out, guess = {}, []
    for term in terms:
        key = _flat(term)
        hit = by_name.get(key) or next((u for k, u in by_name.items() if key in k and len(key) >= 6), None)
        if hit:
            out[term] = hit
        else:
            slug = "-".join(re.sub(r"[^a-z0-9 ]", "", term.lower()).split())
            guess += [(term, BASE + s.format(slug)) for s in SLUGS] if slug else []
    with ThreadPoolExecutor(WORKERS) as pool:
        found = list(pool.map(lambda g: live(g[1]), guess))
    for (term, url), ok in zip(guess, found):
        if ok and term not in out:
            out[term] = url
    return out
