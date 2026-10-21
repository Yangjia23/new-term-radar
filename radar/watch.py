"""The watch list: names that look like a trend, kept until people search them with "ai".

A trend on TikTok is not yet a need: on 19 October 2026 Google completed "hotel lobby ai"
to "hotel lobby ai video", "... ai filter", "... ai trend", and "burning bridges ai" to
"... ai video generator free", while "foam mirror ai" or "hell nah cuh ai", trending on
TikTok the same day, completed to nothing. The day Google starts completing "<name> ai"
is the day people look for the tool.

Names the judge scored at or over watch.min_score from the kinds in watch.kinds join the
list. Once a day each is looked up in Google's autocomplete (free, one request a name,
`pause` seconds apart); the first time a completion holds the name and "ai", it becomes a
"demand" lead with those completions, and is not looked up again. A name leaves the list
after `days`.

Completions say people search a name, not since when: "reporter voice ai" has been searched
for years. So a name found in them is read in Google Trends, "<name> ai" and the name alone (two tasks,
about $0.0024): when "<name> ai" rose in the last three weeks out of almost nothing, the name
is pushed with the day it started; searched before, it is set aside as old and not pushed.
"<name> ai" too small for a curve, the name alone decides; both too small, it is pushed and
says so.

Google completes a name days after the first sites for it are up. TikTok has the AI versions
first: "toc toc ai dance tutorial" on 3 October 2026, its first site on the 9th, Google's
completion on the 21st. So each name the judge scored at `tiktok_min` or over is also searched
on TikTok once a day, "<name> ai" over the last week (about $0.0015 a search, `tiktok_max` a
run): `tiktok_authors` accounts posting an AI version, a tutorial or a template push it at once.
The AI versions may use another name than the one watched: "baby wow karol g", a TikTok search
of 19 October, is "dime dime baby ai" in their captions, and is pushed under that name.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from . import UA, aisa, review, snap
from .i18n import t
from .usecases import NEW_BASE_MAX, shape

SUGGEST = "https://suggestqueries.google.com/complete/search"
# A completion with one of these asks for a template: "hotel lobby ai video", "burning bridges ai video generator free".
# Without, "bulin 47 ai" alone, the need is there but its shape is not: a weak lead, for a person to read.
TEMPLATE = re.compile(r"\b(video|videos|trend|filter|meme|generator|template|effect|edit|prompt|prompts|app)\b")
TIMEOUT = 15
# Trends for a name Google completes with "ai": 90 days worldwide, a rise judged in the last 21
# against the 69 before. Under usecases.NEW_BASE_MAX before, the name is new.
FRESH_DAYS = 90
FRESH = {"unsettled": review.UNSETTLED_DAYS, "window": 21, "factor": review.RISE_FACTOR, "days": 2}
SPIKE_PEAK = 50       # of 100: a one-day spike in the window counts when it is the series' high
_AI = re.compile(r"\bai\b")
VIDEO = "get_tikhub_tiktok_app_v3_fetch_video_search_result"
# A caption of an AI version of a trend: "#ai", "ia" (Spanish), a CapCut template, a tutorial.
AI_VERSION = re.compile(r"(?:^|[\s#])(ai|ia|aidance|aivideo|aitrend|aieffect|aifilter|capcutpioneer|pioneertemplate)\b"
                        r"|\b(tutorial|template)\b")
# The name an AI version goes by, read before "ai": "dime dime baby ai tutorial".
_AI_NAME = re.compile(r"([a-z0-9][a-z0-9' ]{2,40}?)\s+(?:ai|ia)\s+(?:tutorial|dance|video|trend|effect|filter|template|edit)")
_LEADING = {"the", "a", "original", "viral", "new", "how", "to", "make", "create", "do", "this", "trend", "tutorial",
            "dance", "ai", "video", "and", "guy", "girl"}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return res.read()


def suggest(query: str, gl: str) -> list[str]:
    url = SUGGEST + "?" + urllib.parse.urlencode({"client": "firefox", "hl": "en", "gl": gl, "q": query})
    answer = json.loads(_get(url).decode("utf-8", "replace"))
    return [s for s in answer[1] if isinstance(s, str)] if isinstance(answer, list) and len(answer) > 1 else []


def demand(term: str, completions: list[str]) -> list[str]:
    """The completions that are the name with "ai": "hotel lobby ai video", not "hotel lobby air diffuser"."""
    flat = term.replace(" ", "")
    return [c for c in completions if flat in c.lower().replace(" ", "") and _AI.search(c.lower())]


def add(cfg: dict, state: Path, lead: list[dict], today: date | None = None) -> int:
    """Puts the judged names of the watched kinds on the list; returns how many joined."""
    today = today or date.today()
    path = state / "watch.json.gz"
    kept: dict[str, dict] = snap.load(path) or {}
    kinds, cut, joined = set(cfg["watch"]["kinds"]), cfg["watch"]["min_score"], 0
    for r in lead:
        key = r["term"].replace(" ", "")
        if key in kept or r["known"] or not kinds & set(r["kinds"]) or r.get("named", 0) < cut:
            continue
        kept[key] = {"term": r["term"], "added": today.isoformat(), "kinds": sorted(kinds & set(r["kinds"])),
                     "score": r.get("named"), "checked": None, "found": None, "completions": []}
        joined += 1
    snap.save(path, kept)
    return joined


def strong(completions: list[str]) -> bool:
    return any(TEMPLATE.search(c.lower()) for c in completions)


def _term(w: dict) -> dict:
    found = w["completions"]
    days = (date.fromisoformat(w["found"]) - date.fromisoformat(w["added"])).days
    sure = strong(found)
    top = next((c for c in found if TEMPLATE.search(c.lower())), found[0])
    curve = w.get("curve") or {}
    when = t("demand_tiny") if curve.get("no_data") else t("demand_new", day=curve["started"][5:], now=t("now_" + curve["now"]))
    return {"term": w["term"], "examples": found[:3], "variants": [w["term"], f"{w['term']} ai", *found[:3]],
            "recent": len(found), "floor": w.get("score"), "strong": sure,
            "note": t("note_demand_strong" if sure else "note_demand_weak", top=top, n=len(found), days=days) + when}


def fresh(terms: list[str], today: date) -> tuple[dict[str, dict], int]:
    """Each name's worldwide Trends curves over FRESH_DAYS, "<name> ai" first: {term: shape} with
    "asked" the phrase read. "<name> ai" is the need itself: "burning bridges" is a song and a
    phrase searched all year (a base of 29 of 100), "burning bridges ai" was not. Too small for a
    curve, the name alone is read. A failed lookup leaves the name out."""
    window = {"date_from": (today - timedelta(days=FRESH_DAYS)).isoformat(), "date_to": today.isoformat()}
    asks = [(term, phrase) for term in terms for phrase in (f"{term} ai", term)]
    calls = [{"call_id": f"f{i}", "tool": review.TOOL, "arguments": {"body": [{"keywords": [phrase], **window}]}}
             for i, (_, phrase) in enumerate(asks)]
    data, cost = aisa.call_all(calls)
    curves: dict[str, dict] = {}
    for i, (term, phrase) in enumerate(asks):
        if f"f{i}" in data:
            curves[phrase] = {**shape(review._series((data[f"f{i}"].get("tasks") or [{}])[0]), today, FRESH), "asked": phrase}
    out = {}
    for term in terms:
        ai, bare = curves.get(f"{term} ai"), curves.get(term)
        pick = ai if ai and not ai.get("no_data") else bare if bare else ai
        if pick is not None:
            out[term] = _spike(pick, today)
    return out, cost


def _spike(curve: dict, today: date) -> dict:
    """A curve too thin for a two-day rise, out of nothing and at its highest in the window, is new
    too: "zombie couple ai" read 0 for 89 days and 100 on 15 October 2026, the week its domains were
    registered. "reporter voice ai" (09-14) and "letter k ai" (09-08) had their one day before the
    window and nothing in it: their window peak is 0, not their spike."""
    start = (today - timedelta(days=FRESH["unsettled"] + FRESH["window"])).isoformat()
    if curve.get("no_data") or curve.get("new") or curve["base"] >= NEW_BASE_MAX or curve["peak"] < SPIKE_PEAK \
            or curve["peak_day"] < start:
        return curve
    return {**curve, "new": True, "started": curve["peak_day"], "now": "spike"}


def _flat(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _videos(answer: dict) -> list[dict]:
    data = answer.get("data", answer) if isinstance(answer, dict) else {}
    out = []
    for it in data.get("search_item_list") or data.get("aweme_list") or []:
        a = it.get("aweme_info", it) if isinstance(it, dict) else {}
        tags = " ".join("#" + x.get("hashtag_name", "") for x in a.get("text_extra") or [] if x.get("hashtag_name"))
        text = " ".join(f"{a.get('desc') or ''} {tags}".lower().split())
        if a.get("create_time") and AI_VERSION.search(text):
            out.append({"author": (a.get("author") or {}).get("unique_id"), "text": text,
                        "plays": (a.get("statistics") or {}).get("play_count") or 0})
    return out


def _ai_name(text: str) -> str | None:
    m = _AI_NAME.search(re.sub(r"#\w+", " ", text))
    if not m:
        return None
    words = m.group(1).split()[-4:]
    while words and words[0] in _LEADING:
        words.pop(0)
    return " ".join(words) if len("".join(words)) >= 4 else None


def ai_versions(term: str, videos: list[dict], min_authors: int) -> dict | None:
    """The AI versions of `term` among a search's videos, when `min_authors` accounts posted them:
    {"name", "authors", "videos", "plays", "example"}. The videos are those that name the term, or
    the name its AI versions go by when one of them names both."""
    key = _flat(term)
    names: dict[str, set] = {}
    for v in videos:
        n = _ai_name(v["text"])
        if n:
            names.setdefault(n, set()).add(v["author"])
    named = [v for v in videos if key in _flat(v["text"])]
    alt = max((n for n in names if any(_flat(n) in _flat(v["text"]) for v in named)),
              key=lambda n: (len(names[n]), len(n)), default=None)
    keys = {key} | ({_flat(alt)} if alt else set())
    mine = [v for v in videos if any(k in _flat(v["text"]) for k in keys)]
    authors = {v["author"] for v in mine}
    if len(authors) < min_authors:
        return None
    top = max(mine, key=lambda v: v["plays"])
    name = alt if alt and _flat(alt) != key and len(names[alt]) >= 2 else term
    return {"name": name, "authors": len(authors), "videos": len(mine), "plays": sum(v["plays"] for v in mine),
            "example": f"@{top['author']}: {top['text'][:80]}"}


def tiktok(terms: list[str], min_authors: int) -> tuple[dict[str, dict | None], int]:
    """Each name's AI versions on TikTok over the last week, {term: ai_versions or None}. A failed
    search leaves the name out."""
    calls = [{"call_id": f"k{i}", "tool": VIDEO, "arguments": {"keyword": f"{term} ai", "offset": 0, "count": 20,
                                                               "sort_type": 0, "publish_time": 7}}
             for i, term in enumerate(terms)]
    data, cost = aisa.call_all(calls)
    return {term: ai_versions(term, _videos(data[f"k{i}"]), min_authors) for i, term in enumerate(terms) if f"k{i}" in data}, cost


def _tiktok_term(w: dict) -> dict:
    v = w["tiktok"]
    name = v["name"]
    return {"term": name, "examples": [v["example"]], "variants": list(dict.fromkeys([name, f"{name} ai", w["term"]])),
            "recent": v["authors"], "floor": w.get("score"), "strong": True,
            "note": t("note_tiktok_ai", n=v["authors"], videos=v["videos"], plays=f"{v['plays']:,}")
                    + (t("note_tiktok_watched", term=w["term"]) if name != w["term"] else "")}


def check(cfg: dict, state: Path, today: date | None = None) -> dict:
    """Looks up the names not yet looked up today. A name people now search with "ai" is read in
    Trends: new, it is a term; searched for months already, it is set aside as old."""
    c = cfg["watch"]
    if not c["kinds"]:
        return {"skipped": True}
    today = today or date.today()
    path = state / "watch.json.gz"
    kept: dict[str, dict] = snap.load(path) or {}
    cutoff = (today - timedelta(days=c["days"])).isoformat()
    # found names stay (never looked up again); the rest leave after `days`, or under a raised min_score
    kept = {k: w for k, w in kept.items() if w["found"] or (w["added"] >= cutoff and (w.get("score") or 0) >= c["min_score"])}
    due = [w for w in kept.values() if not w["found"] and w["checked"] != today.isoformat()][:c["max_lookups"]]
    hits, errors = [], []
    for i, w in enumerate(due):
        if i:
            time.sleep(c["pause"])
        try:
            found = demand(w["term"], suggest(f"{w['term']} ai", c["gl"]))
        except Exception as exc:  # noqa: BLE001 — one failed lookup, the rest wait for tomorrow
            errors.append(f"{w['term']}: {type(exc).__name__}: {str(exc)[:80]}")
            if len(errors) >= 3:
                break
            continue
        w["checked"] = today.isoformat()
        if found:
            hits.append((w, found[:5]))
    cost, terms, old = 0, [], []
    if hits:
        try:
            curves, cost = fresh([w["term"] for w, _ in hits], today)
        except aisa.AisaError as exc:     # no curve, no verdict: looked up again tomorrow
            curves = {}
            errors.append(f"Trends: {str(exc)[:100]}")
        for w, found in hits:
            curve = curves.get(w["term"])
            if curve is None:
                w["checked"] = None
                continue
            w["found"], w["completions"], w["curve"] = today.isoformat(), found, curve
            if curve.get("no_data") or curve.get("new"):
                w["emitted"] = True
                terms.append(_term(w))
            else:
                w["old"] = True
                old.append(w["term"])
    seen = {w["term"] for w, _ in hits}
    ask = [w for w in kept.values() if not w["found"] and w["term"] not in seen and (w.get("score") or 0) >= c["tiktok_min"]
           and w.get("tchecked") != today.isoformat()][:c["tiktok_max"]]
    if ask:
        try:
            found_tt, tcost = tiktok([w["term"] for w in ask], c["tiktok_authors"])
        except aisa.AisaError as exc:     # looked up again next run
            found_tt, tcost = {}, 0
            errors.append(f"TikTok: {str(exc)[:100]}")
        cost += tcost
        for w in ask:
            if w["term"] not in found_tt:
                continue
            w["tchecked"] = today.isoformat()
            if found_tt[w["term"]]:
                w["found"], w["tiktok"], w["emitted"] = today.isoformat(), found_tt[w["term"]], True
                terms.append(_tiktok_term(w))
    snap.save(path, kept)
    out = {"read": len(due), "watching": sum(1 for w in kept.values() if not w["found"]), "terms": terms,
           "old": old, "cost_micros": cost, "tiktok_read": len(ask)}
    if errors:
        out["errors"] = errors
        if len(errors) >= len(due):
            out["error"] = "; ".join(errors[:2])
    return out
