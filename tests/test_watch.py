"""Signal ① searchwords (TikTok's trending searches) and the watch list (Google's autocomplete). No network."""
import copy
import json
from datetime import date

from radar import __main__ as cli
from radar import config, notify, report, searchwords, watch

TODAY = date(2026, 10, 19)
WORDS = ["foam mirror tiktok trend", "Bulin 47’s Freestyle Surpasses 50M Views", "Hell Nah Cuh TikTok Meme",
         "Testimony Opens in Matthew Farwell Trial", "trend"]


def _cfg():
    c = copy.deepcopy(config.DEFAULTS)
    c["searchwords"]["on"] = True
    c["watch"]["pause"] = 0
    return c


def _words(monkeypatch, words):
    monkeypatch.setattr(searchwords.aisa, "call", lambda calls: (
        {"w": {"data": {"trending_search_words": [{"trendingSearchWord": w} for w in words]}}}, 1000))


def _google(monkeypatch, answers):
    asked = []

    def get(url):
        q = url.split("q=")[1].replace("+", " ").replace("%27", "'")
        asked.append(q)
        return json.dumps([q, answers.get(q, [])]).encode()
    monkeypatch.setattr(watch, "_get", get)
    return asked


def test_the_name_is_the_search_without_its_tail_words():
    assert searchwords.name("foam mirror tiktok trend") == "foam mirror"
    assert searchwords.name("Hell Nah Cuh TikTok Meme") == "hell nah cuh"
    assert searchwords.name("fish sweater TikTok goes viral") == "fish sweater"
    assert searchwords.name("Bulin 47’s Freestyle Surpasses 50M Views") == "bulin 47 freestyle surpasses 50m views"
    assert searchwords.name("trend") == ""
    assert searchwords.name("Ba Ba Ba TikTok Dance Challenge") == "ba ba ba dance"
    assert searchwords.name("suspect trend couple pumpkin patch original") == "suspect"
    assert searchwords.name("ghostface trend with gf") == "ghostface"
    assert searchwords.name("can't stop thinking of you letter r trend") == "cant stop thinking of you letter r"


def test_the_first_run_reports_every_search_and_later_runs_only_the_new_ones(tmp_path, monkeypatch):
    _words(monkeypatch, WORDS)
    first = searchwords.trending(_cfg(), tmp_path, TODAY)
    assert first["first_run"] and first["read"] == 5 and first["new"] == 5
    assert [r["term"] for r in first["terms"]][:1] == ["foam mirror"] and len(first["terms"]) == 4    # "trend" names nothing
    assert first["terms"][0]["note"] == 'TikTok search: "foam mirror tiktok trend"'
    _words(monkeypatch, [*WORDS, "mirror crush trend"])
    later = searchwords.trending(_cfg(), tmp_path, TODAY)
    assert not later["first_run"] and later["new"] == 1 and [r["term"] for r in later["terms"]] == ["mirror crush"]


def test_demand_is_the_name_with_ai_not_a_word_that_starts_like_it():
    got = ["hotel lobby ai", "hotel lobby ai video", "hotel lobby air diffuser", "hotel lobby design"]
    assert watch.demand("hotel lobby", got) == ["hotel lobby ai", "hotel lobby ai video"]
    assert watch.demand("bulin 47", ["bulin47 ai", "47 47 meaning"]) == ["bulin47 ai"]


def _day(monkeypatch, day):
    monkeypatch.setattr(watch, "date", type("D", (date,), {"today": staticmethod(lambda: day)}))


def _lead(term, kinds, named, known=""):
    return {"term": term, "kinds": kinds, "named": named, "known": known}


