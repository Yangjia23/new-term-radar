"""Signal ① searchwords (TikTok's trending searches) and the watch list (Google's autocomplete). No network."""
import copy
import json
from datetime import date, timedelta

import pytest

from radar import __main__ as cli
from radar import config, notify, pushes, report, searchwords, watch

TODAY = date(2026, 10, 19)
WORDS = ["foam mirror tiktok trend", "Bulin 47’s Freestyle Surpasses 50M Views", "Hell Nah Cuh TikTok Meme",
         "Testimony Opens in Matthew Farwell Trial", "trend"]


REAL_FRESH = watch.fresh      # kept before the fixture below stands in for it
NEW = {"no_data": False, "new": True, "rose": True, "started": "2026-10-12", "now": "rising"}
OLD = {"no_data": False, "new": False, "rose": False, "now": "flat"}


@pytest.fixture(autouse=True)
def curves(monkeypatch):
    """Every name Google completes reads as new in Trends, unless a test says otherwise."""
    by_term = {}
    monkeypatch.setattr(watch, "fresh", lambda terms, today: ({k: by_term.get(k, NEW) for k in terms}, 1200))
    return by_term


@pytest.fixture(autouse=True)
def tiktok(monkeypatch):
    """No name has AI versions on TikTok, unless a test says otherwise; the names searched are kept."""
    found, asked = {}, []
    monkeypatch.setattr(watch, "tiktok", lambda terms, n: (asked.extend(terms) or {k: found.get(k) for k in terms}, 1500 * len(terms)))
    return found, asked


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
    assert found["terms"][0]["note"] == 'Strong: Google completes "foam mirror ai video" (2 with ai, 2 days after it was first seen) · rising since 10-12, still rising'
    assert watch.check(cfg, tmp_path, date(2026, 10, 22))["read"] == 0                # found once, never again


def test_a_name_leaves_the_list_after_the_watch_days(tmp_path, monkeypatch):
    cfg = _cfg()
    watch.add(cfg, tmp_path, [_lead("foam mirror", ["searchwords"], 0.7)], TODAY)
    _google(monkeypatch, {})
    assert watch.check(cfg, tmp_path, date(2026, 10, 30))["watching"] == 0          # 11 days on


def test_names_under_the_watch_score_stay_out_and_leave_when_it_is_raised(tmp_path, monkeypatch):
    cfg = _cfg()
    assert watch.add(cfg, tmp_path, [_lead("moo doja cat", ["searchwords"], 0.4), _lead("foam mirror", ["searchwords"], 0.7)], TODAY) == 1
    cfg["watch"]["min_score"] = 0.3
    watch.add(cfg, tmp_path, [_lead("moo doja cat", ["searchwords"], 0.4)], TODAY)
    _google(monkeypatch, {})
    assert watch.check(cfg, tmp_path, TODAY)["watching"] == 2
    cfg["watch"]["min_score"] = 0.6
    assert watch.check(cfg, tmp_path, TODAY)["watching"] == 1


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
    assert pushed == []            # searched with ai, but no AI versions on TikTok and none of its domains taken
    _taken(monkeypatch, {"foam mirror": {"taken": 3, "checked": 9, "first": "2026-10-18"}})
    _google(monkeypatch, {"foam mirror ai": ["foam mirror ai video"]})
    tmp = tmp_path / "state" / "watch.json.gz"
    kept = watch.snap.load(tmp)
    kept["foammirror"].update(found=None, checked=None)      # looked up afresh, now that its domains are taken
    watch.snap.save(tmp, kept)
    cli.main(args)
    title, text = pushed[0]
    assert title == "New-term radar · 1 new · 0 growing"
    assert text.startswith("**[foam mirror](https://www.tiktok.com/search/video?q=foam%20mirror%20ai)**  <font color='green'>🆕 new</font> 🎬 video")
    assert "\ndomains 3/9 taken (since 10/18)" in text and "score" not in text


