"""Signal ① tiktok (trending hashtags through AIsa) and the blocklist. No network."""
import copy
from datetime import date

from radar import config, judge, report, tiktok

TODAY = date(2026, 10, 16)


def _page(tags):
    return {"data": {"items": [{"hashtagName": tag, "publishCnt": n} for tag, n in tags]}}


def _cfg():
    c = copy.deepcopy(config.DEFAULTS)
    c["tiktok"]["countries"] = ["US"]
    c["tiktok"]["pages"] = 1
    return c


def _answer(monkeypatch, tags):
    calls = []

    def call(batch):
        calls.append(batch)
        return {b["call_id"]: _page(tags) for b in batch}, 1000 * len(batch)
    monkeypatch.setattr(tiktok.aisa, "call", call)
    return calls


def test_core_cuts_a_tag_like_a_domain():
    assert tiktok.core("burningbridgesai") == "burningbridges"
    assert tiktok.core("#bulin47challenge") == "bulin47"
    assert tiktok.core("hotellobbytrend") == "hotellobby"


def test_the_first_run_keeps_the_chart_and_later_runs_report_what_entered_it(tmp_path, monkeypatch):
    calls = _answer(monkeypatch, [("marvelrivalsavengers", 108935), ("bulin47", 13815)])
    first = tiktok.trending(_cfg(), tmp_path, TODAY)
    assert first["first_run"] and first["terms"] == [] and first["read"] == 2
    assert calls[0][0]["arguments"]["body"] == {"country_code": "US", "time_range": 7, "page": 1, "limit": 50}
    _answer(monkeypatch, [("bulin47", 14000), ("burningbridgesai", 3193), ("bulin47challenge", 4567)])
    terms = {r["term"]: r for r in tiktok.trending(_cfg(), tmp_path, TODAY)["terms"]}
    assert set(terms) == {"burningbridges", "bulin47"} and terms["bulin47"]["examples"] == ["#bulin47challenge"]
    assert terms["burningbridges"]["note"] == "TikTok: #burningbridgesai new in the US top 100 at #2 (3,193 posts)"


def test_a_hashtag_and_a_domain_wave_are_one_lead_with_the_spaced_name(cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(report.judge, "score", lambda rows, model, focus="names": {"judged": 0})
    blocks = {"tiktok": {"terms": [{"term": "burningbridges", "note": "TikTok: #burningbridgesai", "examples": ["#burningbridgesai"]}]},
              "domain": {"terms": [{"term": "burning bridges", "note": "New domains: 12", "examples": ["burningbridges.ai"]}]}}
    lead, _ = report.leads(cfg, blocks)
    assert len(lead) == 1 and lead[0]["term"] == "burning bridges" and lead[0]["kinds"] == ["tiktok", "domain"]


def test_a_failed_country_says_so(tmp_path, monkeypatch):
    def down(batch):
        raise tiktok.aisa.AisaError("HTTP 502")
    monkeypatch.setattr(tiktok.aisa, "call", down)
    assert tiktok.trending(_cfg(), tmp_path, TODAY)["error"] == "US: HTTP 502"
    assert tiktok.trending(copy.deepcopy(config.DEFAULTS), tmp_path, TODAY) == {"skipped": True}


def test_every_tag_new_to_the_chart_is_listed_with_its_score_even_when_too_short(tmp_path, monkeypatch):
    _answer(monkeypatch, [("bulin47", 13815)])
    tiktok.trending(_cfg(), tmp_path, TODAY)
    _answer(monkeypatch, [("bulin47", 14000), ("nfl", 900), ("burningbridgesai", 3193)])
    block = tiktok.trending(_cfg(), tmp_path, TODAY)
    assert [(e["tag"], e["rank"], e["term"]) for e in block["entered"]] == [("nfl", 2, "nfl"), ("burningbridgesai", 3, "burningbridges")]
    block["entered"][1]["score"] = 0.9
    assert report._entered(block) == ["  new in the chart: #nfl (#2, —), #burningbridgesai (#3, 0.9)"]


def test_the_chart_judges_every_tag_and_marks_the_ones_seen(tmp_path, monkeypatch):
    _answer(monkeypatch, [("bulin47", 13815)])
    tiktok.trending(_cfg(), tmp_path, TODAY)
    _answer(monkeypatch, [("bulin47", 14000), ("nfl", 900)])

    def score(rows, model, focus="names"):
        for r in rows:
            r["named"] = 0.8 if r["term"] == "bulin47" else 0.1
        return {"judged": len(rows)}
    monkeypatch.setattr(judge, "score", score)
    c = tiktok.chart(_cfg(), tmp_path)
    assert [(h["tag"], h["score"], h["seen"]) for h in c["tags"]] == [("bulin47", 0.8, "2026-10-16"), ("nfl", 0.1, None)]
    text = report.tiktok_chart(c)
    assert "| 1 | #bulin47 | 14,000 | bulin47 | 0.8 | ✅ | 2026-10-16 |" in text and "| 2 | #nfl | 900 | nfl | 0.1 |  | — |" in text
