"""Signal ③ domains: words people register domains for, by the dozen.

When a clip turns into an AI trend ("hotel lobby", "bulin 47"), people register its name in
every form within days: bulin47.io, bulin47ai.link, bulin-47-video.com. WhoisDS publishes
each day's newly registered domains for free (about 70,000 a day, a share of all
registrations, enough to see a wave of a dozen). This signal reads each new day's list once,
cuts every domain to its core (the name without ai, video, viral... and without the TLD), and
reports a core that the last `window_days` of lists hold in numbers its own past does not.

The rules, set against the domains registered for 13 AI trends of September and October 2026
(hotel lobby, bulin 47, burning bridges, rumpelstiltskin and others):
- a core counts its distinct domains over the window: a wave runs over several days;
- it needs `min_domains` of them, or `min_domains_ai` when one carries an intent word (ai,
  video) around the name or ends in .ai. The intent word is read from what was cut off, not
  found inside the name: "raindance" holds the letters "ai" and is not an AI domain;
- the count must be `min_lift` times what the core's own history predicts for a window, so an
  everyday word ("zombie", "casino") needs a burst and a new one needs nothing;
- a variant is merged into a new core it contains ("hotellobbyfilter", "drakeburningbridges"),
  never into an everyday one ("zombielovestory" stays apart from "zombie"); a spelling one
  letter off ("rumplestiltskin") is merged too;
- a core is reported once; it is remembered for `history_days`.

The lists are kept per day in the state directory (the cores and their domains, gzip JSON,
a few hundred KB a day), which is what the history is read from. WhoisDS keeps only the last
four days online, so the history starts the day the radar first runs.

A list is not of the day it is named after. Sampled in October 2026, the list of the 14th
held .com domains registered on the 12th, and the list of Tuesday the 13th those of the
weekend before, the 10th and 11th. So each list's days are measured, not assumed: SAMPLE of
its .com domains are looked up at Verisign's RDAP (free) when it is read, and a wave is
labelled with the registration days of the lists it is in.
"""
from __future__ import annotations

import base64
import io
import re
import urllib.request
import zipfile
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from . import UA, snap
from .i18n import t

INDEX = "https://www.whoisds.com/newly-registered-domains"
_LINK = re.compile(r"newly-registered-domains/([A-Za-z0-9+/]+=*)/nrd")
TIMEOUT = 180
EXAMPLES = 6
RDAP = "https://rdap.verisign.com/com/v1/domain/"
SAMPLE = 8
RECENT_DAYS = 10    # a sampled domain registered longer ago than this was re-registered, not new
INTENT = {"ai", "ia", "video", "videos", "aivideo", "videoai"}
# Cut off around the name, as a word between hyphens or glued to either end. "ia" (Spanish
# for AI) only between hyphens: glued, it is the end of media, india, academia.
GLUED_INTENT = INTENT - {"ia"}
SUFFIXES = sorted(GLUED_INTENT | {"viral", "trend", "trends", "generator", "maker", "free", "online", "app", "official"}, key=len, reverse=True)
PREFIXES = sorted(GLUED_INTENT | {"try", "get", "make", "the"}, key=len, reverse=True)
WORDS = set(SUFFIXES) | set(PREFIXES) | INTENT | {"my"}


def cut(domain: str, min_len: int = 5) -> tuple[str, bool, str | None]:
    """(core, intent, words) of a domain: "burning-bridges-ai-video.com" -> ("burningbridges",
    True, "burning bridges"). `words` is the name as written with hyphens, when it was."""
    parts = domain.lower().strip().split(".")
    intent = parts[-1] == "ai" and len(parts) > 1
    tokens = [w for w in parts[0].split("-") if w]
    kept = [w for w in tokens if w not in WORDS]
    intent |= any(w in INTENT for w in tokens if w not in kept)
    name = "".join(kept)
    glued = True
    while glued:
        glued = False
        for a in PREFIXES:
            if name.startswith(a) and len(name) - len(a) >= min_len:
                name, glued, intent = name[len(a):], True, intent or a in INTENT
        for a in SUFFIXES:
            if name.endswith(a) and len(name) - len(a) >= min_len:
                name, glued, intent = name[:-len(a)], True, intent or a in INTENT
    words = " ".join(kept) if len(kept) > 1 and "".join(kept) == name else None
    return name, intent, words


