"""The push: one card per trend, under its own name, on data, again only when it grew."""
from datetime import date

import pytest

from radar import core, pushes, report, store, taken

TODAY = date(2026, 10, 24)


def test_one_trend_under_two_names():
    assert pushes.same("toc toc", "my door toc toc") and pushes.same("toc toc dance", "toc trend toc toc")
    assert pushes.same("window peeper", "peeper guide window peeper") and pushes.same("hittheroad", "hit the road dude")
    assert pushes.same("learn this window peeper", "window peeper") and pushes.same("mr bean", "filtromrbean")
    assert not pushes.same("zombie", "zombie couple")          # one short word does not hold a longer name
    assert not pushes.same("anime eye", "anime star eye")      # nor words apart
    assert not pushes.same("broom riding", "witch broom crash") and not pushes.same("ai", "dance")


def test_the_nine_domains_of_a_name():
    assert taken.spellings("Dime Dime Baby") == [
        "dimedimebaby.com", "dimedimebaby.app", "dimedimebaby.org", "dimedimebabyai.com", "dimedimebabyai.app",
        "dimedimebabyai.org", "dimedimebabyvideo.com", "dimedimebabyvideo.app", "dimedimebabyvideo.org"]
    assert taken.spellings("インムキング") == []


def test_taken_counts_the_recent_registrations_only(monkeypatch):
    # as read on 24 October 2026; windowpeeper.com stands for an old registration, one form did not answer
    days = {"dimedimebaby.com": "2026-10-19", "dimedimebabyai.com": "2026-10-19", "dimedimebaby.org": "2026-10-20",
            "dimedimebabyvideo.app": None, "windowpeeper.com": "2011-03-02", "windowpeeperai.com": "2026-10-22"}
    monkeypatch.setattr(taken, "registered", lambda d: days.get(d, ""))
    got = taken.check(["dime dime baby", "window peeper"], 30, TODAY)
    assert got["dime dime baby"] == {"taken": 3, "checked": 8, "first": "2026-10-19"}
    assert got["window peeper"] == {"taken": 1, "checked": 9, "first": "2026-10-22"}


def test_the_models_answer_names_the_trend_and_flags_a_category():
    answer = ('ok [{"i": 0, "name": "Dime Dime Baby", "generic": false}, {"i": 1, "name": "halloween costume", "generic": true},'
              ' {"i": 7, "name": "x"}, {"i": 2}, {"i": 2, "name": ""}]')
    assert core.parse(answer, 3) == {0: {"name": "dime dime baby", "generic": False},
                                     1: {"name": "halloween costume", "generic": True}}
    assert core.parse("no json", 3) == {}


def test_a_trend_the_model_calls_known_goes_by_the_known_name_and_a_new_one_keeps_its_own():
    answer = ('[{"i": 0, "name": "broom crash", "same_as": "broom riding"}, {"i": 1, "name": "kda firestarter", "same_as": ""},'
              ' {"i": 2, "name": "x", "same_as": "not known"}, {"i": 3, "name": "", "same_as": "broom riding"}]')
    got = core.parse(answer, 4, ["broom riding"])
    assert {i: g["name"] for i, g in got.items()} == {0: "broom riding", 1: "kda firestarter", 2: "x"}


def test_the_model_sees_only_the_known_trends_that_share_a_word():
    rows = [{"term": "witch broom", "examples": ["how to fly on a broom"]}, {"term": "kda firestarter", "examples": []}]
    assert core._related(["broom riding", "dime dime baby", "toc toc", "letter k"], rows) == ["broom riding"]


def test_without_the_model_a_term_is_its_own_name():
    assert core.names([{"term": "bulin 47", "examples": []}], "m") == {"bulin 47": {"name": "bulin 47", "generic": False}}


def _row(term, kinds=("demand",), tiktok=None, curve=None, fmt="video"):
    return {"term": term, "kinds": list(kinds), "named": 0.8, "known": "", "format": fmt, "examples": [], "variants": [],
            "tiktok": tiktok, "curve": curve or {}}


@pytest.fixture
def world(cfg, monkeypatch):
    """The model's names and the registries' answers, as a test sets them."""
    w = {"names": {}, "generic": set(), "taken": {}}
    monkeypatch.setattr(core, "names", lambda rows, model, known=None: {
        r["term"]: {"name": w["names"].get(r["term"], r["term"]), "generic": r["term"] in w["generic"]} for r in rows})
    monkeypatch.setattr(taken, "check", lambda names, recent, today=None: {n: w["taken"][n] for n in names if n in w["taken"]})
    cfg["feishu"]["kinds"] = ["demand", "domain"]
    return w


def test_a_trend_is_pushed_once_under_its_name_on_data(cfg, tmp_path, world):
    world["names"] = {"baby wow karol g": "dime dime baby", "dancing and eating": "dime dime baby"}
    world["generic"] = {"halloween costume"}
    world["taken"] = {"dime dime baby": {"taken": 7, "checked": 9, "first": "2026-10-19"},
                      "jeanphil": {"taken": 3, "checked": 6, "first": "2026-10-06"}}
    tk = {"authors": 18, "plays": 664244, "since": "2026-10-14"}
    lead = [_row("baby wow karol g", tiktok=tk), _row("dancing and eating", tiktok={"authors": 11, "plays": 100, "since": None}),
            _row("halloween costume", tiktok=tk), _row("foam mirror"), _row("jeanphil"),
            _row("fading thing", curve={"now": "fading"}, tiktok=tk)]
    chosen, held = pushes.select(cfg, tmp_path, lead, TODAY)
    # a name the model calls a category is pushed on its data all the same, flagged
    assert [(g["name"], g["status"], g["terms"], g["generic"]) for g in chosen] == [
        ("dime dime baby", "new", ["baby wow karol g", "dancing and eating"], False),
        ("halloween costume", "new", ["halloween costume"], True)]
    assert chosen[0]["tiktok"] == tk                                    # the best numbers of its terms
    assert "<font color='grey'>maybe a category</font>" in pushes.card(chosen[1], {})[0]
    assert held == {"no_data": ["foam mirror"], "over": ["jeanphil", "fading thing"], "pushed": []}
    again, held = pushes.select(cfg, tmp_path, [_row("dime dime baby", tiktok=tk)], TODAY)
    assert again == [] and held["pushed"] == ["dime dime baby"]         # the same numbers: not again


