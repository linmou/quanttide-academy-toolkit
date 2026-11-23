#!/usr/bin/env python3
"""Publish or update `career-discovery/partner-card.md` as a Feishu Personal Homepage link.

Uses Feishu Cloud Docs (`DocxXML` + embedded `<html5-block>` Bento-grid personal homepage +
native clickable Feishu user avatar `<cite type="user"/>` for 1-click DM + 2-column
`<grid>` summary) via the student's local `lark-cli` — requiring zero Git or GitHub account.

Creates a Feishu Cloud Doc on first run, stores `feishu_doc_id` locally in
`career-discovery/.card-link.json`, and updates the SAME URL in place on future runs
so the student's Feishu profile bio link never changes.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def find_lark_cli() -> str | None:
    for candidate in (
        Path.home() / ".local" / "bin" / "lark-cli",
        Path.home() / ".homebrew" / "bin" / "lark-cli",
        Path("/opt/homebrew/bin/lark-cli"),
        Path("/usr/local/bin/lark-cli"),
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which("lark-cli")


def run_cmd(
    cmd: list[str], timeout: int = 90, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.setdefault("LARK_CLI_NO_PROXY_WARN", "1")
    return subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(cwd) if cwd else None,
        check=False,
    )


def load_state(state_path: Path) -> dict:
    if state_path.is_file():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {}


def save_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_feishu_identity(lark_bin: str) -> tuple[str, str]:
    proc = run_cmd([lark_bin, "whoami"], timeout=10)
    if proc.returncode == 0:
        try:
            payload = json.loads(proc.stdout)
            behalf = payload.get("onBehalfOf") or {}
            open_id = str(behalf.get("openId") or "").strip()
            user_name = str(behalf.get("userName") or "").strip()
            return open_id, user_name
        except json.JSONDecodeError:
            pass
    return "", ""


def strip_md_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def parse_partner_card_md(md_text: str) -> dict[str, str]:
    parsed = {
        "intro": "",
        "offer": "",
        "avoid": "",
        "seek": "",
        "weekly_budget": "",
        "schedule_blackout": "",
        "experiment": "",
        "generated_at": "2026-11-22",
        "schema_version": "qt-partner-card/v1",
    }

    section = ""
    intro_lines: list[str] = []
    exp_lines: list[str] = []

    for raw in md_text.splitlines():
        line = raw.strip()
        if not line or line == "---":
            continue
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            if "怎么搭伙" in heading or "一句话" in heading:
                section = "intro"
            elif "协作接口" in heading:
                section = "interface"
            elif "实验" in heading or "自述" in heading or "短帖" in heading:
                section = "experiment"
            else:
                section = ""
            continue

        if line.startswith("Generated-At:"):
            parsed["generated_at"] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Schema-Version:"):
            parsed["schema_version"] = line.split(":", 1)[1].strip()
            continue

        m = re.match(r"^-\s*\*\*([^*]+)\*\*[:：]\s*(.+)$", line)
        if m:
            key_raw, val_raw = m.group(1), strip_md_inline(m.group(2))
            if "Offer" in key_raw:
                parsed["offer"] = val_raw
            elif "Avoid" in key_raw:
                parsed["avoid"] = val_raw
            elif "Seek" in key_raw:
                parsed["seek"] = val_raw
            elif "Weekly-Budget" in key_raw:
                parsed["weekly_budget"] = val_raw
            elif "Schedule-Blackout" in key_raw:
                parsed["schedule_blackout"] = val_raw
            continue

        clean = strip_md_inline(line.lstrip("> ").strip())
        if section == "intro":
            intro_lines.append(clean)
        elif section == "experiment":
            exp_lines.append(clean)

    parsed["intro"] = " ".join(intro_lines).strip()
    parsed["experiment"] = "\n".join(exp_lines).strip()
    return parsed


def build_rich_html(
    fields: dict[str, str],
    user_name: str,
    headline: str,
    subheadline: str,
) -> str:
    esc = lambda s: html.escape(s or "", quote=True)
    name_badge = esc(user_name or "量潮实训基地成员")
    exp_paragraphs = "".join(
        f"<p>{esc(p)}</p>" for p in (fields["experiment"] or "").splitlines() if p.strip()
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="use-iframe" content="true">
  <meta name="html-box-height-mode" content="auto">
  <meta name="description" content="量潮实训基地互补搭档协作个人主页名片">
  <title>{esc(headline)}</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --card: #ffffff;
      --ink: #0f172a;
      --muted: #475569;
      --line: #e2e8f0;
      --hero-a: #0f172a;
      --hero-b: #1e293b;
      --accent: #38bdf8;
      --offer-bg: #f0fdf4;
      --offer-bd: #86efac;
      --offer-ink: #14532d;
      --seek-bg: #eff6ff;
      --seek-bd: #93c5fd;
      --seek-ink: #1e3a8a;
      --avoid-bg: #fff1f2;
      --avoid-bd: #fda4af;
      --avoid-ink: #881337;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      background: transparent;
      color: var(--ink);
      line-height: 1.65;
      padding: 4px 2px 12px;
      width: 100%;
      max-width: 100%;
    }}
    .wrap {{
      display: flex;
      flex-direction: column;
      gap: 14px;
      width: 100%;
    }}
    .hero {{
      background: linear-gradient(135deg, var(--hero-a) 0%, var(--hero-b) 65%, #0f3460 100%);
      color: #f8fafc;
      border-radius: 18px;
      padding: 24px 26px;
      position: relative;
      overflow: hidden;
      box-shadow: 0 10px 28px rgba(15, 23, 42, 0.14);
    }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.04em;
      padding: 4px 11px;
      border-radius: 999px;
      background: rgba(56, 189, 248, 0.16);
      color: #bae6fd;
      border: 1px solid rgba(56, 189, 248, 0.32);
    }}
    .meta-tag {{
      font-size: 12px;
      color: #94a3b8;
    }}
    .hero h1 {{
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: #ffffff;
      margin-bottom: 6px;
    }}
    .hero .sub {{
      font-size: 15px;
      color: #cbd5e1;
      margin-bottom: 14px;
    }}
    .hero .intro {{
      font-size: 14px;
      color: #e2e8f0;
      background: rgba(255, 255, 255, 0.07);
      border-left: 3px solid var(--accent);
      padding: 11px 14px;
      border-radius: 0 10px 10px 0;
      margin-bottom: 16px;
    }}
    .pills {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .pill {{
      font-size: 12.5px;
      padding: 5px 12px;
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.55);
      border: 1px solid rgba(255, 255, 255, 0.16);
      color: #f1f5f9;
    }}
    .bento {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    @media (max-width: 600px) {{
      .bento {{ grid-template-columns: 1fr; }}
    }}
    .card {{
      border-radius: 15px;
      padding: 16px 18px;
      border: 1px solid var(--line);
      background: var(--card);
      box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
    }}
    .card.offer {{
      background: var(--offer-bg);
      border-color: var(--offer-bd);
    }}
    .card.seek {{
      background: var(--seek-bg);
      border-color: var(--seek-bd);
    }}
    .card.avoid {{
      grid-column: 1 / -1;
      background: var(--avoid-bg);
      border-color: var(--avoid-bd);
    }}
    .card-head {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      margin-bottom: 8px;
    }}
    .offer .card-head {{ color: var(--offer-ink); }}
    .seek .card-head {{ color: var(--seek-ink); }}
    .avoid .card-head {{ color: var(--avoid-ink); }}
    .card p {{
      font-size: 14px;
      color: #1e293b;
    }}
    .mvp {{
      border-radius: 16px;
      padding: 18px 20px;
      background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
      border: 1px solid #cbd5e1;
    }}
    .mvp-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }}
    .mvp-title {{
      font-size: 15px;
      font-weight: 700;
      color: #0f172a;
    }}
    .mvp-chip {{
      font-size: 11.5px;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 999px;
      background: #e0f2fe;
      color: #0369a1;
    }}
    .mvp p {{
      font-size: 14px;
      color: #334155;
      margin-bottom: 8px;
    }}
    .mvp p:last-child {{ margin-bottom: 0; }}
    .pact {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px dashed #cbd5e1;
    }}
    .pact span {{
      font-size: 12px;
      color: #475569;
      background: #f1f5f9;
      padding: 4px 10px;
      border-radius: 8px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="hero-top">
        <span class="badge">✦ {name_badge} · 互补搭档主页</span>
        <span class="meta-tag">{esc(fields["schema_version"])} · {esc(fields["generated_at"])}</span>
      </div>
      <h1>{esc(headline)}</h1>
      <div class="sub">{esc(subheadline)}</div>
      <div class="intro">{esc(fields["intro"])}</div>
      <div class="pills">
        <span class="pill">⏱ 投入节奏：{esc(fields["weekly_budget"])}</span>
        <span class="pill">🌙 出没时段：{esc(fields["schedule_blackout"])}</span>
      </div>
    </section>

    <section class="bento">
      <div class="card offer">
        <div class="card-head">⚡ OFFER · 我来兜底的长板</div>
        <p>{esc(fields["offer"])}</p>
      </div>
      <div class="card seek">
        <div class="card-head">🧭 SEEK · 想找的互补搭档</div>
        <p>{esc(fields["seek"])}</p>
      </div>
      <div class="card avoid">
        <div class="card-head">🛡 AVOID · 我不碰的协作边界</div>
        <p>{esc(fields["avoid"])}</p>
      </div>
    </section>

    <section class="mvp">
      <div class="mvp-head">
        <span class="mvp-title">🚀 近期想试的 2 周微实验</span>
        <span class="mvp-chip">14-Day Reversible MVP</span>
      </div>
      {exp_paragraphs}
      <div class="pact">
        <span>✔ 开工前先对齐小目标边界</span>
        <span>✔ 偏异步深潜 · 少开同步长会</span>
        <span>✔ 跑通成果双方共同署名</span>
      </div>
    </section>
  </div>
</body>
</html>
"""


