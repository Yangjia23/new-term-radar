"""Signal ③ domains, the Feishu push and the keyword table's names-only mode. No network:
the lists and the Feishu API are stand-ins."""
import copy
import json
from datetime import date, timedelta

from radar import __main__ as cli
from radar import config, domains, notify, report, sites, usecases

C = copy.deepcopy(config.DEFAULTS["domains"])
TODAY = date(2026, 10, 16)

# Part of what was registered for the trends of September and October 2026, and bystanders.
WAVE = """hotellobby.ai hotellobby.app hotellobbyai.com hotellobbyai.net hotel-lobby.org aihotellobby.art hotellobbyfilter.com
bulin47.ai bulin47ai.link bulin-47-ai.net bulin-47-video.com bulin47.io
rumpelstiltskin.ai rumpelstiltskinai.com rumpelstiltskin.app rumplestiltskinai.com
zombielovestory.app zombielovestory.com zombielovestory.net zombieai.app zombieai.com zombieai.net
raindance.com raindance.net raindance.org
casibombet.app casibombet.bet casibombet.net
kaylachristinemedia.com kaylachristinemedia.org""".split()


def test_cut_takes_the_intent_words_off_and_keeps_the_name_as_written():
    assert domains.cut("burning-bridges-ai-video.com") == ("burningbridges", True, "burning bridges")
    assert domains.cut("thebulin47video.com") == ("bulin47", True, None)
    assert domains.cut("bulin47.ai") == ("bulin47", True, None)            # the .ai TLD is intent too
    assert domains.cut("bulin-47-ia.online") == ("bulin47", True, "bulin 47")


def test_cut_does_not_find_ai_inside_a_word():
    assert domains.cut("raindance.com") == ("raindance", False, None)      # r-ai-ndance
    assert domains.cut("kaylachristinemedia.com")[:2] == ("kaylachristinemedia", False)   # medi-a, not "ia"


def test_near_spellings():
    assert domains._near("rumplestiltskin", "rumpelstiltskin")             # two letters swapped
    assert domains._near("hotellobby", "hotellobbys") and not domains._near("hotellobby", "hotellobbyai")


def test_find_reports_the_waves_and_attaches_their_variants():
    rows = {r["core"]: r for r in domains.find([domains.group(WAVE)], [], C)}
    assert rows["hotellobby"]["term"] == "hotel lobby" and rows["hotellobby"]["domains"] == 7      # hotellobbyfilter.com among them
    assert rows["bulin47"]["term"] == "bulin 47" and rows["bulin47"]["intent"] == 4                # all but bulin47.io
    assert rows["rumpelstiltskin"]["domains"] == 4                            # with the misspelling
    assert "rumplestiltskin" not in rows and "hotellobbyfilter" not in rows
    assert "kaylachristinemedia" not in rows                                  # two domains, no intent word


def test_find_puts_waves_with_ai_or_video_first():
    order = [r["core"] for r in domains.find([domains.group(WAVE)], [], C)]
    assert order.index("casibombet") > order.index("bulin47") and order.index("raindance") > order.index("hotellobby")


def test_an_everyday_word_needs_a_burst_and_a_new_one_keeps_apart_from_it():
    everyday = {"zombie": [f"zombie{i}.xyz" for i in range(3)]}
    history = [everyday] * 10                                                # three zombie domains a day for ten days
    rows = {r["core"]: r for r in domains.find([domains.group(WAVE)], history, C)}
    assert "zombie" not in rows                                              # three a day is its usual
    assert rows["zombielovestory"]["domains"] == 3                          # not swallowed by it


def test_an_everyday_word_takes_no_variants():
    world = ["world.ai", "world.app", "worldai.com"] + [f"world{w}.com" for w in ("sbykai", "wide", "class", "news", "maps", "cup", "tour")]
    row = next(r for r in domains.find([domains.group(world)], [], C) if r["core"] == "world")
    assert row["domains"] == 3                                               # its own three, not worldsbykai and the rest


def test_a_list_is_labelled_with_the_days_its_domains_were_registered(monkeypatch):
    when = {f"d{i}.com": day for i, day in enumerate(["2026-10-10"] * 5 + ["2026-10-11"] * 2 + ["2023-10-12"])}
    monkeypatch.setattr(domains, "registered", lambda d: when.get(d))
    assert domains.days_of("2026-10-13", list(when) + ["x.net"]) == ["2026-10-10", "2026-10-11"]   # not the 2023 one
    assert domains.span(["2026-10-10", "2026-10-11"]) == "10-10~10-11" and domains.span(["2026-10-14"]) == "10-14"


