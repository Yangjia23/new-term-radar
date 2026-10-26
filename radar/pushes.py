"""What goes to Feishu: each trend once, under its own name, again only when it grows.

Up to 23 October 2026 a push was a term as the signals caught it: some 30 to 40 a day, one in
three a trend worth a page. The rest were the same trend under other names ("toc toc", "toc toc
dance", "my door toc toc", "toc trend toc toc"), categories and holidays ("halloween costume",
"amapiano"), trends already over, and the same name twice with nothing to tell the two apart
("window peeper" on the 21st and again on the 23rd). Now:

1. Each term is read for the trend it points to (radar/core.py): "baby wow karol g" is
   "dime dime baby". Terms with one name are one card. A name the model takes for a category
   or a holiday ("halloween costume") is pushed like any other when the data says so, and the
   card says what the model thought: the model names, the data decides.
2. A trend is pushed on data, not on a score: AI versions on TikTok (the watch list's own
   rule, `watch.tiktok_authors` accounts and `watch.tiktok_plays` plays), a wave of new
   domains, a new page on a hand-picked list of trends (a "curated" site in "pages":
   tryatrend), or `min_taken` of the name's nine domains registered in the last `recent_days`
   (radar/taken.py). Of the trends pushed 16 to 23 October, 18 of 29 had two or more of the
   nine taken, and 4 of 35 of the noise did. A name whose first domain is older than
   `old_days`, or whose Trends curve is already fading, is over and not pushed.
3. A ledger of what was pushed (state/pushed.json.gz) holds each trend's names and its numbers
   then. A trend in it is pushed again only when it grew: plays `grow_plays` times, accounts
   `grow_authors` times, or `grow_taken` more domains taken. The card says which: 🆕 or 📈.
"""
from __future__ import annotations

import os
import re
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

from . import core, covered, i18n, report, snap, store, taken
from .i18n import t

LEDGER = "pushed.json.gz"
# Words that do not tell one trend from another: "toc toc dance" and "toc trend toc toc" are "toc toc".
FILLER = {"trend", "trends", "tiktok", "capcut", "plantilla", "template", "templates", "filter", "tutorial", "viral",
          "original", "dance", "edit", "edits", "ai", "ia", "video", "videos", "guide", "learn", "effect", "challenge", "meme"}


def words(name: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in FILLER]


def same(a: str, b: str) -> bool:
    """One trend under two names: "toc toc" and "my door toc toc", "hittheroad" and "hit the road
    dude", "window peeper" and "learn this window peeper". The shorter must stand in the longer
    as it is: "anime eye" is not "anime star eye". A single short word does not hold a longer
    name ("zombie" is not "zombie couple")."""
    wa, wb = words(a), words(b)
    fa, fb = "".join(wa), "".join(wb)
    if not fa or not fb:
        return False
    if fa == fb:
        return True
    short, long_ = (wa, wb) if len(fa) <= len(fb) else (wb, wa)
    fs = "".join(short)
    if len(short) < 2 and len(fs) < 8:
        return False
    return fs in "".join(long_)


def _find(ledger: dict[str, dict], names: list[str]) -> str | None:
    return next((k for k, e in ledger.items() if any(same(n, a) for n in names for a in e["names"])), None)


def _seed(state: Path, kinds: set[str], today: date) -> dict[str, dict]:
    """The first ledger: what the radar pushed before it kept one, from its leads database (this
    run's own leads are already recorded there, and are not pushed yet)."""
    out: dict[str, dict] = {}
    try:
        rows = store.connect(state).execute("SELECT term, first_seen, signals FROM leads WHERE coalesce(named, 1) >= 0.4 "
                                            "AND first_seen < ?", (today.isoformat(),)).fetchall()
    except Exception:  # noqa: BLE001 — no database yet: an empty ledger
        return out
    for term, first, signals in rows:
        if kinds & set(re.findall(r'"(\w+)"', signals)) and not _find(out, [term]):
            out[term] = {"names": [term], "first": first, "last": first, "authors": None, "plays": None, "taken": None}
    return out