def xml_esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_docx_xml(
    title: str,
    html_rel_path: str,
    open_id: str,
    fields: dict[str, str],
) -> str:
    cite_xml = (
        f'<cite type="user" user-id="{xml_esc(open_id)}"/>'
        if open_id.startswith("ou_")
        else "<b>名片主人</b>"
    )
    return f"""<title>{xml_esc(title)}</title>
<callout emoji="👋" background-color="light-blue" border-color="blue">
  <p><b>看对眼想搭伙？</b>直接点击右侧飞书头像即可一键发起私聊 👉 {cite_xml}（支持先用 2 周微实验低成本试跑，开工前对齐小目标与署名）</p>
</callout>
<html5-block path="@{html_rel_path}"/>
<h2>快速检索摘要（供飞书搜索与移动端速览）</h2>
<grid>
  <column width-ratio="0.5">
    <callout emoji="⚡" background-color="light-green" border-color="green">
      <p><b>我能提供的长板（Offer）</b><br/>{xml_esc(fields["offer"])}</p>
    </callout>
  </column>
  <column width-ratio="0.5">
    <callout emoji="🧭" background-color="light-blue" border-color="blue">
      <p><b>想找的同路人（Seek）</b><br/>{xml_esc(fields["seek"])}</p>
    </callout>
  </column>
</grid>
<callout emoji="🛡" background-color="light-gray" border-color="gray">
  <p><b>协作边界（Avoid）</b>：{xml_esc(fields["avoid"])}<br/><b>投入节奏与时段</b>：{xml_esc(fields["weekly_budget"])}｜{xml_esc(fields["schedule_blackout"])}</p>
</callout>
"""


