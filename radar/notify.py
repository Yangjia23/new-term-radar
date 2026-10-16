"""Send a report: by mail through Resend, or to a Feishu chat. Both optional.

Mail: RESEND_API_KEY, EMAIL_FROM (an address on a domain you verified in Resend),
RADAR_EMAIL_TO (comma-separated for several). Without RADAR_EMAIL_TO it says so and does
nothing: a missing recipient must not fail the run that produced the report.
Needs the `markdown` package (pip install markdown).

Feishu: a self-built app's bot (the way find-idea and gamerant-roblox-monitor send):
FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_RECEIVE_ID (a chat_id unless
FEISHU_RECEIVE_ID_TYPE says otherwise). The message is a card with one Markdown element.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from . import UA

# Inline styles: Gmail drops a <style> block that sits outside <head>, which leaves
# tables unbordered with centred headers. Every tag carries its own.
FONT = "-apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif"
INLINE = {
    "h2": "font-size:18px;margin:0 0 12px;color:#1f2328",
    "h3": "font-size:15px;margin:24px 0 8px;color:#1f2328",
    "p": "margin:8px 0",
    "table": "border-collapse:collapse;margin:8px 0;width:100%",
    "th": "border:1px solid #d0d7de;padding:6px 10px;font-size:13px;background:#f6f8fa;text-align:left;white-space:nowrap",
    "td": "border:1px solid #d0d7de;padding:6px 10px;font-size:13px;vertical-align:top",
    "ul": "padding-left:0;margin:8px 0;list-style:none",
    "li": "margin:0 0 10px;padding:8px 12px;border-left:3px solid #d0d7de;background:#f6f8fa;font-size:13px",
    "a": "color:#0969da",
}
TAG = re.compile(r"<(" + "|".join(INLINE) + r")(\s[^>]*)?>")
_ADDRESS = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[a-z]{2,}$", re.I)


def _inline(m: re.Match) -> str:
    attrs = m.group(2) or ""
    if m.group(1) == "td" and 'style="text-align' in attrs:   # markdown's own column alignment
        return f"<td{attrs}>"
    return f'<{m.group(1)} style="{INLINE[m.group(1)]}"{attrs}>'


def html(md_text: str) -> str:
    import markdown
    body = TAG.sub(_inline, markdown.markdown(md_text, extensions=["tables"]))
    return f'<div style="font:14px/1.6 {FONT};color:#1f2328;max-width:900px">{body}</div>'


def recipients(raw: str) -> list[str]:
    """RADAR_EMAIL_TO as people type it: commas (also full-width), semicolons or spaces
    between addresses; quotes and angle brackets around them are dropped."""
    parts = re.split(r"[,，;；\s]+", raw.strip().strip("\"'"))
    return [p.strip("\"'<>") for p in parts if p.strip("\"'<>")]


def send(subject: str, md_text: str) -> str:
    to = recipients(os.environ.get("RADAR_EMAIL_TO", ""))
    if not to:
        return "mail skipped: RADAR_EMAIL_TO not set"
    bad = [i + 1 for i, a in enumerate(to) if not _ADDRESS.match(a)]
    if bad:   # the address itself stays out of the log
        raise SystemExit(f"RADAR_EMAIL_TO: {len(to)} address(es), number {bad} is not an email address")
    body = json.dumps({"from": os.environ["EMAIL_FROM"], "to": to, "subject": subject, "html": html(md_text)}).encode()
    # Resend sits behind Cloudflare, which answers Python's default User-Agent with 403 "error code: 1010".
    req = urllib.request.Request("https://api.resend.com/emails", data=body, method="POST", headers={
        "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return f"mail sent ({res.status})"
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Resend {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc


FEISHU = "https://open.feishu.cn/open-apis"
CARD_CHARS = 15000


def _feishu_post(url: str, body: dict, token: str = "", params: str = "") -> dict:
    headers = {"Content-Type": "application/json; charset=utf-8", "User-Agent": UA}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url + params, data=json.dumps(body, ensure_ascii=False).encode(), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.load(res)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Feishu {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc


def card(title: str, md_text: str) -> dict:
    return {"config": {"wide_screen_mode": True},
            "header": {"template": "blue", "title": {"tag": "plain_text", "content": title}},
            "elements": [{"tag": "markdown", "content": md_text[:CARD_CHARS]}]}


def feishu(title: str, md_text: str) -> str:
    keys = ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_RECEIVE_ID")
    if not all(os.environ.get(k) for k in keys):
        return "feishu skipped: FEISHU_APP_ID, FEISHU_APP_SECRET or FEISHU_RECEIVE_ID not set"
    auth = _feishu_post(f"{FEISHU}/auth/v3/tenant_access_token/internal",
                        {"app_id": os.environ["FEISHU_APP_ID"], "app_secret": os.environ["FEISHU_APP_SECRET"]})
    token = auth.get("tenant_access_token")
    if not token:
        raise SystemExit(f"Feishu token: code {auth.get('code')} {auth.get('msg', '')}")
    kind = os.environ.get("FEISHU_RECEIVE_ID_TYPE", "chat_id")
    sent = _feishu_post(f"{FEISHU}/im/v1/messages", {
        "receive_id": os.environ["FEISHU_RECEIVE_ID"], "msg_type": "interactive",
        "content": json.dumps(card(title, md_text), ensure_ascii=False)}, token, f"?receive_id_type={kind}")
    if sent.get("code") != 0:
        raise SystemExit(f"Feishu send: code {sent.get('code')} {sent.get('msg', '')}")
    return "feishu sent"
