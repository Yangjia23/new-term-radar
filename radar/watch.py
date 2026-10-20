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
for years. So a name found in them is read in Google Trends (one task, about $0.0012): one
that rose in the last three weeks out of almost nothing is pushed with the day it started;
one searched before is set aside as old and not pushed. Too few searches for Trends to draw
a curve, it is pushed and says so.
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
from .usecases import shape

SUGGEST = "https://suggestqueries.google.com/complete/search"
# A completion with one of these asks for a template: "hotel lobby ai video", "burning bridges ai video generator free".
# Without, "bulin 47 ai" alone, the need is there but its shape is not: a weak lead, for a person to read.
TEMPLATE = re.compile(r"\b(video|videos|trend|filter|meme|generator|template|effect|edit|prompt|prompts|app)\b")
TIMEOUT = 15
# Trends for a name Google completes with "ai": 90 days worldwide, a rise judged in the last 21
# against the 69 before. Under usecases.NEW_BASE_MAX before, the name is new.
FRESH_DAYS = 90
FRESH = {"unsettled": review.UNSETTLED_DAYS, "window": 21, "factor": review.RISE_FACTOR, "days": 2}
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
    """Each name's worldwide Trends curve over FRESH_DAYS: {term: usecases.shape(...)}. A name that
    rose in the last FRESH["window"] days out of almost nothing is new; one that was searched before
    (a May meme, "reporter voice") is not. A failed lookup leaves the name out."""
    window = {"date_from": (today - timedelta(days=FRESH_DAYS)).isoformat(), "date_to": today.isoformat()}
    calls = [{"call_id": f"f{i}", "tool": review.TOOL, "arguments": {"body": [{"keywords": [k], **window}]}}
             for i, k in enumerate(terms)]
    data, cost = aisa.call_all(calls)
    out = {}
    for i, k in enumerate(terms):
        if f"f{i}" in data:
            out[k] = shape(review._series((data[f"f{i}"].get("tasks") or [{}])[0]), today, FRESH)
    return out, cost


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