def apply_feishu_share(lark_bin: str, doc_id: str, share: str) -> tuple[str, str | None]:
    if share == "none":
        return "private_owner_only", None

    params = json.dumps({"token": doc_id, "type": "docx"}, ensure_ascii=False)
    desired_external = share == "anyone_readable"
    data = json.dumps(
        {
            "external_access": desired_external,
            "link_share_entity": share,
        },
        ensure_ascii=False,
    )
    proc = run_cmd(
        [
            lark_bin,
            "drive",
            "permission.public",
            "patch",
            "--as",
            "user",
            "--params",
            params,
            "--data",
            data,
            "--yes",
        ]
    )
    if proc.returncode == 0:
        return share, None

    if share == "anyone_readable":
        fallback_data = json.dumps(
            {"external_access": False, "link_share_entity": "tenant_readable"},
            ensure_ascii=False,
        )
        fb_proc = run_cmd(
            [
                lark_bin,
                "drive",
                "permission.public",
                "patch",
                "--as",
                "user",
                "--params",
                params,
                "--data",
                fallback_data,
                "--yes",
            ]
        )
        if fb_proc.returncode == 0:
            return "tenant_readable", "anyone_readable_blocked_by_tenant_fell_back_to_tenant_readable"

    return "permission_unchanged", (proc.stderr or proc.stdout).strip()[:240]


