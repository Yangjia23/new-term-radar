"""Signal ① templates: the hashtags of TikTok's AI template sellers. No network."""
import copy
from datetime import date, timedelta

from radar import config, templates

TODAY = date(2026, 10, 21)


def _video(author, desc, tags, plays=1000):
    return {"aweme_info": {"create_time": 1792500000, "desc": desc, "author": {"unique_id": author},
                           "statistics": {"play_count": plays},
                           "text_extra": [{"hashtag_name": t} for t in tags]}}


# Videos of 21 October 2026 for "ai dance tutorial" and "#capcutpioneer ai", as TikHub returns them.
ANSWERS = {
    "q0": {"data": {"search_item_list": [
        _video("hope48817", "#capcut #capcutpioneer toc toc trend toc toc ai dance how to make toc toc ai dance",
               ["capcut", "capcutpioneer", "toctoctrend", "aidancetutorial"]),
        _video("wren42841", "toc toc trend toc toc ai dance", ["toctoc", "capcutforus", "fyp"]),
        _video("kspjw7xc66", "✨Cómo crear el efecto viral de IA del baile original Dime Dime Baby✨",
               ["tendenciadimedimebaby", "capcutmaster"], 70122),
    ]}},
    "q1": {"data": {"search_item_list": [
        _video("gqt9daub36", "✨Cómo crear el efecto viral de IA del baile original Dime Dime Baby✨",
               ["bailedimedimebaby", "dimedimebaby", "capcutmaster"], 74271),
        _video("ruben.merimi", "how to make my ride is here broom trend", ["capcutpioneer", "broomridingtrend"]),
        _video("hope48817", "toc toc again", ["toctocdance"]),                    # the same account once more
    ]}},
}


def _cfg():
    c = copy.deepcopy(config.DEFAULTS)
    c["templates"]["on"] = True
    return c


def test_a_hashtag_is_cut_to_the_trend_it_names():
    assert templates.core("tendenciadimedimebaby") == templates.core("bailedimedimebaby") == "dimedimebaby"
    assert templates.core("toctoctrend") == templates.core("toctocdance") == "toctoc"
    assert templates.core("broomridingtrend") == "broomriding"
    for tag in ("capcutforus", "capcutmaster", "trendingtiktok", "fyp🎵", "aidancetutorial", "nhachaymoingay", "capcut102"):
        assert not templates.named(tag, templates.core(tag)), tag
    assert templates.written("dimedimebaby", ["original Dime Dime Baby dance", "#dimedimebaby"]) == "dime dime baby"
    assert templates.written("broomriding", ["my ride is here broom trend"]) == "broomriding"   # no caption writes it


def test_names_two_accounts_use_are_reported_once(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(templates.aisa, "call_all", lambda c: calls.append(c) or (ANSWERS, 7000))
    out = templates.trending(_cfg(), tmp_path, TODAY)
    assert len(calls[0]) == len(templates.QUERIES) and calls[0][0]["arguments"]["publish_time"] == 1
    by = {r["term"]: r for r in out["terms"]}
    assert set(by) == {"toc toc", "dime dime baby"}                    # broom riding: one account so far
    assert by["dime dime baby"]["note"].startswith("TikTok template sellers: 2 accounts")
    assert out["read"] == 6 and out["cost_micros"] == 7000
    assert templates.trending(_cfg(), tmp_path, TODAY)["terms"] == []     # reported once
    more = {"q0": {"data": {"search_item_list": [_video("svkqg8", "broom riding ai", ["broomridingtrend"])]}}}
    monkeypatch.setattr(templates.aisa, "call_all", lambda c: (more, 1000))
    later = templates.trending(_cfg(), tmp_path, TODAY + timedelta(days=1))
    assert [r["term"] for r in later["terms"]] == ["broom riding"]     # a second account, the next day


def test_off_unless_the_config_turns_it_on(tmp_path):
    assert templates.trending(copy.deepcopy(config.DEFAULTS), tmp_path, TODAY) == {"skipped": True}