def test_diff_keeps_each_list_reports_once_and_survives_a_bad_day(tmp_path, monkeypatch):
    cfg = {"domains": C}
    monkeypatch.setattr(domains, "days_of", lambda day, listed: [(date.fromisoformat(day) - timedelta(days=2)).isoformat()])
    monkeypatch.setattr(sites, "look", lambda host: "")
    lists = {"2026-10-14": "u1", "2026-10-15": "u2", "2026-10-16": "u3"}
    monkeypatch.setattr(domains, "available", lambda: lists)
    monkeypatch.setattr(domains, "download", lambda url: WAVE if url == "u3" else ["quiet.com"])
    first = domains.diff(cfg, tmp_path, TODAY)
    assert first["first_run"] and first["read"] == list(lists) and first["window"] == list(lists)
    assert {r["core"] for r in first["terms"]} >= {"hotellobby", "bulin47"} and first["terms"][0]["first_day"] == "2026-10-16"
    assert first["terms"][0]["registered"] == "10-14" and first["terms"][0]["note"].endswith("registered 10-14")
    again = domains.diff(cfg, tmp_path, TODAY)
    assert again["read"] == [] and again["terms"] == []                     # kept on disk, and reported already
    (tmp_path / "domains" / "registered.json.gz").unlink()
    assert domains.diff(cfg, tmp_path, TODAY)["registered"]["2026-10-16"] == ["2026-10-14"]   # measured from what was kept

    def broken(url):
        raise OSError("timed out")
    monkeypatch.setattr(domains, "available", lambda: {**lists, "2026-10-17": "u4"})
    monkeypatch.setattr(domains, "download", broken)
    late = domains.diff(cfg, tmp_path, TODAY + timedelta(days=1))
    assert "2026-10-17: OSError: timed out" in late["errors"][0] and late["window"] == list(lists)


# Two of the eight domains registered for "flying car" from 16 to 17 October 2026, as their home pages read on the 20th.
PAGES = {
    "flyingcarai.art": '<title>Flying Car AI &ndash; Launch Your Car Off the Viral Ramp From One Photo</title>'
                       '<meta name="description" content="Upload one photo and get the stunt video in minutes.">',
    "flyingcar.dev": "<title>flyingcar.dev for sale | Spaceship.com</title>",
}


def test_a_site_is_a_tool_when_its_page_names_the_word_and_an_ai_tool():
    assert sites.head(PAGES["flyingcarai.art"]).startswith("Flying Car AI – Launch Your Car")
    assert sites.tool("flyingcar", sites.head(PAGES["flyingcarai.art"]))
    assert sites.tool("flyingcar", "Flying Car AI Video Generator | Ramp Stunt from a Photo")
    assert not sites.tool("flyingcar", sites.head(PAGES["flyingcar.dev"]))          # parked for sale
    assert not sites.tool("flyingcar", "AllFlyingCars: Flying Car Prices and Release Dates")
    assert not sites.tool("hotellobby", "Flying Car AI Video Generator")          # a tool, for another word


def test_a_live_tool_makes_a_wave_strong_and_ai_domains_alone_do_not(tmp_path, monkeypatch):
    monkeypatch.setattr(sites, "look", lambda host: sites.head(PAGES.get(host, "")))
    rows = [{"core": "flyingcar", "intent": 2, "note": "n", "examples": ["flyingcar.dev", "flyingcarai.art"]},
            {"core": "crazyfrog", "intent": 2, "note": "n", "examples": ["crazyfrogai.pro"]},
            {"core": "boxtruck", "intent": 0, "note": "n", "examples": ["boxtruck.now"]}]
    errors = []
    assert domains._look({"domains": C}, tmp_path, rows, [], {}, TODAY, errors) == []
    car, frog, truck = rows
    assert car["floor"] == domains.SITE_FLOOR and car["strong"] and car["examples"][0] == "flyingcarai.art"
    assert "flyingcarai.art" in car["note"] and "Flying Car AI" in car["note"]
    assert "floor" not in frog and frog["note"] == "n" and "floor" not in truck and errors == []