def _group(rows: list[dict], names: dict[str, dict]) -> list[dict]:
    """The rows of one trend merged into one: its name, its terms, the best numbers among them."""
    out: list[dict] = []
    for r in rows:
        got = names.get(r["term"]) or {"name": r["term"], "generic": False}
        name = got["name"]
        g = next((g for g in out if same(g["name"], name)), None)
        if g is None:
            g = {"name": name, "terms": [], "kinds": set(), "tiktok": None, "curve": {}, "format": r.get("format", "text"),
                 "generic": True, "curated": None}
            out.append(g)
        g["generic"] = g["generic"] and got["generic"]      # one term read as a trend is enough
        g["terms"].append(r["term"])
        g["kinds"] |= set(r["kinds"])
        tk = r.get("tiktok")
        if tk and (not g["tiktok"] or tk["plays"] > g["tiktok"]["plays"]):
            g["tiktok"] = tk
        g["curve"] = g["curve"] or r.get("curve") or {}
        g["curated"] = g["curated"] or r.get("curated")
    return out


def select(cfg: dict, state: Path, lead: list[dict], today: date | None = None) -> tuple[list[dict], dict]:
    """The trends to push now, each {"name", "terms", "status": "new"|"up", "tiktok", "taken",
    "before"}; and what was held back, by reason."""
    today = today or date.today()
    c = cfg["push"]
    kinds = set(cfg["feishu"]["kinds"])
    rows = [r for r in report.named(cfg, lead) if (kinds & set(r["kinds"]) or r.get("curated")) and not r["known"]]
    held: dict[str, list[str]] = {"no_data": [], "over": [], "pushed": []}
    if not rows:
        return [], held
    path = state / LEDGER
    ledger: dict[str, dict] = snap.load(path) or _seed(state, kinds, today)
    recent = (today - timedelta(days=c["old_days"])).isoformat()
    names = core.names(rows, cfg["judge"]["model"], [k for k, e in ledger.items() if e["last"] >= recent])
    groups = _group(rows, names)
    for g in groups:            # a trend pushed before keeps the name it was pushed under
        g["key"] = _find(ledger, [g["name"], *g["terms"]])
        if g["key"] and g["key"] != g["name"]:
            g["terms"] = list(dict.fromkeys([g["name"], *g["terms"]]))
            g["name"] = g["key"]
    try:
        found = taken.check([g["name"] for g in groups], c["recent_days"], today)
    except Exception:  # noqa: BLE001 — without the registries the other data decides
        found = {}
    old = (today - timedelta(days=c["old_days"])).isoformat()
    out = []
    for g in groups:
        g["taken"] = found.get(g["name"]) or {"taken": 0, "checked": 0, "first": None}
        tk = g["tiktok"] or {}
        if not (tk or "domain" in g["kinds"] or g["curated"] or g["taken"]["taken"] >= c["min_taken"]):
            held["no_data"].append(g["name"])
            continue
        first = g["taken"]["first"]
        if (first and first < old) or g["curve"].get("now") == "fading":
            held["over"].append(g["name"])
            continue
        now = {"authors": tk.get("authors", 0), "plays": tk.get("plays", 0), "taken": g["taken"]["taken"]}
        key = g.pop("key")
        if key is None:
            ledger[g["name"]] = {"names": [g["name"], *g["terms"]], "first": today.isoformat(), "last": today.isoformat(), **now}
            out.append({**g, "status": "new"})
            continue
        e = ledger[key]
        before = dict(e)
        e["names"] = list(dict.fromkeys(e["names"] + [g["name"], *g["terms"]]))
        # a number never measured before (a ledger seeded from the database) is kept, not compared
        grew = (bool(e["plays"]) and now["plays"] >= e["plays"] * c["grow_plays"]) \
            or (bool(e["authors"]) and now["authors"] >= e["authors"] * c["grow_authors"]) \
            or (e["taken"] is not None and now["taken"] >= e["taken"] + c["grow_taken"])
        if grew:
            out.append({**g, "status": "up", "before": before})
        else:
            held["pushed"].append(g["name"])
        for k, v in now.items():
            e[k] = max(e[k] or 0, v)
        e["last"] = today.isoformat() if grew else e["last"]
    snap.save(path, ledger)
    out.sort(key=lambda g: (g["status"] != "new", -(g["tiktok"] or {}).get("plays", 0), -g["taken"]["taken"]))
    return out, held