def test_a_name_searched_for_months_is_set_aside_as_old_and_never_pushed(tmp_path, monkeypatch, curves):
    cfg = _cfg()
    watch.add(cfg, tmp_path, [_lead("reporter voice", ["searchwords"], 0.6), _lead("foam mirror", ["searchwords"], 0.7)], TODAY)
    _google(monkeypatch, {"reporter voice ai": ["reporter voice ai", "news reporter voice ai"], "foam mirror ai": ["foam mirror ai video"]})
    curves["reporter voice"] = OLD
    got = watch.check(cfg, tmp_path, TODAY)
    assert [r["term"] for r in got["terms"]] == ["foam mirror"] and got["old"] == ["reporter voice"] and got["cost_micros"] == 1200
    assert watch.check(cfg, tmp_path, date(2026, 10, 20))["read"] == 0               # old: not looked up again


def test_too_few_searches_for_a_curve_is_pushed_and_says_so(tmp_path, monkeypatch, curves):
    cfg = _cfg()
    watch.add(cfg, tmp_path, [_lead("bulin 47", ["searchwords"], 0.8)], TODAY)
    _google(monkeypatch, {"bulin 47 ai": ["bulin 47 ai"]})
    curves["bulin 47"] = {"no_data": True}
    note = watch.check(cfg, tmp_path, TODAY)["terms"][0]["note"]
    assert note.endswith(" · too few searches for a Trends curve yet")


def test_a_failed_trends_lookup_tries_again_tomorrow(tmp_path, monkeypatch):
    cfg = _cfg()
    watch.add(cfg, tmp_path, [_lead("foam mirror", ["searchwords"], 0.7)], TODAY)
    _google(monkeypatch, {"foam mirror ai": ["foam mirror ai video"]})

    def down(terms, today):
        raise watch.aisa.AisaError("HTTP 502")
    monkeypatch.setattr(watch, "fresh", down)
    got = watch.check(cfg, tmp_path, TODAY)
    assert got["terms"] == [] and got["errors"] == ["Trends: HTTP 502"] and got["watching"] == 1
    monkeypatch.setattr(watch, "fresh", lambda terms, today: ({k: NEW for k in terms}, 0))
    assert [r["term"] for r in watch.check(cfg, tmp_path, date(2026, 10, 20))["terms"]] == ["foam mirror"]


def _trends(values, end):
    days = [end - timedelta(days=len(values) - 1 - i) for i in range(len(values))]
    return {"tasks": [{"result": [{"items": [{"data": [{"date_from": d.isoformat(), "values": [v]} for d, v in zip(days, values)]}]}]}]}


def test_fresh_tells_a_new_rise_from_a_meme_of_may(monkeypatch):
    end = TODAY
    new = [0] * 75 + [0, 2, 5, 12, 30, 55, 80, 100, 95, 90, 88, 85, 80, 70, 0]     # rising since about 10-08
    may = [100, 90, 70, 60, 50, 45, 40, 38, 35, 30] + [25] * 65 + [22] * 15          # searched long before, fading
    song = [30, 28, 32, 29, 31] * 18                                                   # "burning bridges": a song, searched all year
    answers = {"evan walk dance ai": new, "evan walk dance": may, "hotel lobby ai": may, "hotel lobby": may,
               "burning bridges ai": new, "burning bridges": song, "letter k ai": [0] * 90, "letter k": song}
    monkeypatch.setattr(watch.aisa, "call_all", lambda calls: (
        {c["call_id"]: _trends(answers[c["arguments"]["body"][0]["keywords"][0]], end) for c in calls}, 1200 * len(calls)))
    got, cost = REAL_FRESH(["evan walk dance", "hotel lobby", "burning bridges", "letter k"], TODAY)
    assert got["evan walk dance"]["new"] and got["evan walk dance"]["asked"] == "evan walk dance ai"
    assert got["burning bridges"]["new"]                                              # the phrase is old, "... ai" is new
    assert not got["hotel lobby"].get("new")
    assert got["letter k"]["asked"] == "letter k" and not got["letter k"].get("new")  # "... ai" too small: the name decides
    assert cost == 9600