# Single new domains of the list of 20 October 2026 and their titles on the 21st.
TITLES = {
    "thrillerdanceai.com": "Thriller Dance AI Video Generator - Lead the Zombie Dance",
    "teslaroadsteraivideo.fun": "Tesla Roadster AI Video Generator | Custom Flying Car Videos",
    "catclappingai.org": "Cat Clapping AI – Turn Your Pet Into the Clapping Cat Meme",
    "zombieaimaker.com": "Zombie Filter – Turn Your Photo into a Zombie with AI | Zombie AI",
    "stoneai.co.in": "StoneAI — AI Website Builder",
    "proxlai.com": "Proxlai: prices for every AI API",
    "aivsgames.com": "AI Playing Video Games: Records & Leaderboards",
    "memevideomaker.com": "Meme Video Maker: Create Short AI Videos from Photos",
    "nsfwphototovideo.com": "NSFW Photo to Video · AI Image to Video Generator, 18+",
    "toctocaidance.com": "",
}


def test_a_single_site_names_its_trend_from_its_title():
    name = lambda host: sites.name(domains.cut(host, 5)[0], TITLES[host])
    assert name("thrillerdanceai.com") == ("thriller dance", "thrillerdance")
    assert name("teslaroadsteraivideo.fun") == ("tesla roadster", "teslaroadster")
    assert name("catclappingai.org") == ("cat clapping", "catclapping")
    assert name("zombieaimaker.com") == ("zombie", "zombie")
    for host in ("stoneai.co.in", "proxlai.com", "aivsgames.com", "memevideomaker.com", "nsfwphototovideo.com"):
        assert name(host) is None, host
    assert sites.name("toctocaidance", "Toc Toc AI Video Generator | Toc Toc Dance from One Photo") == ("toc toc", "toctoc")


def test_single_sites_of_todays_lists_are_leads_and_a_silent_one_is_read_again(tmp_path, monkeypatch):
    monkeypatch.setattr(sites, "look", lambda host: TITLES.get(host, ""))
    fresh = [domains.group(list(TITLES) + ["raindance.com", "quiet.com"], 5)]
    assert domains.candidate("toctocaidance.com", 5) and not domains.candidate("raindance.com", 5)
    reported = {"catclapping": "2026-10-10"}
    out = domains._look({"domains": C}, tmp_path, [], fresh, reported, TODAY, [])
    by = {r["term"]: r for r in out}
    assert set(by) == {"thriller dance", "tesla roadster", "zombie"}       # cat clapping was reported already
    r = by["thriller dance"]
    assert r["strong"] and r["floor"] == domains.SITE_FLOOR and r["examples"] == ["thrillerdanceai.com"]
    assert "Thriller Dance AI Video Generator" in r["note"] and reported["thrillerdance"] == TODAY.isoformat()
    later = TODAY + timedelta(days=C["site_retry_days"])
    TITLES["toctocaidance.com"] = "Toc Toc AI Video Generator | Toc Toc Dance from One Photo"
    assert domains._look({"domains": C}, tmp_path, [], [], reported, TODAY + timedelta(days=1), []) == []   # not due yet
    again = domains._look({"domains": C}, tmp_path, [], [], reported, later, [])
    assert [r["term"] for r in again] == ["toc toc"]
    assert domains._look({"domains": C}, tmp_path, [], [], reported, later + timedelta(days=2), []) == []   # read twice, then dropped


def test_a_floor_lifts_the_judges_score_in_the_lead(cfg, monkeypatch):
    monkeypatch.setattr(report.judge, "score", lambda rows, model, focus: [r.update(named=0.2) for r in rows] and {"judged": len(rows)})
    row = {"term": "flying car", "recent": 5, "lift": 5.0, "note": "n", "examples": [], "floor": 0.9, "strong": True}
    lead, _ = report.leads(cfg, {"domain": {"terms": [row]}})
    assert lead[0]["named"] == 0.9 and lead[0]["strong"] and report.to_push(cfg, lead)


def test_diff_with_nothing_online_and_nothing_kept_says_so(tmp_path, monkeypatch):
    def down():
        raise OSError("network is down")
    monkeypatch.setattr(domains, "available", down)
    assert "network is down" in domains.diff({"domains": C}, tmp_path, TODAY)["error"]


# --- the report and the Feishu push --------------------------------------------------------

def _lead(cfg, rows):
    block = {"window": ["2026-10-14", "2026-10-15", "2026-10-16"], "read": ["2026-10-16"], "history_days": 2, "terms": rows}
    for r in rows:
        r.update(first_day="2026-10-16", registered="10-14", note=f"New domains: {r['domains']} ({r['tlds']} TLDs), registered 10-14")
    lead, _ = report.leads(cfg, {"domain": block})
    return lead, block


