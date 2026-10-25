"""Signal ① pages (trend pages new to a site's sitemap) and the Feishu heartbeat. No network."""
import copy

from radar import config, pages, report

SITE = "https://dreamina.capcut.com"


def _cfg():
    c = copy.deepcopy(config.DEFAULTS)
    c["pages"] = {"dreamina": {"index": f"{SITE}/sitemap.xml", "sections": ["ai-video", "ai-image"], "pause": 0}}
    return c


def _sitemap(monkeypatch, paths):
    monkeypatch.setattr(pages, "site_urls", lambda index, shards, pause: {f"{SITE}/{p}" for p in paths})


def test_the_name_is_the_slug_without_its_tail_words():
    assert pages.name("ozil-goal-ai-video-generator") == "ozil goal"
    assert pages.name("me-next-monday-ai-video") == "me next monday"
    assert pages.name("ai-liquid-metal-filter") == "liquid metal"
    assert pages.name("ai-video-generator") == ""


def test_the_first_run_keeps_the_pages_and_later_runs_report_the_new_ones(tmp_path, monkeypatch):
    _sitemap(monkeypatch, ["ai-video/drinking-trend", "resource/blend-tool-on-photoshop"])
    first = pages.new_pages(_cfg(), tmp_path)
    assert first["first_run"] and first["terms"] == [] and first["read"] == 1        # resource/ is not a kept section
    _sitemap(monkeypatch, ["ai-video/drinking-trend", "ai-video/ozil-goal-ai-video-generator", "ai-image/ai-video",
                           "ai-video/how-small-teams-scale-promo-videos-with-ai", "resource/new-guide"])
    later = pages.new_pages(_cfg(), tmp_path)
    assert not later["first_run"] and later["new"] == 3
    assert [r["term"] for r in later["terms"]] == ["ozil goal"]                       # tail words alone, or a guide, name nothing
    assert later["terms"][0]["note"] == "Trend page: dreamina"
    assert later["terms"][0]["examples"] == []                                         # the push names the site, not the page


def test_a_site_with_its_trends_at_the_root_skips_its_guides_and_translations(tmp_path, monkeypatch):
    # tryatrend.com's sitemap of 25 October 2026, in part
    c = copy.deepcopy(config.DEFAULTS)
    c["pages"] = {"tryatrend": {"index": f"{SITE}/sitemap.xml", "skip": ["guides", "es", "ja", "pricing"], "pause": 0}}
    _sitemap(monkeypatch, ["", "witch-broom-ai", "es/trend-escoba-voladora-ia", "guides/how-to-make-witch-broom-ai-video", "pricing"])
    assert pages.new_pages(c, tmp_path)["read"] == 1
    _sitemap(monkeypatch, ["", "witch-broom-ai", "sorry-i-lied-costume-ai", "es/perdon-trend-ia",
                           "guides/how-to-make-im-so-sorry-i-lied-ai-video", "ja/pricing", "pricing"])
    assert [r["term"] for r in pages.new_pages(c, tmp_path)["terms"]] == ["sorry i lied costume"]


def test_a_page_and_a_trends_query_are_one_lead(cfg, monkeypatch):
    monkeypatch.setattr(report.judge, "score", lambda rows, model, focus="names": {"judged": 0})
    blocks = {"pages": {"terms": [{"term": "ozil goal", "note": "New page on dreamina", "examples": []}]},
              "rising": {"terms": [{"term": "ozil goal", "note": "Trends: ozil goal ai", "examples": []}]}}
    lead, _ = report.leads(cfg, blocks)
    assert len(lead) == 1 and lead[0]["kinds"] == ["pages", "rising"]


def test_a_site_that_fails_says_so(tmp_path, monkeypatch):
    def down(index, shards, pause):
        raise OSError("HTTP 403")
    monkeypatch.setattr(pages, "site_urls", down)
    assert pages.new_pages(_cfg(), tmp_path)["error"] == "dreamina: HTTP 403"


def test_the_heartbeat_lists_each_signal_that_ran(monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_REPOSITORY", "me/radar")
    title, text = report.heartbeat("sources", {"x": {"skipped": True}, "tiktok": {"read": 100, "terms": []},
                                               "pages": {"read": 4800, "first_run": True, "terms": []}})
    assert title == "New-term radar · sources: ran fine, nothing new"
    assert text.splitlines()[:2] == ["- ① TikTok: ok · 100", "- ① trend pages: ok · 4800, first run: snapshot built"]
    assert "① X" not in text and "actions/runs/42" in text