def test_one_day_of_searches_out_of_nothing_is_a_first_spike():
    spike = {"no_data": False, "new": False, "rose": False, "base": 0, "peak": 100, "peak_day": "2026-10-15", "now": "flat"}
    assert watch._spike(spike, TODAY)["new"] and watch._spike(spike, TODAY)["now"] == "spike"
    assert not watch._spike({**spike, "base": 42}, TODAY)["new"]                   # searched before
    assert not watch._spike({**spike, "peak_day": "2026-08-01"}, TODAY)["new"]      # an old peak
    # "reporter voice ai": one spike on 09-14, zeros since; the window's "peak" is a zero
    assert not watch._spike({**spike, "base": 1.8, "peak": 0, "peak_day": "2026-10-17"}, TODAY)["new"]


def test_a_completion_naming_a_template_is_strong_the_name_alone_is_weak(tmp_path, monkeypatch):
    assert watch.strong(["hotel lobby ai video", "hotel lobby ai"]) and watch.strong(["burning bridges ai video generator free"])
    assert not watch.strong(["bulin 47 ai"]) and not watch.strong(["reporter voice ai", "news reporter voice ai"])
    cfg = _cfg()
    watch.add(cfg, tmp_path, [_lead("bulin 47", ["searchwords"], 0.8)], TODAY)
    _google(monkeypatch, {"bulin 47 ai": ["bulin 47 ai", "47 47 meaning"]})
    weak = watch.check(cfg, tmp_path, TODAY)["terms"][0]
    assert not weak["strong"] and weak["note"].startswith('Weak: Google completes only "bulin 47 ai"')


def test_the_hourly_job_pushes_demand_and_nothing_else(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"lang": "en", "searchwords": {"on": True}, "watch": {"pause": 0},
                                    "feishu": {"heartbeat": True}, "judge": {"model": "m", "min_score": 0.5}}))
    monkeypatch.setattr(report.judge, "score", lambda rows, model, focus="names": [
        r.__setitem__("named", 0.8) for r in rows] and {"judged": len(rows)})
    pushed = []
    monkeypatch.setattr(notify, "feishu", lambda title, text: pushed.append((title, text)) or "feishu sent")
    args = ["searchwords", "--config", str(cfg_path), "--state", str(tmp_path / "state"), "--feishu"]
    _words(monkeypatch, ["foam mirror tiktok trend"])
    _google(monkeypatch, {})
    _day(monkeypatch, TODAY)
    cli.main(args)
    assert pushed == []                                              # a new name, watched: no push, no heartbeat
    _google(monkeypatch, {"foam mirror ai": ["foam mirror ai filter"]})
    _taken(monkeypatch, {"foam mirror": {"taken": 4, "checked": 9, "first": "2026-10-19"}})
    _day(monkeypatch, date(2026, 10, 20))
    cli.main(args)
    assert len(pushed) == 1 and "**[foam mirror]" in pushed[0][1] and "<font color='blue'>rising</font>" in pushed[0][1]


def _taken(monkeypatch, found):
    monkeypatch.setattr(pushes.taken, "check", lambda names, recent, today=None: {n: found[n] for n in names if n in found})


def _video(author, desc, plays=1000):
    return {"aweme_info": {"create_time": 1792400000, "desc": desc, "author": {"unique_id": author},
                           "statistics": {"play_count": plays}}}


# Captions of 19 October 2026, for the TikTok search "dime dime baby ai" of the last week.
DIME = {"data": {"search_item_list": [
    _video("bella.moore54", "baby wow karol g dance trend bby wow guy dancing and eating original dime dime baby ai tutorial", 185122),
    _video("lucy.bruce_win", "dime dime baby ai tutorial dime dime baby ai dance dime dime baby ai video", 580033),
    _video("xqh626", "✨How to create the viral AI effect for the original Dime Dime Baby dance✨"),
    _video("jcwb3u5", "#capcut #capcutpioneer dime dime baby ai tutorial dime dime baby ai dance"),
    _video("zane.mercer4", "dime dime baby", 9143922),                     # the original clip: no AI in it
    _video("cook", "best ai recipe tutorial for dinner"),                   # AI, but of something else
]}}


