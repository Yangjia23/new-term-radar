"""How many of a name's domains are taken, and since when: the need, measured.

A clip that turns into an AI trend has its name registered in every form within days. Read at
the registries' RDAP (free, no key) on 24 October 2026, "dime dime baby":
dimedimebaby.com, .app and dimedimebabyai.com on 19 October, .org, ai.app and ai.org on the
20th, dimedimebabyvideo.com on the 21st; "bulin 47" all nine forms from 9 to 11 October.
The .com and the ai.com go first, the video forms a day to four later.

So each name about to be pushed is looked up in nine forms: the name, the name with "ai", the
name with "video", each in .com, .app and .org. A form registered in the last `recent` days
counts as taken for this trend; one registered years ago ("windowpeeper.com" might be) does not.
The name must be the one people search ("dime dime baby"), not what was said around it
("baby wow karol g"): see radar/core.py.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from . import UA

TIMEOUT = 15
WORKERS = 9
RDAP = {"com": "https://rdap.verisign.com/com/v1/domain/",
        "app": "https://pubapi.registry.google/rdap/domain/",
        "org": "https://rdap.publicinterestregistry.org/rdap/domain/"}
FORMS = ("{}", "{}ai", "{}video")


def spellings(name: str) -> list[str]:
    """The nine domains of a name: "dime dime baby" -> dimedimebaby.com ... dimedimebabyvideo.org."""
    core = "".join(ch for ch in name.lower() if ch.isascii() and ch.isalnum())
    return [f"{form.format(core)}.{tld}" for form in FORMS for tld in RDAP] if core else []


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rdap+json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return res.read()


def registered(domain: str) -> str | None:
    """The day a domain was registered; "" when it is free; None when the registry did not answer."""
    try:
        data = json.loads(_get(RDAP[domain.rsplit(".", 1)[1]] + domain))
    except urllib.error.HTTPError as exc:
        return "" if exc.code == 404 else None
    except (OSError, ValueError):
        return None
    return next((e["eventDate"][:10] for e in data.get("events", []) if e.get("eventAction") == "registration"), None)


def check(names: list[str], recent: int, today: date | None = None) -> dict[str, dict]:
    """{name: {"taken", "checked", "first", "domains"}}: of its nine domains, how many were registered
    in the last `recent` days, how many the registries answered for, the first of those days, and
    those domains, earliest first."""
    today = today or date.today()
    floor = (today - timedelta(days=recent)).isoformat()
    todo = {n: spellings(n) for n in dict.fromkeys(names)}
    hosts = sorted({h for hs in todo.values() for h in hs})
    with ThreadPoolExecutor(WORKERS) as pool:
        days = dict(zip(hosts, pool.map(registered, hosts)))
    out = {}
    for name, hs in todo.items():
        answered = [days[h] for h in hs if days[h] is not None]
        new = sorted((days[h], h) for h in hs if days[h] and days[h] >= floor)
        out[name] = {"taken": len(new), "checked": len(answered), "first": new[0][0] if new else None,
                     "domains": [h for _, h in new]}
    return out
