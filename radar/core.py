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

The same call sorts out what is not one trend: a holiday or season ("halloween costume"), a
genre or category ("amapiano", "edit tutorial", "genderswap"), a person alone, a brand or tool
site, a year recap. Those are not pushed. One chat call for all the names about to be pushed,
through the judge's model.
"""
from __future__ import annotations

import json
import re

from . import aisa

SYSTEM = (
    "You read terms a radar caught on TikTok, Google and in new domains, each with a few places it appeared. "
    "For each, say whether it points to ONE specific viral trend that people remake with AI (a song, a music video "
    "scene, a dance, a clip, a meme, a filter or effect named after one thing), and if so, the trend's own name as "
    "people would search it with \"ai\".\n"
    "Cut the term in layers. Drop platform words: trend, tiktok, capcut, plantilla, template, filter, tutorial, "
    "viral, original, dance, edit, ai, video, guide, learn, how to. A singer, player or celebrity is background, not "
    "the name. A lyric or a move points to the trend it belongs to: use the examples (hashtags, captions, domains) to "
    "find that trend's name. Examples: 'baby wow karol g' with captions '#dimedimebaby' -> 'dime dime baby'; "
    "'plantilla viral dame hombro' with '#bulin47' -> 'bulin 47'; 'peeper guide window peeper' -> 'window peeper'; "
    "'toc trend toc toc' -> 'toc toc'; 'hittheroad' (domain 'Hit the Road Dude AI') -> 'hit the road dude'. "
    "A trend may carry a brand, a person or an old classic in its name ('tesla flying car', 'mr bean filter', "
    "'gangnam style ai dance'): it is a trend when the examples show people making AI videos of that one thing.\n"
    "When the term is one of the trends listed under `known` (the same clip, song or dance under other words), "
    "answer that known name exactly.\n"
    "Answer \"\" (not one trend) for: a holiday or season ('halloween costume'), a music genre or a content category "
    "('amapiano', 'uk rap', 'edit tutorial', 'genderswap', 'art style', 'football edits', 'slowed audios'), a year "
    "recap or dump ('2026 recap'), a person alone with no clip named ('lamine yamal', 'jason derulo'), a brand, "
    "tool, studio or business site with no trend in it ('hivideostudio', 'tmc video', 'halal trade', 'ai detector'), "
    "a random or made-up string ('troquevande'), adult content, or "
    "anything made for Chinese-speaking users.\n"
    "Answer with JSON only, one object per item of `terms`, in the same order: [{\"i\": 0, \"name\": \"dime dime baby\"}, "
    "{\"i\": 1, \"name\": \"\"}, ...]"
)


def parse(answer: str, n: int) -> dict[int, str]:
    """{index: name} from the model's answer, "" for not one trend; bad items are dropped."""
    m = re.search(r"\[.*\]", answer, re.S)
    try:
        items = json.loads(m.group(0)) if m else []
    except ValueError:
        return {}
    out = {}
    for it in items if isinstance(items, list) else []:
        try:
            i, name = int(it["i"]), it["name"]
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= i < n and isinstance(name, str):
            out[i] = " ".join(re.sub(r"[^\w' ]", " ", name.lower()).split())
    return out


def names(rows: list[dict], model: str, known: list[str] | None = None) -> dict[str, str]:
    """{term: the trend's name, or "" when the term is not one trend}. `known`: the trends pushed
    lately, so that "broom crash" comes back as "broom riding" when it is that trend. A failed call,
    or a term the model skipped, keeps the term as its own name: the data still decides whether it
    is pushed."""
    if not rows:
        return {}
    user = json.dumps({"known": known or [], "terms": [
        {"i": i, "term": r["term"], "examples": [e[:160] for e in (r.get("examples") or [])[:4]]
         + [v for v in r.get("variants", []) if v not in (r["term"], f"{r['term']} ai")][:3]}
        for i, r in enumerate(rows)]}, ensure_ascii=False)
    try:
        got = parse(aisa.chat(model, SYSTEM, user, max_tokens=60 * len(rows) + 200), len(rows))
    except aisa.AisaError:
        got = {}
    return {r["term"]: got.get(i, r["term"]) for i, r in enumerate(rows)}
