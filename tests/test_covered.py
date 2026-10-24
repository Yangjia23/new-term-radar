"""Whether Dreamina has a page for a name about to be pushed. No network."""
from radar import covered, report, snap

# Part of Dreamina's sitemap of 19 October 2026.
SITEMAP = ["https://dreamina.capcut.com/ai-video/my-ride-is-here-ai-broom-trend",
           "https://dreamina.capcut.com/ai-video/crazy-frog-chase-video",
           "https://dreamina.capcut.com/ai-video/toc-toc-dance-ai-video-trend",
           "https://dreamina.capcut.com/ai-image/ai-halloween-costume-generator"]


def test_a_name_is_found_in_the_kept_sitemap_then_at_the_usual_slugs(tmp_path, monkeypatch):
    snap.save(tmp_path / "pages" / "dreamina.json.gz", SITEMAP)
    asked = []
    up = "https://dreamina.capcut.com/ai-video/closed-on-sunday-ai-video"         # newer than the sitemap
    monkeypatch.setattr(covered, "live", lambda url: asked.append(url) or url == up)
    found = covered.dreamina(tmp_path, ["my ride is here", "crazy frog", "toc toc", "closed on sunday", "foam mirror"])
    assert found == {"my ride is here": SITEMAP[0], "crazy frog": SITEMAP[1], "toc toc": SITEMAP[2], "closed on sunday": up}
    assert all("my-ride" not in u and "crazy-frog" not in u for u in asked)     # found in the sitemap: not asked
    assert len([u for u in asked if "foam-mirror" in u]) == len(covered.SLUGS)