def test_a_new_page_on_a_hand_picked_list_is_pushed_on_its_own(cfg, tmp_path, world):
    lead = [{**_row("ceiling fan", kinds=("pages",)), "curated": "tryatrend"}, _row("fire text", kinds=("pages",))]
    chosen, _ = pushes.select(cfg, tmp_path, lead, TODAY)
    assert [g["name"] for g in chosen] == ["ceiling fan"]                    # Dreamina's page alone is not pushed
    assert pushes.card(chosen[0], {})[1] == "new on tryatrend"


def test_a_trend_is_pushed_again_when_it_grew(cfg, tmp_path, world):
    world["taken"] = {"window peeper": {"taken": 1, "checked": 9, "first": "2026-10-22"}}
    pushes.select(cfg, tmp_path, [_row("window peeper", tiktok={"authors": 3, "plays": 70000, "since": "2026-10-20"})], date(2026, 10, 21))
    big = {"authors": 18, "plays": 664244, "since": "2026-10-20"}
    chosen, _ = pushes.select(cfg, tmp_path, [_row("learn this window peeper", tiktok=big)], date(2026, 10, 23))
    assert [(g["name"], g["status"], g["terms"]) for g in chosen] == [("window peeper", "up", ["learn this window peeper"])]
    lines = pushes.card(chosen[0], {})
    assert lines[0] == "**[window peeper](https://www.tiktok.com/search/video?q=window%20peeper%20ai)**  " \
                       "<font color='orange'>📈 growing</font> 🎬 video"
    assert lines[1] == "first pushed 10/21 · accounts 3→18 · plays 70k→664k · domains 1/9 taken (since 10/22) · caught as learn this window peeper"
    assert pushes.select(cfg, tmp_path, [_row("window peeper", tiktok=big)], date(2026, 10, 24))[0] == []


def test_the_first_ledger_holds_what_was_pushed_before(cfg, tmp_path, world):
    conn = store.connect(tmp_path)
    store.record(conn, [{"term": "toc toc", "kinds": ["demand"], "signals": ["s"], "named": 0.8, "variants": []},
                        {"term": "letter k", "kinds": ["searchwords"], "signals": ["s"], "named": 0.8, "variants": []}],
                 date(2026, 10, 21))
    tk = {"authors": 10, "plays": 2411926, "since": "2026-10-03"}
    chosen, held = pushes.select(cfg, tmp_path, [_row("toc trend toc toc", tiktok=tk), _row("letter k", tiktok=tk)], TODAY)
    assert [g["name"] for g in chosen] == ["letter k"] and held["pushed"] == ["toc toc"]   # numbers kept, not compared


def test_the_card_has_two_lines_of_numbers(cfg, tmp_path, world, monkeypatch):
    world["names"] = {"baby wow karol g": "dime dime baby"}
    world["taken"] = {"dime dime baby": {"taken": 7, "checked": 9, "first": "2026-10-19"}}
    monkeypatch.setattr(pushes.covered, "dreamina", lambda state, names: {})
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_REPOSITORY", "me/radar")
    lead = [_row("baby wow karol g", tiktok={"authors": 18, "plays": 664244, "since": "2026-10-14"}, curve={"now": "rising"})]
    title, text = pushes.push(cfg, tmp_path, lead, {}, TODAY)
    assert title == "New-term radar · 1 new · 0 growing"
    assert text == ("**[dime dime baby](https://www.tiktok.com/search/video?q=dime%20dime%20baby%20ai)**  "
                    "<font color='green'>🆕 new</font> 🎬 video <font color='blue'>rising</font>\n"
                    "AI versions since 10/14 · 18 accounts, 664k plays · domains 7/9 taken (since 10/19) · caught as baby wow karol g\n"
                    "\n[Full report](https://github.com/me/radar/actions/runs/42)")


def test_push_is_quiet_without_news_and_speaks_up_when_any_source_fails(cfg, tmp_path, world):
    assert pushes.push(cfg, tmp_path, [], {"domain": {"terms": []}}, TODAY) is None
    title, text = pushes.push(cfg, tmp_path, [], {"domain": {"error": "OSError: timed out", "terms": []}}, TODAY)
    assert title == "New-term radar · a source failed" and "③ new domains: OSError: timed out" in text
    # a source that only feeds the watch list says so too
    title, text = pushes.push(cfg, tmp_path, [], {"searchwords": {"error": "AisaError: no trending search words"}}, TODAY)
    assert "AisaError: no trending search words" in text


def test_a_blocklisted_term_is_never_pushed(cfg, tmp_path, world, monkeypatch):
    monkeypatch.setattr(report.judge, "score", lambda rows, model, focus="names": {"judged": 0})
    cfg["blocklist"] = ["huangguo"]
    block = {"terms": [{"term": t, "note": "New domains: 5", "examples": [f"{t.replace(' ', '')}.ai"]} for t in ("huangguo", "bulin 47")]}
    lead, _ = report.leads(cfg, {"domain": block})
    chosen, _ = pushes.select(cfg, tmp_path, lead, TODAY)
    assert [g["name"] for g in chosen] == ["bulin 47"]                  # a wave of new domains is data enough