def _near(a: str, b: str) -> bool:
    """One letter added, dropped, changed, or two neighbours swapped."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def group(domains: list[str], min_len: int = 5) -> dict[str, list[str]]:
    """{core: [domains]} for one day's list; cores shorter than min_len or all digits are left out."""
    out: dict[str, list[str]] = {}
    for d in domains:
        d = d.strip().lower()
        if not d:
            continue
        core = cut(d, min_len)[0]
        if len(core) >= min_len and not core.isdigit():
            out.setdefault(core, []).append(d)
    return out


def find(window: list[dict[str, list[str]]], history: list[dict[str, list[str]]], c: dict,
         reported: set[str] = frozenset()) -> list[dict]:
    """The cores the window's lists hold in numbers their history does not. `window` and
    `history` are per-day {core: [domains]}; `reported` cores are not reported again."""
    w, h = max(len(window), 1), len(history)
    seen: dict[str, set[str]] = {}
    for day in window:
        for core, ds in day.items():
            seen.setdefault(core, set()).update(ds)
    past = Counter()
    for day in history:
        for core, ds in day.items():
            past[core] += len(ds)
    expect = (lambda core: past[core] * w / h) if h else (lambda core: 0.0)
    # A core qualifies on its own domains, compared with its own past. Variants are added after
    # that, to show: counted in, "worldsbykai" would make "world" look like a wave.
    picked: dict[str, dict] = {}
    for core, ds in seen.items():
        if core in reported:
            continue
        intent = sum(1 for d in ds if cut(d, c["min_len"])[1])
        n = len(ds)
        if not (n >= c["min_domains"] or (n >= c["min_domains_ai"] and intent)):
            continue
        lift = round(n / (expect(core) + 1), 1)
        if lift >= c["min_lift"]:
            picked[core] = {"lift": lift}
    home: dict[str, str] = {}
    for k in seen:
        if k in picked:
            continue
        # A variant is the name with a word before or after it: look at its ends, not every substring.
        ends = {k[:i] for i in range(c["min_len"], len(k))} | {k[-i:] for i in range(c["min_len"], len(k))}
        inside = ends & picked.keys()
        if inside:
            home[k] = max(inside, key=len)
    by_start: dict[str, list[str]] = {}
    for k in seen:
        by_start.setdefault(k[:1], []).append(k)
    for b in picked:
        if len(b) >= 8:
            for k in by_start.get(b[:1], []):
                if k not in home and k not in picked and _near(k, b):
                    home[k] = b
    extra: dict[str, set[str]] = {}
    for k, b in home.items():
        extra.setdefault(b, set()).update(seen[k])
    rows = []
    for core, p in picked.items():
        own = seen[core]
        more = extra.get(core, set()) - own
        # An everyday word has hundreds of longer names around it ("world": worldsbykai...): not its variants.
        ds = own | more if len(more) <= 2 * len(own) else own
        cuts = {d: cut(d, c["min_len"]) for d in ds}
        written = Counter(x[2] for d, x in cuts.items() if x[2] and x[0] == core)
        term = written.most_common(1)[0][0] if written else core
        first = next((i for i, day in enumerate(window) if core in day), 0)
        rows.append({"term": term, "core": core, "recent": len(own), "lift": p["lift"], "domains": len(ds),
                     "tlds": len({d.rsplit(".", 1)[-1] for d in ds}), "intent": sum(1 for x in cuts.values() if x[1]),
                     "first": first, "examples": sorted(ds, key=lambda d: (not cuts[d][1], len(d), d))[:EXAMPLES],
                     "variants": list(dict.fromkeys([term, f"{term} ai"]))})
    # A wave with no ai or video in any of its names is mostly a betting brand bought in bulk: after the rest.
    rows.sort(key=lambda r: (-bool(r["intent"]), -r["lift"], -r["domains"], r["core"]))
    return rows[:c["max_terms"]]


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return res.read()


def available() -> dict[str, str]:
    """{day: download url} of the lists WhoisDS has online (the last four days)."""
    html = _get(INDEX).decode("utf-8", "replace")
    out = {}
    for b64 in dict.fromkeys(_LINK.findall(html)):
        try:
            name = base64.b64decode(b64).decode()
        except ValueError:
            continue
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.zip", name)
        if m:
            out[m.group(1)] = f"https://www.whoisds.com//whois-database/newly-registered-domains/{b64}/nrd"
    return out