def _plays(n: int) -> str:
    if i18n.lang() == "zh":
        return (f"{n / 10000:.0f}万" if n >= 100000 else f"{n / 10000:.1f}万") if n >= 10000 else f"{n:,}"
    return f"{n / 1000:.0f}k" if n >= 1000 else str(n)


def card(g: dict, pages: dict[str, str]) -> list[str]:
    """Two lines: the name and its tags; then the numbers, nothing else."""
    q = urllib.parse.quote(f"{g['name']} ai")
    tags = [t("fs2_new") if g["status"] == "new" else t("fs2_up")]
    if g["format"] in ("video", "image", "voice"):
        tags.append(t("fs2_" + g["format"]))
    if g.get("generic"):
        tags.append(t("fs2_generic"))
    if g["curve"].get("now") in ("rising", "spike"):
        tags.append(t("fs2_rising"))
    head = f"**[{g['name']}](https://www.tiktok.com/search/video?q={q})**  " + " ".join(tags)
    tk, tn = g["tiktok"] or {}, g["taken"]
    parts = []
    if g["status"] == "up":
        b = g["before"]
        parts.append(t("fs2_first", day=b["first"][5:].replace("-", "/")))
        if tk and b.get("authors"):
            parts.append(t("fs2_authors_up", a=b["authors"], b=tk["authors"]))
        if tk and b.get("plays"):
            parts.append(t("fs2_plays_up", a=_plays(b["plays"]), b=_plays(tk["plays"])))
    elif tk:
        if tk.get("since"):
            parts.append(t("fs2_since", day=tk["since"][5:].replace("-", "/")))
        parts.append(t("fs2_ai", authors=tk["authors"], plays=_plays(tk["plays"])))
    if tn["checked"]:
        # which ones: on 26 October "domains 1/9 taken" for "free ai rap" was the one site the lead came from
        parts.append(t("fs2_taken", n=tn["taken"], of=tn["checked"]) + (t("fs2_taken_since", day=tn["first"][5:].replace("-", "/")) if tn["first"] else "")
                     + (t("fs2_taken_which", domains=", ".join(tn.get("domains", [])[:3])) if tn.get("domains") else ""))
    if g.get("curated"):
        parts.append(t("fs2_curated", site=g["curated"]))
    if g["name"] in pages:
        parts.append(t("fs2_dreamina", url=pages[g["name"]]))
    others = [x for x in g["terms"] if x != g["name"]]
    if others:
        parts.append(t("fs2_from", terms=" / ".join(others[:2])))
    return [head, " · ".join(parts)]


def push(cfg: dict, state: Path, lead: list[dict], b: dict[str, dict], today: date | None = None) -> tuple[str, str] | None:
    """The Feishu message: (title, Markdown), or None when there is nothing to push and nothing failed."""
    # every source that failed, not only the pushed kinds: TikTok's searches and template hashtags feed the
    # watch list, and on 25 October both failed with no word in Feishu
    errors = [f"{t('kind_' + k)}: {v['error']}" for k, v in b.items() if v.get("error")]
    chosen, _ = select(cfg, state, lead, today)
    if not chosen and not errors:
        return None
    try:
        pages = covered.dreamina(state, [g["name"] for g in chosen]) if chosen else {}
    except Exception:  # noqa: BLE001 — the card goes without it
        pages = {}
    lines: list[str] = []
    for g in chosen:
        lines += ([""] if lines else []) + card(g, pages)
    if errors:
        lines += ["", t("fs_err", why="; ".join(errors))]
    run = os.environ.get("GITHUB_RUN_ID")
    if run:
        url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{run}"
        lines += ["", t("fs_link", url=url)]
    new = sum(g["status"] == "new" for g in chosen)
    title = t("fs2_title", new=new, up=len(chosen) - new) if chosen else t("fs_alert")
    return title, "\n".join(lines)
