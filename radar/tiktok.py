"""Signal ① tiktok: hashtags new to TikTok's trending top 100, where a clip turns into a trend.

TikTok's Creative Center ranks the hashtags rising in a country over the last 7 days (read
through AIsa, TikHub behind it, $0.001 a page of 50). The AI remakes of a trend show there
as their own tags: in the US top 50 for 9-16 October 2026 sat bulin47, bulin47freestyle,
bulin47challenge and burningbridgesai. A hashtag is reported the run it enters the top
`pages` x 50 for the first time; the first run only keeps what is there.

A hashtag is one word; it is cut to its core like a domain ("burningbridgesai" ->
"burningbridges"), so the lead joins the same trend found among new domains or searches.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from . import aisa, snap
from .domains import cut
from .i18n import t

TOOL = "post_tikhub_tiktok_ads_get_trends_hashtag_list"
PAGE = 50
SEEN_DAYS = 60
# Words a trend's own tag carries after its name: #bulin47challenge, #hotellobbytrend.
TAILS = ("challenge", "edits", "edit")


def core(tag: str) -> str:
    tag = tag.lower().lstrip("#")
    for tail in TAILS:
        if tag.endswith(tail) and len(tag) - len(tail) >= 5:
            tag = tag[:-len(tail)]
            break
    return cut(tag + ".x")[0]


def hashtags(country: str, pages: int, days: int) -> tuple[list[dict], int]:
    """The trending hashtags of one country, best first: [{"tag", "posts", "rank"}], and the cost."""
    calls = [{"call_id": f"p{p}", "tool": TOOL, "arguments": {"body": {
        "country_code": country, "time_range": days, "page": p, "limit": PAGE}}} for p in range(1, pages + 1)]
    data, cost = aisa.call(calls)
    out = []
    for p in range(1, pages + 1):
        items = (((data.get(f"p{p}") or {}).get("data") or {}).get("items")) or []
        out += [{"tag": it["hashtagName"].lower(), "posts": int(it.get("publishCnt") or 0), "rank": (p - 1) * PAGE + i + 1}
                for i, it in enumerate(items) if it.get("hashtagName")]
    if not out:
        raise aisa.AisaError(f"no hashtags for {country}")
    return out, cost


def trending(cfg: dict, state: Path, today: date | None = None) -> dict:
    c = cfg["tiktok"]
    if not c["countries"]:
        return {"skipped": True}
    today = today or date.today()
    path = state / "tiktok.json.gz"
    stored = snap.load(path)
    first_run = stored is None
    seen: dict[str, str] = stored or {}
    rows: dict[str, dict] = {}
    entered: list[dict] = []     # every tag new to the chart, the ones too short to name anything too
    cost, read, errors = 0, 0, []
    for country in c["countries"]:
        try:
            tags, spent = hashtags(country, c["pages"], c["days"])
        except aisa.AisaError as exc:
            errors.append(f"{country}: {exc}")
            continue
        cost += spent
        read += len(tags)
        for h in tags:
            key = f"{country}:{h['tag']}"
            new = key not in seen
            seen[key] = today.isoformat()
            term = core(h["tag"])
            if first_run or not new:
                continue
            entered.append({"tag": h["tag"], "rank": h["rank"], "posts": h["posts"], "country": country, "term": term})
            if len(term) < 4:
                continue
            row = rows.setdefault(term, {"term": term, "examples": [], "variants": [term, f"{term} ai"], "recent": 0,
                                         "note": t("note_tiktok", tag=h["tag"], rank=h["rank"], country=country, posts=f"{h['posts']:,}")})
            row["examples"].append(f"#{h['tag']}")
            row["recent"] += 1
    if read:
        cutoff = (today - timedelta(days=SEEN_DAYS)).isoformat()
        snap.save(path, {k: d for k, d in seen.items() if d >= cutoff})
    out = {"countries": len(c["countries"]), "read": read, "first_run": first_run, "cost_micros": cost, "terms": list(rows.values()),
           "entered": entered}
    if errors:
        out["errors"] = errors
        if not read:
            out["error"] = "; ".join(errors[:2])
    return out


def chart(cfg: dict, state: Path) -> dict:
    """The whole chart as it stands, each tag with its core, whether the radar has seen it, and the
    judge's score for every core: to check what the filter keeps and drops. Leaves the snapshot alone."""
    from . import judge   # the judge imports the network client; keep it out of the signal's import
    c = cfg["tiktok"]
    seen = snap.load(state / "tiktok.json.gz") or {}
    tags, cost = [], 0
    for country in c["countries"]:
        got, spent = hashtags(country, c["pages"], c["days"])
        cost += spent
        tags += [{**h, "country": country, "term": core(h["tag"]), "seen": seen.get(f"{country}:{h['tag']}")} for h in got]
    rows = [{"term": term, "examples": [f"#{h['tag']}" for h in tags if h["term"] == term][:3]}
            for term in dict.fromkeys(h["term"] for h in tags)]
    judged = judge.score(rows, cfg["judge"]["model"], cfg["judge"].get("focus", "names"))
    scores = {r["term"]: r.get("named") for r in rows}
    for h in tags:
        h["score"] = scores.get(h["term"])
    return {"tags": tags, "judge": judged, "min_score": cfg["judge"]["min_score"], "cost_micros": cost}
