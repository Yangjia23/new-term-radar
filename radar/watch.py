"""The watch list: names that look like a trend, kept until people search them with "ai".

A trend on TikTok is not yet a need: on 19 October 2026 Google completed "hotel lobby ai"
to "hotel lobby ai video", "... ai filter", "... ai trend", and "burning bridges ai" to
"... ai video generator free", while "foam mirror ai" or "hell nah cuh ai", trending on
TikTok the same day, completed to nothing. The day Google starts completing "<name> ai"
is the day people look for the tool.

Names the judge scored at or over judge.min_score from the kinds in watch.kinds join the
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
    kinds, cut, joined = set(cfg["watch"]["kinds"]), cfg["judge"]["min_score"], 0
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
    kept = {k: w for k, w in kept.items() if w["added"] >= cutoff or w["found"]}
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
    snap.save(path, kept)
    out = {"read": len(due), "watching": sum(1 for w in kept.values() if not w["found"]), "terms": terms,
           "old": old, "cost_micros": cost}
    if errors:
        out["errors"] = errors
        if len(errors) >= len(due):
            out["error"] = "; ".join(errors[:2])
    return out