def download(url: str) -> list[str]:
    """One day's list. The server takes about a minute for its 600 KB and now and then drops
    the connection, so a failed download is tried once more."""
    for attempt in range(2):
        try:
            data = _get(url)
            break
        except OSError:
            if attempt:
                raise
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = next(n for n in z.namelist() if n.endswith(".txt"))
        return z.read(name).decode("utf-8", "replace").split()


def registered(domain: str) -> str | None:
    """The day a .com domain was registered, from Verisign's RDAP."""
    try:
        data = json.loads(_get(RDAP + domain))
    except (OSError, ValueError):
        return None
    return next((e["eventDate"][:10] for e in data.get("events", []) if e.get("eventAction") == "registration"), None)


def days_of(day: str, domains: list[str]) -> list[str]:
    """The registration days a list holds, measured on a sample of its .com domains."""
    coms = sorted(d for d in domains if d.endswith(".com"))
    sample = random.Random(day).sample(coms, min(SAMPLE, len(coms)))
    floor = (date.fromisoformat(day) - timedelta(days=RECENT_DAYS)).isoformat()
    found = Counter(r for r in map(registered, sample) if r and r >= floor)
    # the days that hold a real share of the sample, not one stray domain
    return sorted(d for d, n in found.items() if n >= max(2, len(sample) // 4)) or sorted(found)[:1]


def span(days: list[str]) -> str:
    """"10-14" or "10-10~10-11"."""
    return days[0][5:] if days[0] == days[-1] else f"{days[0][5:]}~{days[-1][5:]}"


def diff(cfg: dict, state: Path, today: date | None = None) -> dict:
    """Reads the lists not read yet, keeps them per day, and reports the cores of the window."""
    c = cfg["domains"]
    today = today or date.today()
    folder = state / "domains"
    kept = {p.name[:10]: p for p in folder.glob("????-??-??.json.gz")} if folder.exists() else {}
    first_run = not kept
    errors, read = [], []
    mpath = folder / "registered.json.gz"
    measured: dict[str, list[str]] = snap.load(mpath) or {}
    try:
        online = available()
    except Exception as exc:  # noqa: BLE001 — the history on disk still makes a report
        online = {}
        errors.append(f"{type(exc).__name__}: {str(exc)[:120]}")
    for day, url in sorted(online.items()):
        if day in kept:
            continue
        try:
            listed = download(url)
            snap.save(folder / f"{day}.json.gz", group(listed, c["min_len"]))
        except Exception as exc:  # noqa: BLE001 — that day is tried again next run
            errors.append(f"{day}: {type(exc).__name__}: {str(exc)[:100]}")
            continue
        kept[day] = folder / f"{day}.json.gz"
        read.append(day)
        measured[day] = days_of(day, listed)
    if not kept:
        return {"error": "; ".join(errors) or t("domains_none_online"), "terms": []}
    cutoff = (today - timedelta(days=c["history_days"] + c["window_days"])).isoformat()
    for day in [d for d in kept if d < cutoff]:
        kept.pop(day).unlink(missing_ok=True)
    days = sorted(kept)
    win_days, past_days = days[-c["window_days"]:], days[:-c["window_days"]]
    rpath = folder / "reported.json.gz"
    reported = {k: d for k, d in (snap.load(rpath) or {}).items() if d >= (today - timedelta(days=c["history_days"])).isoformat()}
    rows = find([snap.load(kept[d]) for d in win_days], [snap.load(kept[d]) for d in past_days], c, set(reported))
    for r in rows:
        r["first_day"] = win_days[r.pop("first")]
        regs = sorted({d for day in win_days[win_days.index(r["first_day"]):] for d in measured.get(day, [])})
        r["registered"] = span(regs) if regs else ""
        r["note"] = t("note_domain", n=r["domains"], tlds=r["tlds"], day=r["registered"]) if regs else \
            t("note_domain_list", n=r["domains"], tlds=r["tlds"], day=r["first_day"][5:])
        reported[r["core"]] = today.isoformat()
    snap.save(rpath, reported)
    snap.save(mpath, {d: v for d, v in measured.items() if d in kept})
    out = {"read": read, "window": win_days, "history_days": len(past_days), "first_run": first_run, "terms": rows,
           "registered": {d: measured.get(d, []) for d in win_days}}
    if errors:
        out["errors"] = errors
    return out
