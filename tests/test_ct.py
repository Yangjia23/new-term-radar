"""CT lookups (Cert Spotter) for the names pushed. No network."""
import urllib.error

from radar import ct, report

C = {"max_lookups": 9, "per_name": 3}


def test_hosts_are_a_wave_s_own_domains_first_then_the_usual_spellings():
    assert ct.hosts({"term": "bulin 47", "examples": ["bulin47ai.link", "bulin47.ai", "bulin-47-video.com"]}, 3) == \
        ["bulin47.ai", "bulin-47-video.com", "bulin47ai.link"]
    assert ct.hosts({"term": "hotel lobby", "examples": ["#hotellobbyai", "hotel lobby ai"]}, 3) == \
        ["hotellobbyai.com", "hotellobby.ai", "hotellobby.com"]


def test_check_counts_live_sites_and_their_first_day(monkeypatch):
    days = {"hotellobbyai.com": ["2026-09-24", "2026-10-01"], "hotellobby.ai": ["2026-09-29"], "hotellobby.com": []}
    monkeypatch.setattr(ct, "issued", lambda h: days[h])
    out = ct.check([{"term": "hotel lobby", "examples": []}], C)
    assert out == {"names": {"hotel lobby": {"live": 2, "checked": 3, "first": "2026-09-24"}}, "lookups": 3}


def test_check_stops_when_the_free_allowance_is_spent(monkeypatch):
    def limited(h):
        raise urllib.error.HTTPError(h, 429, "Too Many Requests", {}, None)
    monkeypatch.setattr(ct, "issued", limited)
    out = ct.check([{"term": "a word", "examples": []}, {"term": "another", "examples": []}], C)
    assert out["lookups"] == 1 and out["names"] == {} and out["errors"] == ["awordai.com: HTTP 429"]


def test_check_reads_no_more_names_than_the_lookups_allow(monkeypatch):
    monkeypatch.setattr(ct, "issued", lambda h: [])
    rows = [{"term": f"word{i}", "examples": []} for i in range(5)]
    assert list(ct.check(rows, C)["names"]) == ["word0", "word1", "word2"]


def test_the_push_line_says_how_many_sites_are_live(cfg, monkeypatch):
    monkeypatch.setattr(report.judge, "score", lambda rows, model, focus="names": {"judged": 0})
    block = {"terms": [{"term": "hotel lobby", "note": "New domains: 7", "examples": ["hotellobby.ai"]},
                       {"term": "bulin 47", "note": "New domains: 5", "examples": ["bulin47.ai"]}]}
    lead, _ = report.leads(cfg, {"domain": block})
    extra = {"ct": {"names": {"hotel lobby": {"live": 2, "checked": 3, "first": "2026-09-24"},
                              "bulin 47": {"live": 0, "checked": 3, "first": None}}}}
    text = report.push(cfg, lead, {"domain": block}, extra)[1]
    assert "**hotel lobby** · New domains: 7 · CT: 2/3 live, first 09-24" in text and "**bulin 47** · New domains: 5 · CT: none of 3 live" in text