def publish_feishu(
    lark_bin: str,
    card_path: Path,
    state_path: Path,
    title: str,
    headline: str,
    subheadline: str,
    share: str,
    confirm_share: bool,
) -> dict:
    state = load_state(state_path)
    doc_id = state.get("feishu_doc_id")
    url = state.get("feishu_url")

    open_id, user_name = get_feishu_identity(lark_bin)
    fields = parse_partner_card_md(card_path.read_text(encoding="utf-8"))

    card_dir = card_path.resolve().parent
    html_path = card_dir / "partner-card.html"
    xml_path = card_dir / "partner-card.xml"

    html_path.write_text(
        build_rich_html(fields, user_name, headline, subheadline),
        encoding="utf-8",
    )
    xml_path.write_text(
        build_docx_xml(title, "./partner-card.html", open_id, fields),
        encoding="utf-8",
    )

    if doc_id:
        upd = run_cmd(
            [
                lark_bin,
                "docs",
                "+update",
                "--as",
                "user",
                "--doc",
                doc_id,
                "--command",
                "overwrite",
                "--doc-format",
                "xml",
                "--content",
                "@./partner-card.xml",
            ],
            cwd=card_dir,
        )
        if upd.returncode == 0:
            applied_share = state.get("feishu_share", "unchanged")
            share_warn = None
            if confirm_share and share != "none":
                applied_share, share_warn = apply_feishu_share(lark_bin, doc_id, share)
                state["feishu_share"] = applied_share
                save_state(state_path, state)
            return {
                "status": "ok",
                "channel": "feishu_rich_xml_html5",
                "action": "updated_in_place",
                "url": url or f"feishu://docx/{doc_id}",
                "share": applied_share,
                "warning": share_warn,
            }

    crt = run_cmd(
        [
            lark_bin,
            "docs",
            "+create",
            "--as",
            "user",
            "--doc-format",
            "xml",
            "--title",
            title,
            "--content",
            "@./partner-card.xml",
        ],
        cwd=card_dir,
    )
    if crt.returncode != 0:
        return {
            "status": "error",
            "channel": "feishu_rich_xml_html5",
            "error": (crt.stderr or crt.stdout).strip()[:400],
        }

    payload = json.loads(crt.stdout)
    doc = ((payload.get("data") or {}).get("document")) or {}
    new_doc_id = doc.get("document_id")
    new_url = doc.get("url")
    if not new_doc_id:
        return {
            "status": "error",
            "channel": "feishu_rich_xml_html5",
            "error": "missing_document_id_in_response",
        }

    applied_share = "private_owner_only"
    share_warn = None
    if confirm_share and share != "none":
        applied_share, share_warn = apply_feishu_share(lark_bin, new_doc_id, share)

    state.update(
        {
            "feishu_doc_id": new_doc_id,
            "feishu_url": new_url,
            "feishu_share": applied_share,
        }
    )
    save_state(state_path, state)
    return {
        "status": "ok",
        "channel": "feishu_rich_xml_html5",
        "action": "created",
        "url": new_url,
        "share": applied_share,
        "warning": share_warn,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", type=Path, default=Path("career-discovery/partner-card.md"))
    parser.add_argument("--state", type=Path, default=Path("career-discovery/.card-link.json"))
    parser.add_argument("--title", default="互补搭档协作名片")
    parser.add_argument("--headline", default="理乱麻、搭轻流之人")
    parser.add_argument("--subheadline", default="拆解混沌机制 · 驭 AI 造小样板 · 寻一位熟稔一线烟火的同路客")
    parser.add_argument(
        "--share",
        choices=("none", "tenant_readable", "anyone_readable"),
        default="anyone_readable",
        help="Link sharing level for Feishu docx (applied only when --confirm-share is set).",
    )
    parser.add_argument(
        "--confirm-share",
        action="store_true",
        help="Pass only after the student explicitly confirms making the link readable.",
    )
    args = parser.parse_args()

    if not args.card.is_file():
        print(json.dumps({"status": "error", "error": f"card_not_found:{args.card}"}, ensure_ascii=False))
        return 1

    lark_bin = find_lark_cli()
    if not lark_bin:
        print(
            json.dumps(
                {
                    "status": "unavailable",
                    "reason": "lark_cli_not_found",
                    "hint": "Run lark-cli auth login first, or copy career-discovery/partner-card.md into a Feishu Cloud Doc.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    res = publish_feishu(
        lark_bin,
        args.card,
        args.state,
        args.title,
        args.headline,
        args.subheadline,
        args.share,
        args.confirm_share,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
