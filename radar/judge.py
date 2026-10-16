"""Is this term the name of a new thing, or a common word?

The signals surface whatever is new in the text they read: "Opus 5.5" and "HyperFrames",
but also "Lots", "Trained" and "voice notes". A small model reads each term with a few
places it appeared and scores it from 0 to 1; the report leads with the names.

One chat call per CHUNK terms through AIsa's OpenAI-compatible endpoint (or DeepSeek's, see
aisa.chat), the model set in config.json (judge.model). judge.focus "trends" asks a narrower
question: is it a viral trend people remake as AI videos? A company or app name then scores
low too. Without a key, or when the call fails, the terms keep no score and the report lists
them all: the judge sorts the report, it never blocks it.
"""
from __future__ import annotations

import json
import re

from . import aisa

CHUNK = 25
SYSTEM = (
    "You sort terms for a radar that looks for new product names. For each term, score from 0.0 to 1.0 how likely "
    "it is the NAME of one specific product, model, tool, library, company or technique, or of one viral trend: a "
    "song, clip, dance or meme that people now remake as AI videos, as opposed to a common word, a generic category, "
    "a feature description or a fragment of a sentence. `examples` are places where the term appeared (posts, "
    "repository descriptions, model ids, URL paths, newly registered domains); use them.\n"
    "Names: 'opus 5.5', 'hyperframes', 'seedance', 'qwen image 2.1', 'strata' (when the examples show a project "
    "called Strata), 'hotel lobby', 'bulin 47', 'rumpelstiltskin', 'zombie couple' (when the examples are domains "
    "like hotellobbyai.com or bulin-47-video.com: a trend people make AI videos of).\n"
    "Not names: 'dashboard', 'voice notes', 'pdf', 'lots', 'trained', 'video generator', 'new release', 'today'; "
    "and everyday words that domains always carry, however many: 'world', 'tools', 'robot', 'girlfriend', 'center'; "
    "nor a betting, loan or shop brand bought in bulk ('casibom bet', 'sky88').\n"
    "A known company or product family alone ('google', 'claude') is a name, but an old one: score it 0.5.\n"
    "Answer with JSON only, one object per term, in the same order: [{\"i\": 0, \"score\": 0.9}, ...]"
)


SYSTEM_TRENDS = (
    "You sort terms for a radar that looks for new viral TRENDS that people remake as AI videos or photos: a song, a scene "
    "from a music video, a dance, a clip, a meme, a character or a story format. Examples of such trends: 'hotel lobby' "
    "(a Migos performance people swap themselves into), 'bulin 47' (a street freestyle), 'rumpelstiltskin' (an AI clip that "
    "became a meme), 'burning bridges' (a Drake video scene), 'zombie couple' (an AI story format).\n"
    "For each term, score from 0.0 to 1.0 how likely it is such a trend. `examples` are where the term appeared: newly "
    "registered domains or Google searches. A domain with ai, video, generator, trend or filter around the term hints at an "
    "AI video template; a search like '<term> ai' or '<brand> <term>' hints at the same.\n"
    "Score low (0.0 to 0.2): a company, startup, product, app or SaaS name ('victoriaalpha', 'listkit', 'aha creators'); a "
    "betting, loan, crypto or shop brand ('886bet', 'sportbonustop', 'extrade'); an ordinary word or name in any language, "
    "or a place ('tools', 'world', 'robot', 'diary', 'fellside', 'stednjiste'); a generic AI category ('super intelligence', "
    "'ai girlfriend'); news about a company ('openai contractors terminated'); a feature or a plan ('pricing', 'login'); "
    "adult or sexual content; a name in Chinese pinyin or anything made for Chinese-speaking users ('huangguo', 'duanju'); "
    "news, sports and holidays ('hurricane isaias', 'chicago marathon', 'columbus day'); a real person, such as an "
    "entrepreneur, influencer, celebrity, athlete or executive ('iman gadzhi', 'alex mashrabov', 'shane gillis'), unless "
    "the examples show people remaking a clip of them as AI videos ('migos ai video', 'migos trend').\n"
    "When it is unclear whether the term is a trend, give 0.3 to 0.5.\n"
    "Answer with JSON only, one object per term, in the same order: [{\"i\": 0, \"score\": 0.9}, ...]"
)
SYSTEMS = {"names": SYSTEM, "trends": SYSTEM_TRENDS}


def parse(answer: str, n: int) -> dict[int, float]:
    """{index: score} from the model's answer; indexes outside 0..n-1 and bad scores are dropped."""
    m = re.search(r"\[.*\]", answer, re.S)
    try:
        items = json.loads(m.group(0)) if m else []
    except ValueError:
        return {}
    out = {}
    for it in items if isinstance(items, list) else []:
        try:
            i, score = int(it["i"]), float(it["score"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= i < n and 0.0 <= score <= 1.0:
            out[i] = score
    return out


def score(rows: list[dict], model: str, focus: str = "names") -> dict:
    """Sets r["named"] on each row the model scored. Returns {"judged": n} or {"error": ...}."""
    if not model:
        return {"judged": 0, "skipped": True}
    judged = 0
    for start in range(0, len(rows), CHUNK):
        chunk = rows[start:start + CHUNK]
        user = json.dumps([{"i": i, "term": r["term"], "examples": [e[:160] for e in r.get("examples", [])[:3]]}
                           for i, r in enumerate(chunk)], ensure_ascii=False)
        try:
            scores = parse(aisa.chat(model, SYSTEMS[focus], user), len(chunk))
        except aisa.AisaError as exc:
            return {"judged": judged, "error": str(exc)[:160]}
        for i, s in scores.items():
            chunk[i]["named"] = s
        judged += len(scores)
    return {"judged": judged}