def test_the_daily_report_lists_the_waves(cfg):
    lead, block = _lead(cfg, domains.find([domains.group(WAVE)], [], C))
    text = "\n".join(report._domain_lines(block, cfg))
    assert "| **hotel lobby** 🤖 | 7 | 6 | ×6.0 | 10-14 |" in text and "History: 2 days of lists. Under a week" in text


def test_push_has_one_line_per_new_name_with_its_curve(cfg, monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_REPOSITORY", "me/radar")
    lead, block = _lead(cfg, domains.find([domains.group(WAVE)], [], C))
    uc = {"benchmark": "gpts", "rows": [{"phrase": "hotel lobby", "started": "2026-10-12", "now": "rising", "peak_vs": 51, "bench_level": 40}]}
    title, text = report.push(cfg, lead, {"domain": block}, {"usecases": uc})
    assert title == "New-term radar · 7 new"
    assert "**hotel lobby** · New domains: 7 (6 TLDs), registered 10-14 · rising since 10-12 · still rising · peak vs gpts: 51 vs 40\n" \
           "    hotellobby.ai, aihotellobby.art, hotellobbyai.com" in text
    assert "[Full report](https://github.com/me/radar/actions/runs/42)" in text


def test_push_is_quiet_without_news_and_speaks_up_when_the_source_fails(cfg):
    assert report.push(cfg, [], {"domain": {"terms": []}}, {}) is None
    title, text = report.push(cfg, [], {"domain": {"error": "OSError: timed out", "terms": []}}, {})
    assert title == "New-term radar · a source failed" and "③ new domains: OSError: timed out" in text


def test_feishu_needs_its_three_keys_and_sends_a_card(monkeypatch):
    for k in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_RECEIVE_ID"):
        monkeypatch.delenv(k, raising=False)
    assert notify.feishu("t", "x").startswith("feishu skipped")
    for k in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_RECEIVE_ID"):
        monkeypatch.setenv(k, "v")
    sent = []

    def post(url, body, token="", params=""):
        sent.append((url, body, token, params))
        return {"tenant_access_token": "tok"} if "auth" in url else {"code": 0}
    monkeypatch.setattr(notify, "_feishu_post", post)
    assert notify.feishu("New-term radar", "1. **hotel lobby**") == "feishu sent"
    url, body, token, params = sent[1]
    assert token == "tok" and params == "?receive_id_type=chat_id" and body["msg_type"] == "interactive"
    assert json.loads(body["content"])["elements"][0]["content"] == "1. **hotel lobby**"


# --- the names-only keyword table and the config's skip -----------------------------------

def test_names_only_reads_the_curve_and_nothing_else(cfg, tmp_path, monkeypatch):
    cfg["usecases"]["generic"] = False

    def paid(*a, **k):
        raise AssertionError("no posts, phrases or volumes in names-only mode")
    for fn in ("evidence", "propose", "screen"):
        monkeypatch.setattr(usecases, fn, paid)
    days = [(TODAY - timedelta(days=89 - i), v) for i, v in enumerate([1] * 85 + [9, 53, 40, 59, 100])]
    monkeypatch.setattr(usecases, "fetch_series", lambda keywords, bench, today: (
        {k: {"solo": days, "pair": [(d, v, 40) for d, v in days]} for k in keywords}, 2400))
    uc = usecases.run(cfg, tmp_path, ["hotel lobby"], {}, TODAY)
    assert [r["phrase"] for r in uc["rows"]] == ["hotel lobby"] and uc["rows"][0]["now"] == "rising" and uc["no_evidence"] == []
    text = "\n".join(report.keyword_table(cfg, uc))
    assert "Each name's Google Trends curve" in text and "GOANYAPI" not in text


def test_skip_in_the_config_turns_a_signal_off(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(cli.domains, "diff", lambda cfg, state: called.append(1) or {"terms": []})
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"skip": ["domains", "x", "hf", "breakout", "sitemaps", "newsites", "review", "judge"]}))
    assert cli.main(["daily", "--config", str(path), "--state", str(tmp_path / "s")]) == 0 and called == []


def test_download_tries_once_more_when_the_server_drops_the_connection(monkeypatch):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("domain-names.txt", "bulin47.ai\nbulin47ai.link\n")
    answers = [OSError("EOF occurred in violation of protocol"), buf.getvalue()]

    def flaky(url):
        a = answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a
    monkeypatch.setattr(domains, "_get", flaky)
    assert domains.download("u") == ["bulin47.ai", "bulin47ai.link"]
