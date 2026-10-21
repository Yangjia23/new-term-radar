"""What a wave's new sites say on their home page: a tool for the trend, or a parked name.

On 19 October 2026 the judge called "flying car" an everyday word (0.2) while two of its eight
new domains were already selling the trend: flyingcarai.art, "Flying Car AI – Launch Your Car
Off the Viral Ramp From One Photo", and flying-car-ai.com, "Flying Car AI Video Generator |
Ramp Stunt from a Photo". The rest were parked for sale. A home page's title and description
that name the word and a tool for it say what the word is better than the word alone.

One GET a domain (free), a few at a time; a site that does not answer says nothing.
"""
from __future__ import annotations

import html
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import UA

TIMEOUT = 8
MAX_BYTES = 200_000
WORKERS = 32
# The words of an AI tool for a trend: "AI Video Generator", "from one photo", "... AI filter".
TOOL = re.compile(r"\bai\b.*\b(video|videos|generator|filter|effect|template|maker|photo|image|edit|editor|meme|dance|duet)\b"
                  r"|\b(video|generator|filter|effect|template|maker)\b.*\bai\b|\bfrom (one|a|your) (photo|picture|image|selfie)\b")
# A single site is a template for a trend: a video, a dance, a filter, a meme, made from a photo.
# "StoneAI — AI Website Builder", "Proxlai: prices for every AI API" are tools, not for a trend.
TEMPLATE = re.compile(r"\b(videos?(?! games?)|dance|filter|meme|effect|duet|trend)\b|\bfrom (one|a|your|1|2|1–2|1-2) (car )?(photo|picture|selfie)")
# AI products that are not a template for a trend.
OTHER = re.compile(r"detector|humani[sz]er|chatbot|trading|website builder|\bapi\b|playbook|course")
ADULT = re.compile(r"nsfw|porn|nude|hentai|18\+|xxx")
# What a title says before "AI": "Flying Car AI Video Generator", "Toc Toc AI – ...".
_LEAD = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9 '&.-]{1,40}?)\s+AI\b")
# Words that name no trend: "Making AI Videos", "Free AI Video Generator".
GENERIC = {"making", "make", "free", "best", "online", "create", "the", "my", "your", "pro", "smart", "easy", "top",
           "video", "videos", "photo", "image", "art", "magic", "super", "ultimate", "simple", "fast", "instant",
           "creative", "studio", "mastery", "master", "trend", "trends", "viral", "meme", "dance", "style", "styles",
           "ai", "maker", "generator", "filter", "effect", "edit", "editor", "app", "tool", "tools", "hi", "hub", "lab",
           "labs", "playbook", "guide", "academy", "baby", "pet", "cat", "dog", "kids", "couple", "selfie", "face"}
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_META = re.compile(r"<meta\b[^>]*>", re.I)
_CONTENT = re.compile(r"""content\s*=\s*["']([^"']*)["']""", re.I)
_WHICH = re.compile(r"""(?:name|property)\s*=\s*["'](description|og:title|og:description)["']""", re.I)


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return res.read(MAX_BYTES).decode("utf-8", "replace")


def head(page: str) -> str:
    """The title and the description of a page, as one line."""
    parts = [m.group(1) for m in _TITLE.finditer(page)][:1]
    for tag in _META.findall(page):
        if _WHICH.search(tag) and (c := _CONTENT.search(tag)):
            parts.append(c.group(1))
    return " ".join(html.unescape(" | ".join(parts)).split())


def look(host: str) -> str:
    """The home page's title and description; "" when the site does not answer."""
    try:
        return head(_get(f"https://{host}"))
    except Exception:  # noqa: BLE001 — a parked, dead or slow site is just not a tool
        return ""


def tool(core: str, text: str) -> bool:
    """A page about the word that offers an AI tool for it: "Flying Car AI Video Generator" for "flyingcar"."""
    low = text.lower()
    return core in re.sub(r"[^a-z0-9]", "", low) and bool(TOOL.search(low))


def heads(hosts: list[str]) -> dict[str, str]:
    """{host: its home page's title and description}, "" for a site that does not answer."""
    with ThreadPoolExecutor(WORKERS) as pool:
        return dict(zip(hosts, pool.map(look, hosts)))


def name(core: str, text: str) -> tuple[str, str] | None:
    """(name, core) of the trend a single new site is a template for, None when it is not one. Read
    from the title alone: descriptions name video and trends for any AI product ("Vitre AI", an ad
    studio). The name is what the title puts before "AI" ("Thriller Dance AI Video Generator" ->
    "thriller dance") when the domain holds it, toctocaidance.com being "toc toc"; else the
    domain's core when the title opens with it ("Zombie Filter – ... with AI", "AI Baby Dance Video
    Generator"). A title naming no trend ("Viral AI Video Playbook") is not one."""
    title = text.split(" | ")[0]
    low = title.lower()
    if not (TOOL.search(low) and TEMPLATE.search(low)) or ADULT.search(low) or OTHER.search(low):
        return None
    m = _LEAD.match(title)
    if m:
        lead = " ".join(m.group(1).lower().split())
        flat = re.sub(r"[^a-z0-9]", "", lead)
        if len(flat) >= 5 and flat in core and not _generic(flat):
            return lead, flat
    opening = re.sub(r"^ai", "", re.sub(r"[^a-z0-9]", "", low))
    return (core, core) if len(core) >= 6 and opening.startswith(core) and not _generic(core) else None


def _generic(flat: str) -> bool:
    """Made of GENERIC words only: "memevideo", "aivideomaker"."""
    ok = [True] + [False] * len(flat)
    for i in range(1, len(flat) + 1):
        ok[i] = any(ok[j] and flat[j:i] in GENERIC for j in range(max(0, i - 12), i))
    return ok[-1]