def test_ai_versions_go_by_the_name_their_captions_give():
    videos = watch._videos(DIME)
    assert len(videos) == 5                                                   # the original clip is not an AI version
    found = watch.ai_versions("baby wow karol g", videos, 3)
    assert found["name"] == "dime dime baby" and found["authors"] == 4 and found["plays"] == 185122 + 580033 + 2000
    assert watch.ai_versions("dime dime baby", videos, 3)["name"] == "dime dime baby"
    assert watch.ai_versions("dime dime baby", videos, 5) is None              # too few accounts
    assert watch.ai_versions("foam mirror", videos, 1) is None                # not named at all


def test_names_scored_high_are_searched_on_tiktok_and_pushed_under_the_ai_name(tmp_path, monkeypatch, tiktok):
    found, asked = tiktok
    cfg = _cfg()
    watch.add(cfg, tmp_path, [_lead("baby wow karol g", ["searchwords"], 0.7), _lead("foam mirror", ["searchwords"], 0.6)], TODAY)
    _google(monkeypatch, {})
    found["baby wow karol g"] = watch.ai_versions("baby wow karol g", watch._videos(DIME), 3)
    out = watch.check(cfg, tmp_path, TODAY)
    assert asked == ["baby wow karol g"] and out["tiktok_read"] == 1          # foam mirror is under tiktok_min
    (r,) = out["terms"]
    assert r["term"] == "dime dime baby" and r["strong"] and r["floor"] == 0.7 and "baby wow karol g" in r["variants"]
    assert r["note"].startswith("AI versions on TikTok: 4 accounts") and 'watched as "baby wow karol g"' in r["note"]
    assert out["cost_micros"] == 1500
    again = watch.check(cfg, tmp_path, TODAY + timedelta(days=1))
    assert again["terms"] == [] and asked == ["baby wow karol g"]             # pushed once, not searched again


def test_ai_versions_with_few_plays_wait_for_the_next_day(tmp_path, monkeypatch, tiktok):
    found, asked = tiktok
    cfg = _cfg()
    watch.add(cfg, tmp_path, [_lead("bow bow bow", ["searchwords"], 0.8)], TODAY)
    _google(monkeypatch, {})
    found["bow bow bow"] = {"name": "bow bow bow", "authors": 3, "videos": 3, "plays": 7559, "example": "@a: x"}
    assert watch.check(cfg, tmp_path, TODAY)["terms"] == []                  # under 100,000 plays
    found["bow bow bow"]["plays"] = 150_000
    (r,) = watch.check(cfg, tmp_path, TODAY + timedelta(days=1))["terms"]
    assert r["term"] == "bow bow bow" and asked == ["bow bow bow", "bow bow bow"]


def test_a_name_without_ai_versions_is_searched_on_tiktok_once_a_day(tmp_path, monkeypatch, tiktok):
    _, asked = tiktok
    cfg = _cfg()
    watch.add(cfg, tmp_path, [_lead("toc toc", ["searchwords"], 0.8)], TODAY)
    _google(monkeypatch, {})
    assert watch.check(cfg, tmp_path, TODAY)["terms"] == []
    watch.check(cfg, tmp_path, TODAY)
    watch.check(cfg, tmp_path, TODAY + timedelta(days=1))
    assert asked == ["toc toc", "toc toc"]


def test_names_never_searched_on_tiktok_go_first(tmp_path, monkeypatch, tiktok):
    _, asked = tiktok
    cfg = _cfg()
    cfg["watch"]["tiktok_max"] = 2
    watch.add(cfg, tmp_path, [_lead("old one", ["searchwords"], 0.8), _lead("old two", ["searchwords"], 0.8)], TODAY)
    _google(monkeypatch, {})
    watch.check(cfg, tmp_path, TODAY)
    watch.add(cfg, tmp_path, [_lead("broom riding", ["templates"], 0.8)], TODAY)
    asked.clear()
    watch.check(cfg, tmp_path, TODAY + timedelta(days=1))
    assert asked[0] == "broom riding"                      # new, ahead of the two searched yesterday


def test_ai_music_is_not_an_ai_version_and_a_search_is_cut_before_ai():
    song = {"data": {"search_item_list": [_video(a, "best ai song??? #slowedaudios #comebackandback") for a in "abc"]}}
    assert watch._videos(song) == []                         # AI music, not a video template
    assert searchwords.name("steppin ai dance tutorial") == "steppin"
