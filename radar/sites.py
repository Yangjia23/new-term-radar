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

TIMEOUT = 10
MAX_BYTES = 200_000
WORKERS = 16
# The words of an AI tool for a trend: "AI Video Generator", "from one photo", "... AI filter".
TOOL = re.compile(r"\bai\b.*\b(video|videos|generator|filter|effect|template|maker|photo|image|edit|editor)\b"
                  r"|\b(video|generator|filter|effect|template|maker)\b.*\bai\b|\bfrom (one|a|your) (photo|picture|image|selfie)\b")
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


def tools(rows: list[dict], per_name: int) -> dict[str, tuple[str, str]]:
    """{core: (host, its title)} for the rows one of whose first `per_name` domains is a tool for the word."""
    asks = [(r["core"], h) for r in rows for h in r["examples"][:per_name]]
    with ThreadPoolExecutor(WORKERS) as pool:
        heads = list(pool.map(lambda a: look(a[1]), asks))
    out: dict[str, tuple[str, str]] = {}
    for (core, host), text in zip(asks, heads):
        if core not in out and tool(core, text):
            out[core] = (host, text.split(" | ")[0][:90])
    return out