def test_judged_names_of_the_watched_kinds_join_and_are_looked_up_once_a_day(tmp_path, monkeypatch):
    cfg = _cfg()
    joined = watch.add(cfg, tmp_path, [_lead("foam mirror", ["searchwords"], 0.7), _lead("hurricane", ["searchwords"], 0.1),
                                       _lead("ozil goal", ["rising"], 0.9), _lead("hotel lobby", ["tiktok"], 0.8, known="hotel lobby")], TODAY)
    assert joined == 1                                               # a low score, an unwatched kind, a known name stay out
    asked = _google(monkeypatch, {})
    quiet = watch.check(cfg, tmp_path, TODAY)
    assert asked == ["foam mirror ai"] and quiet["terms"] == [] and quiet["watching"] == 1
    assert watch.check(cfg, tmp_path, TODAY)["read"] == 0 and len(asked) == 1        # once a day
    _google(monkeypatch, {"foam mirror ai": ["foam mirror ai video", "foam mirror ai trend", "foam mirror art"]})
    found = watch.check(cfg, tmp_path, date(2026, 10, 21))
    assert [r["term"] for r in found["terms"]] == ["foam mirror"] and found["watching"] == 0
    assert found["terms"][0]["note"] == 'Google completes "foam mirror ai video" (2 with ai, 2 days after it was first seen)'
    assert watch.check(cfg, tmp_path, date(2026, 10, 22))["read"] == 0                # found once, never again


def test_a_name_leaves_the_list_after_the_watch_days(tmp_path, monkeypatch):
    cfg = _cfg()
    watch.add(cfg, tmp_path, [_lead("foam mirror", ["searchwords"], 0.7)], TODAY)
    _google(monkeypatch, {})
    assert watch.check(cfg, tmp_path, date(2026, 11, 20))["watching"] == 0


def test_sources_pushes_a_trending_search_only_once_google_completes_it_with_ai(tmp_path, monkeypatch, capsys):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"lang": "en", "searchwords": {"on": True}, "watch": {"pause": 0},
                                    "skip": ["x", "hf", "tiktok", "rising", "pages"], "judge": {"model": "m", "min_score": 0.5}}))
    _words(monkeypatch, ["foam mirror tiktok trend", "Six Flags Closes Goliath"])
    scores = {"mirror": 0.8}

    def score(rows, model, focus="names"):
        for r in rows:
            r["named"] = scores["mirror"] if "mirror" in r["term"] else 0.1
        return {"judged": len(rows)}
    monkeypatch.setattr(report.judge, "score", score)
    pushed = []
    monkeypatch.setattr(notify, "feishu", lambda title, text: pushed.append((title, text)) or "feishu sent")
    _google(monkeypatch, {})
    _day(monkeypatch, TODAY)
    args = ["sources", "--config", str(cfg_path), "--state", str(tmp_path / "state"), "--feishu"]
    cli.main(args)
    assert pushed == []                                              # trending on TikTok, nobody searches it with ai yet
    _words(monkeypatch, ["foam mirror tiktok trend", "Six Flags Closes Goliath"])
    _google(monkeypatch, {"foam mirror ai": ["foam mirror ai video"]})
    _day(monkeypatch, date(2026, 10, 20))
    scores["mirror"] = 0.2         # judged again with Google's completions, it keeps the score it joined with
    cli.main(args)
    title, text = pushed[0]
    assert title == "New-term radar · 1 new" and text.startswith("1. **foam mirror**")
    assert 'Google completes "foam mirror ai video" (1 with ai, 1 days after it was first seen)' in text


def test_a_name_found_before_it_was_marked_reported_is_reported_once(tmp_path, monkeypatch):
    cfg = _cfg()
    watch.add(cfg, tmp_path, [_lead("foam mirror", ["searchwords"], 0.7)], TODAY)
    path = tmp_path / "watch.json.gz"
    kept = watch.snap.load(path)
    kept["foammirror"].update(found="2026-10-19", completions=["foam mirror ai video"])      # as an older run left it
    watch.snap.save(path, kept)
    _google(monkeypatch, {})
    again = watch.check(cfg, tmp_path, date(2026, 10, 20))
    assert [r["term"] for r in again["terms"]] == ["foam mirror"] and again["terms"][0]["floor"] == 0.7
    assert watch.check(cfg, tmp_path, date(2026, 10, 21))["terms"] == []
