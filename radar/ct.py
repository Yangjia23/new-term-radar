"""Certificate Transparency: how many sites for a word are already live, and since when.

Not a signal. For each name about to be pushed, a few of its domains are looked up in the CT
logs through SSLMate's Cert Spotter (free, no key, about ten lookups at a time): a site that
got an HTTPS certificate is live or about to be. For a wave of new domains those are its own
domains; for a hashtag or a search, the usual spellings ("hotellobbyai.com", "hotellobby.ai").
"hotellobbyai.com" had its first certificate on 24 September 2026, four days before the trend
reached the newsletters: the date says how long others have been building for a word.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from . import UA

URL = "https://api.certspotter.com/v1/issuances"
TIMEOUT = 30
SPELLINGS = ("{}ai.com", "{}.ai", "{}.com")


def hosts(row: dict, per_name: int) -> list[str]:
    """The domains to look up for a lead: its own new domains first, else the usual spellings."""
    own = [e for e in row.get("examples", []) if "." in e and " " not in e and not e.startswith("#")]
    own.sort(key=lambda d: (not d.endswith((".com", ".ai")), len(d)))
    core = row["term"].replace(" ", "").replace("-", "")
    return list(dict.fromkeys(own + [s.format(core) for s in SPELLINGS]))[:per_name]


def issued(host: str) -> list[str]:
    """The days certificates were issued for a host and its subdomains, earliest first."""
    query = urllib.parse.urlencode({"domain": host, "include_subdomains": "true"})
    req = urllib.request.Request(f"{URL}?{query}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return sorted(x["not_before"][:10] for x in json.load(res) if x.get("not_before"))


def check(rows: list[dict], c: dict) -> dict:
    """{term: {"live", "checked", "first"}} for as many leads as the lookups allow, in order."""
    out, used, errors = {}, 0, []
    for r in rows:
        todo = hosts(r, c["per_name"])
        if used + len(todo) > c["max_lookups"]:
            break
        live, first = 0, None
        for h in todo:
            used += 1
            try:
                days = issued(h)
            except urllib.error.HTTPError as exc:
                errors.append(f"{h}: HTTP {exc.code}")
                if exc.code == 429:          # the free allowance is spent: stop, the next run tries again
                    return {"names": out, "lookups": used, "errors": errors}
                continue
            except (OSError, ValueError) as exc:
                errors.append(f"{h}: {type(exc).__name__}")
                continue
            if days:
                live += 1
                first = min(first or days[0], days[0])
        out[r["term"]] = {"live": live, "checked": len(todo), "first": first}
    res = {"names": out, "lookups": used}
    if errors:
        res["errors"] = errors
    return res
