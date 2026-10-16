"""Signal ① rising: what people started searching around seed words, from Google Trends.

Google Trends' related queries for a seed ("higgsfield", "ai video") list the searches that
grew most in the window; "Breakout" are those that grew past 5,000%. A new AI trend shows up
there as soon as people search for it together with the tool they make it with: for
"higgsfield", "storm ii ai" was a Breakout over 12-21 September 2026 (the first SEO pages for
it came on 16 October), and "hotel lobby ai" the top Breakout over 15-25 September, before
the trend reached the newsletters on the 28th.

Read through SerpApi (SERPAPI_API_KEY): one search per seed and run, so `seeds` times the runs
a day is what a day costs. SerpApi's account endpoint is free and says how many searches are
left; the signal stops at `reserve`. A query is reported once, and remembered for SEEN_DAYS.
Each is cut to its core for the lead ("higgsfield hotel lobby ai" -> "hotel lobby"), so a
trend found here and among new domains is one lead; the query itself is kept as its variant.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from . import UA, snap
from .i18n import t

URL = "https://serpapi.com/search.json"
ACCOUNT = "https://serpapi.com/account.json"
TIMEOUT = 120
SEEN_DAYS = 60
# Words around a trend's name in a search, and words that are a search's grammar, not its subject.
FILLER = set("""ai video videos generator free trend trends tiktok app online filter effect effects template templates
prompt prompts maker make how to the a an with in on of for is what""".split())


class SerpError(RuntimeError):
    pass


def key() -> str:
    return os.environ.get("SERPAPI_API_KEY", "").strip()


def _get(url: str, params: dict) -> dict:
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode({**params, "api_key": key()}), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            data = json.load(res)
    except urllib.error.HTTPError as exc:
        try:
            why = json.loads(exc.read().decode("utf-8", "replace")).get("error", "")
        except ValueError:
            why = ""
        raise SerpError(f"HTTP {exc.code}: {why}"[:160]) from exc
    except (OSError, ValueError) as exc:
        raise SerpError(f"{type(exc).__name__}: {exc}"[:160]) from exc
    if data.get("error") and not data.get("related_queries"):
        raise SerpError(str(data["error"])[:160])
    return data


def left() -> int | None:
    """Searches left this month; free to ask. None when the account cannot be read."""
    try:
        return int(_get(ACCOUNT, {}).get("total_searches_left"))
    except (SerpError, TypeError, ValueError):
        return None


def related(seed: str, window: str, geo: str = "") -> list[dict]:
    """The rising related queries of one seed: [{"query", "value", "rise"}]; rise is a percent,
    or None for a Breakout."""
    params = {"engine": "google_trends", "data_type": "RELATED_QUERIES", "q": seed, "date": window, "tz": "0", "hl": "en"}
    if geo:
        params["geo"] = geo
    rising = (_get(URL, params).get("related_queries") or {}).get("rising") or []
    return [{"query": " ".join(str(x.get("query", "")).lower().split()), "value": x.get("value", ""),
             "rise": None if str(x.get("value", "")).lower() == "breakout" else int(x.get("extracted_value") or 0)}
            for x in rising if x.get("query")]


def core(query: str, seed: str) -> str:
    """The subject of a search, without the seed and the words around a trend's name:
    "higgsfield hotel lobby ai" -> "hotel lobby"."""
    drop = FILLER | set(seed.lower().split())
    words = [w for w in query.lower().split() if w not in drop]
    return " ".join(words)


def rising(cfg: dict, state: Path, today: date | None = None) -> dict:
    c = cfg["rising"]
    if not c["seeds"]:
        return {"skipped": True}
    if not key():
        return {"error": t("rising_nokey"), "terms": []}
    today = today or date.today()
    remaining = left()
    if remaining is not None and remaining <= c["reserve"]:
        return {"error": t("rising_spent", left=remaining, reserve=c["reserve"]), "left": remaining, "terms": []}
    seeds = c["seeds"] if remaining is None else c["seeds"][:remaining - c["reserve"]]
    path = state / "rising.json.gz"
    seen: dict[str, str] = snap.load(path) or {}
    rows: dict[str, dict] = {}
    errors, read, queries = [], 0, 0
    for seed in seeds:
        try:
            found = related(seed, c["window"], c["geo"])
        except SerpError as exc:
            errors.append(f"{seed}: {exc}")
            continue
        read += 1
        for x in found:
            if x["rise"] is not None and x["rise"] < c["min_rise"]:
                continue
            queries += 1
            term = core(x["query"], seed)
            if x["query"] in seen or len(term) < 3:
                continue
            seen[x["query"]] = today.isoformat()
            value = t("rising_breakout") if x["rise"] is None else f"+{x['rise']:,}%"
            row = rows.setdefault(term, {"term": term, "examples": [], "variants": [term], "seeds": [], "note": ""})
            row["examples"].append(x["query"])
            row["variants"].append(x["query"])
            row["seeds"].append(seed)
            if not row["note"]:
                row["note"] = t("note_rising", query=x["query"], seed=seed, value=value)
    if read:   # a run that read nothing keeps what was seen
        cutoff = (today - timedelta(days=SEEN_DAYS)).isoformat()
        snap.save(path, {q: d for q, d in seen.items() if d >= cutoff})
    out = {"seeds": len(seeds), "read": read, "queries": queries, "left": None if remaining is None else remaining - read,
           "terms": [dict(r, variants=list(dict.fromkeys(r["variants"])), recent=len(set(r["seeds"]))) for r in rows.values()]}
    if errors:
        out["errors"] = errors
        if not read:
            out["error"] = "; ".join(errors[:2])
    return out
