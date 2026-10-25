"""The name people search for a trend, read out of what the radar caught.

The signals catch what was said around a trend, not its name: "baby wow karol g" (a lyric and
the singer) for "dime dime baby", "plantilla viral dame hombro" (template, viral, a lyric) for
"bulin 47", "enzo fernandez celebration" (a player and a move) for "ozil goal". Domains are
registered, and pages made, for the name; so the name is what is looked up (radar/taken.py)
and what is pushed.

A name is cut in layers, as one cuts "bungie destiny 2 unvaulting update" into a studio, a game
and the thing searched: platform words (trend, tiktok, capcut, plantilla, template, filter,
tutorial, viral, original, ai) go; a singer, player or celebrity is background; a lyric or a
move points to the trend it belongs to; the name of the song, clip, dance or meme is the name.
The AI versions' own captions and hashtags say it best ("#dimedimebaby", "dime dime baby ai
tutorial"), so the model reads them with the term.

The model names, it does not decide. On 25 October 2026 it was also asked whether a term was
one trend at all, and it turned away "im sorry i lied" (AI versions by 7 accounts, 2 million
plays), "20v1 ryanwitdasauce" and "tiny desk concert outstanding": nothing was pushed that day.
Whether a name is pushed is the data's call (radar/pushes.py). What the model thinks is a
category, a holiday or a brand rather than one trend ("halloween costume", "amapiano") is only
flagged, and the card says so.
"""
from __future__ import annotations

import json
import re

from . import aisa

SYSTEM = (
    "You read terms a radar caught on TikTok, Google and in new domains, each with a few places it appeared. "
    "For each, give the name of the viral trend it points to (a song, a music video scene, a dance, a clip, a meme, "
    "a filter or effect), as people would search it with \"ai\".\n"
    "Cut the term in layers. Drop platform words: trend, tiktok, capcut, plantilla, template, filter, tutorial, "
    "viral, original, dance, edit, ai, video, guide, learn, how to. A singer, player or celebrity is background, not "
    "the name. A lyric or a move points to the trend it belongs to: use the examples (hashtags, captions, domains) to "
    "find that trend's name. Examples: 'baby wow karol g' with captions '#dimedimebaby' -> 'dime dime baby'; "
    "'plantilla viral dame hombro' with '#bulin47' -> 'bulin 47'; 'peeper guide window peeper' -> 'window peeper'; "
    "'toc trend toc toc' -> 'toc toc'; 'hittheroad' (domain 'Hit the Road Dude AI') -> 'hit the road dude'. "
    "When you cannot tell, keep the term itself as the name. Always give a name.\n"
    "`same_as`: when the trend is one listed under `known` (the same clip, song or dance under other words), that "
    "known name exactly; otherwise \"\".\n"
    "`generic`: true when the name is not one specific trend but a holiday or season ('halloween costume'), a music "
    "genre or content category ('amapiano', 'edit tutorial', 'genderswap', 'art style'), a year recap ('2026 recap'), "
    "a person alone with no clip ('lamine yamal'), or a brand, tool or business ('hivideostudio', 'ai detector'); "
    "otherwise false. It is a hint for a person, nothing is dropped for it.\n"
    "Answer with JSON only, one object per item of `terms`, in the same order: "
    "[{\"i\": 0, \"name\": \"dime dime baby\", \"same_as\": \"\", \"generic\": false}, "
    "{\"i\": 1, \"name\": \"broom crash\", \"same_as\": \"broom riding\", \"generic\": false}, "
    "{\"i\": 2, \"name\": \"halloween costume\", \"same_as\": \"\", \"generic\": true}, ...]"
)


def _clean(name: str) -> str:
    return " ".join(re.sub(r"[^\w' ]", " ", name.lower()).split())


def parse(answer: str, n: int, known: list[str] | None = None) -> dict[int, dict]:
    """{index: {"name", "generic"}} from the model's answer. A trend it calls one of `known` goes by
    that known name; a `same_as` not in `known` is ignored. Items without a name are dropped."""
    known_names = {_clean(k): k for k in known or []}
    m = re.search(r"\[.*\]", answer, re.S)
    try:
        items = json.loads(m.group(0)) if m else []
    except ValueError:
        return {}
    out = {}
    for it in items if isinstance(items, list) else []:
        try:
            i, name = int(it["i"]), _clean(it["name"])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if not (0 <= i < n and name):
            continue
        same = it.get("same_as")
        out[i] = {"name": known_names.get(_clean(same), name) if isinstance(same, str) and same else name,
                  "generic": it.get("generic") is True}
    return out


def _related(known: list[str], rows: list[dict]) -> list[str]:
    """The known trends that share a word with a term or its examples: "broom riding" for "broom
    crash". Given all 200 names pushed lately, the model lost track of the new ones."""
    seen = set()
    for r in rows:
        for text in [r["term"], *(r.get("examples") or [])[:4]]:
            seen |= {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 4}
    return [k for k in known if seen & {w for w in re.findall(r"[a-z0-9]+", k.lower()) if len(w) >= 4}]


def names(rows: list[dict], model: str, known: list[str] | None = None) -> dict[str, dict]:
    """{term: {"name": the trend's name, "generic": a category rather than one trend?}}. `known`:
    the trends pushed lately, so that "broom crash" comes back as "broom riding" when it is that
    trend; only those sharing a word with the terms are shown to the model. A failed call, or a
    term the model skipped, keeps the term as its own name."""
    if not rows:
        return {}
    known = _related(known or [], rows)
    user = json.dumps({"known": known, "terms": [
        {"i": i, "term": r["term"], "examples": [e[:160] for e in (r.get("examples") or [])[:4]]
         + [v for v in r.get("variants", []) if v not in (r["term"], f"{r['term']} ai")][:3]}
        for i, r in enumerate(rows)]}, ensure_ascii=False)
    try:
        got = parse(aisa.chat(model, SYSTEM, user, max_tokens=90 * len(rows) + 200), len(rows), known)
    except aisa.AisaError:
        got = {}
    return {r["term"]: got.get(i, {"name": r["term"], "generic": False}) for i, r in enumerate(rows)}
