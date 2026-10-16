"""Signal ① rising (Google Trends' rising related queries through SerpApi), the DeepSeek route
for the judge, and its trends focus. No network: SerpApi and the chat are stand-ins."""
import copy
from datetime import date

from radar import aisa, config, judge, report, rising

TODAY = date(2026, 9, 25)
# What SerpApi answered for "higgsfield" over 15-25 September 2026, shortened.
HIGGSFIELD = [{"query": "hotel lobby ai", "value": "Breakout", "extracted_value": 27900},
              {"query": "migos trend", "value": "Breakout", "extracted_value": 9200},
              {"query": "migos ai", "value": "+2,800%", "extracted_value": 2800},
              {"query": "higgsfield api", "value": "+160%", "extracted_value": 160}]


def _serp(monkeypatch, answers, left=300):
    calls = []

    def get(url, params):
        calls.append(params)
        if url == rising.ACCOUNT:
            return {"total_searches_left": left}
        return {"related_queries": {"rising": answers.get(params["q"], [])}}
    monkeypatch.setattr(rising, "_get", get)
    monkeypatch.setenv("SERPAPI_API_KEY", "k")
    return calls


def _cfg(seeds):
    c = copy.deepcopy(config.DEFAULTS)
    c["rising"]["seeds"] = seeds
    return c


def test_core_drops_the_seed_and_the_words_around_a_trend():
    assert rising.core("higgsfield hotel lobby ai", "higgsfield") == "hotel lobby"
    assert rising.core("storm ii ai", "higgsfield") == "storm ii"
    assert rising.core("how to make migos ai video", "ai video") == "migos"


def test_rising_keeps_breakouts_and_big_rises_and_reports_each_query_once(tmp_path, monkeypatch):
    calls = _serp(monkeypatch, {"higgsfield": HIGGSFIELD})
    out = rising.rising(_cfg(["higgsfield"]), tmp_path, TODAY)
    terms = {r["term"]: r for r in out["terms"]}
    assert set(terms) == {"hotel lobby", "migos"} and out["queries"] == 3 and out["left"] == 299
    assert terms["migos"]["examples"] == ["migos trend", "migos ai"] and "hotel lobby ai" in terms["hotel lobby"]["variants"]
    assert terms["hotel lobby"]["note"] == 'Trends: "hotel lobby ai" around higgsfield, Breakout'
    assert calls[1]["date"] == "now 7-d" and calls[1]["data_type"] == "RELATED_QUERIES"
    assert rising.rising(_cfg(["higgsfield"]), tmp_path, TODAY)["terms"] == []          # seen already


def test_rising_stops_at_the_reserve_and_reads_only_what_the_credits_allow(tmp_path, monkeypatch):
    _serp(monkeypatch, {}, left=20)
    assert "20 searches left" in rising.rising(_cfg(["a", "b"]), tmp_path, TODAY)["error"]
    calls = _serp(monkeypatch, {}, left=21)
    assert rising.rising(_cfg(["a", "b"]), tmp_path, TODAY)["seeds"] == 1 and [c.get("q") for c in calls] == [None, "a"]


def test_rising_without_seeds_is_off_and_without_a_key_says_so(tmp_path, monkeypatch):
    assert rising.rising(_cfg([]), tmp_path, TODAY) == {"skipped": True}
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    assert rising.rising(_cfg(["higgsfield"]), tmp_path, TODAY)["error"] == "no SERPAPI_API_KEY"


def test_a_seed_that_fails_leaves_the_others(tmp_path, monkeypatch):
    _serp(monkeypatch, {"higgsfield": HIGGSFIELD})
    real = rising._get

    def get(url, params):
        if params.get("q") == "pixverse":
            raise rising.SerpError("HTTP 429: rate limited")
        return real(url, params)
    monkeypatch.setattr(rising, "_get", get)
    out = rising.rising(_cfg(["pixverse", "higgsfield"]), tmp_path, TODAY)
    assert out["read"] == 1 and out["errors"] == ["pixverse: HTTP 429: rate limited"] and "error" not in out


def test_a_trend_found_by_both_signals_is_one_lead(cfg, tmp_path, monkeypatch):
    _serp(monkeypatch, {"higgsfield": HIGGSFIELD})
    monkeypatch.setattr(report.judge, "score", lambda rows, model, focus="names": {"judged": 0})
    domain = {"terms": [{"term": "hotel lobby", "note": "New domains: 7", "recent": 7, "lift": 7.0, "examples": ["hotellobby.ai"]}]}
    lead, _ = report.leads(cfg, {"rising": rising.rising(_cfg(["higgsfield"]), tmp_path, TODAY), "domain": domain})
    hotel = next(r for r in lead if r["term"] == "hotel lobby")
    assert hotel["kinds"] == ["rising", "domain"] and lead[0] is hotel                     # two signals lead


# --- the judge: DeepSeek and the trends focus --------------------------------------------

def test_a_deepseek_model_goes_to_deepseek_when_its_key_is_set(monkeypatch):
    sent = []
    monkeypatch.setattr(aisa, "_post", lambda url, body, timeout, token="": sent.append((url, token)) or
                        {"choices": [{"message": {"content": "ok"}}]})
    monkeypatch.setenv("AISA_API_KEY", "aisa")
    aisa.chat("deepseek-chat", "s", "u")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds")
    aisa.chat("deepseek-chat", "s", "u")
    aisa.chat("gpt-4.1-mini", "s", "u")
    assert sent == [(aisa.CHAT, ""), (aisa.DEEPSEEK_CHAT, "ds"), (aisa.CHAT, "")]


def test_the_trends_focus_asks_the_narrower_question(monkeypatch):
    asked = []
    monkeypatch.setattr(judge.aisa, "chat", lambda model, system, user, *a: asked.append(system) or '[{"i": 0, "score": 0.9}]')
    judge.score([{"term": "hotel lobby"}], "deepseek-chat", "trends")
    judge.score([{"term": "hotel lobby"}], "deepseek-chat")
    assert asked == [judge.SYSTEM_TRENDS, judge.SYSTEM] and "viral TRENDS" in asked[0]
