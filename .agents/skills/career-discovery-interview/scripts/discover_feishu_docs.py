#!/usr/bin/env python3
"""Two-stage Feishu document discovery, diagnostic-question mapper, and authorized fetcher.

Stage 1 (`--mode discover`, default):
  Enumerates accessible Feishu Wiki spaces/nodes (including `my_library`) and recent
  Feishu doc/wiki links shared in chats via `lark-cli`. Inspects metadata ONLY (title,
  token, space, type) without reading document bodies, classifies each document into
  categories A–E, and maps it to specific career-discovery diagnostic questions
  (RIASEC × Bandura self-efficacy, Schein career anchors × anti-vision, Keeney MCDA ×
  Stanford DYL energy & post-work calibration).

Stage 2 (`--mode fetch --tokens <tok1,tok2,...>` or `--categories <B,C,...>`):
  Fetches content ONLY for user-authorized document tokens or categories, scrubs PII
  (<cite> tags, @mentions, open_ids, URLs), and extracts concise topical snippets and
  reflective hooks for the interview state machine.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

CATEGORY_SPECS: dict[str, dict[str, Any]] = {
    "A": {
        "code": "A",
        "key": "governance_wiki",
        "label": "A. 公共第二大脑与治理章程库",
        "default_recommended": False,
        "privacy_level": "public_org",
        "mapped_questions": [
            "Ref 1 §一 RIASEC: C 常规秩序型（知识库索引归档、议事规则） / I 研究探索型（制度与机制拆解）",
            "Ref 2 §一 Schein 职业锚: GM 全局管理与统筹锚 / SE 确定性与凭证保障锚",
            "SKILL Phase 2.2 制度实情核验: 核对实习证明、结项初审、不活跃核查等现行生效书面决议",
        ],
        "interview_states": ["B3_SCENE_RESONANCE", "B7_ANCHOR_TRADEOFF", "A2_STRENGTH_OR_STRETCH", "Phase2_Governance"],
    },
    "B": {
        "code": "B",
        "key": "department_tasks",
        "label": "B. 各部门任务书与业务方案文档",
        "default_recommended": True,
        "privacy_level": "shared_task",
        "mapped_questions": [
            "Ref 1 §一 RIASEC 六维真实任务情境: R 实操构建（小游戏上线）、I 研究探索（第二大脑边界刻画）、A 艺术创意（小说/视觉/BGM）、E 企业经营（小红书引流转化）、S 社会联结（新人引导）、C 常规秩序（台账SOP）",
            "Ref 1 §二.2 脚手架敏感度检验 (Scaffolding Test): 基于80%半成品模板+AI改版任务书区分 Q2 潜能破冰区 与 Q4 直接规避区",
            "Ref 3 §一 组织方向对齐检验 & §三 一石二鸟协同设计 (2-Week MVP 任务切口)",
        ],
        "interview_states": ["B3_SCENE_RESONANCE", "B4_SCAFFOLD_PROBE", "B8_PATH_CONFIRM", "A2_STRENGTH_OR_STRETCH", "A5_BUDGETED_SYNTHESIS"],
    },
    "C": {
        "code": "C",
        "key": "work_logs_reports",
        "label": "C. 个人实训工作日志与工作汇报",
        "default_recommended": True,
        "privacy_level": "member_work_record",
        "mapped_questions": [
            "Ref 3 §四.1 斯坦福 DYL 充能/耗能瞬间 (AEIOU 能量校准): 从真实实训体验（如跑通上线成就感或卡点）切入",
            "Ref 1 §二 Bandura 四象限鉴别: 依据已完成的实操记录锚定 Q1 核心优势区、Q2 潜能破冰区 与 Q3 伪优势消耗区",
            "Ref 3 §五 实战复盘与增量校准 (Mode C): 对照实际产出与体感反差更新 profile.md (vN -> vN+1)",
        ],
        "interview_states": ["B2_ENERGY", "B4_SCAFFOLD_PROBE", "B5_BURNOUT_PROBE", "A2_STRENGTH_OR_STRETCH", "Mode_C_Calibration"],
    },
    "D": {
        "code": "D",
        "key": "meeting_minutes",
        "label": "D. 会议纪要与研讨区文档",
        "default_recommended": True,
        "privacy_level": "shared_discussion",
        "mapped_questions": [
            "Ref 2 §三 反愿景排查表 (T1-T9 时间保护红线): 结合近期对齐会与研讨痛点排查信息爬楼、需求变动、无议程长会等雷区",
            "Ref 3 §一 组织方向对齐检验: 了解基地近期主线议题与协作摩擦点",
        ],
        "interview_states": ["B3_SCENE_RESONANCE", "B6_QUICK_CARD", "A4_QUICK_CARD"],
    },
    "E": {
        "code": "E",
        "key": "personal_library",
        "label": "E. 个人文档库私密/小组归档记录",
        "default_recommended": False,
        "privacy_level": "private_explicit_only",
        "mapped_questions": [
            "Ref 2 §一 Schein 职业锚 & Ref 3 §五 认知演进复盘: 仅在用户显式勾选单篇文档时读取，用于深度个人复盘",
        ],
        "interview_states": ["Explicit_Opt_In_Only"],
    },
}

FEISHU_LINK_RE = re.compile(
    r"https?://[A-Za-z0-9._-]*feishu\.cn/(?:wiki|docx|docs)/[A-Za-z0-9_-]+"
)
CITE_TAG_RE = re.compile(r"<cite\b[^>]*>.*?</cite>", re.DOTALL)
HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
ID_PATTERNS = re.compile(r"\b(?:ou|oc|on|cli|img|file|om)_[A-Za-z0-9_-]{6,}\b")
AT_MENTION = re.compile(r"@[^\s@,:：，。！？!?\]]{1,20}")
URL_PATTERN = re.compile(r"https?://\S+")
NOISE_LINE = re.compile(
    r"^(\+1|收到|好的|哈哈+|谢谢.*|赞|ok|OK|\[图片\]|\[表情\]|\[贴纸\]|!\[.*?\].*)$"
)


def find_lark_cli() -> str | None:
    local_bin = Path.home() / ".local" / "bin" / "lark-cli"
    if local_bin.is_file() and os.access(local_bin, os.X_OK):
        return str(local_bin)
    return shutil.which("lark-cli")


def run_lark_json(bin_path: str, args: list[str], timeout: int = 12) -> dict[str, Any]:
    env = dict(os.environ)
    env.setdefault("LARK_CLI_NO_PROXY_WARN", "1")
    try:
        proc = subprocess.run(
            [bin_path, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid_json", "raw": proc.stdout[:300]}


def classify_document(title: str, space_name: str = "", space_type: str = "") -> str:
    t = (title or "").strip()
    s = (space_name or "").strip()

    if space_type == "my_library" or s == "My Document Library":
        return "E"
    if any(k in t for k in ("会话", "Chat between")):
        return "E"
    if any(k in t for k in ("工作日志", "工作汇报", "个人总结", "学习日志", "复盘日志", "周报")):
        return "C"
    if any(k in t for k in ("智能纪要", "AI 视图", "会议", "研讨会", "讨论区")):
        return "D"
    if any(
        k in t
        for k in (
            "任务书",
            "推广方案",
            "产品组任务",
            "运营部门",
            "选拔结果",
            "SOP",
            "初审协作文档",
            "小游戏",
            "小说",
            "小红书",
            "第二大脑认知探索",
        )
    ):
        return "B"
    if any(
        k in s
        for k in (
            "联盟第二大脑",
            "量潮实训代表第二大脑",
            "工作章程",
            "工作手册",
            "工作档案",
            "归档站知识库",
        )
    ) or any(
        k in t
        for k in (
            "第二大脑",
            "工作章程",
            "工作手册",
            "工作档案",
            "议事",
            "决议",
            "提案",
            "架构",
            "角色",
            "机制",
            "成员管理",
        )
    ):
        return "A"
    return "B"


def scrub_text_line(raw: str) -> str:
    line = raw.strip()
    if not line or line.startswith(("```", "---", "| -", "|-")):
        return ""
    line = CITE_TAG_RE.sub("某成员", line)
    line = HTML_TAG_RE.sub(" ", line)
    line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
    line = re.sub(r"(?:记录人|汇报人|负责人|参会人)\s*[:：]\s*[^\s|，。,:：]{1,15}", "", line)
    line = AT_MENTION.sub("某成员", line)
    line = ID_PATTERNS.sub("", line)
    line = URL_PATTERN.sub("", line)
    line = re.sub(r"\s+", " ", line).strip(" -•|>\t")
    if len(line) < 6 or NOISE_LINE.match(line):
        return ""
    return line[:140]


def discover_wiki_nodes(bin_path: str, max_depth: int = 1) -> list[dict[str, Any]]:
    spaces_res = run_lark_json(bin_path, ["wiki", "+space-list", "--as", "user", "--format", "json"])
    spaces = list((spaces_res.get("data") or {}).get("spaces") or [])

    my_lib_res = run_lark_json(
        bin_path,
        ["wiki", "spaces", "get", "--as", "user", "--params", '{"space_id":"my_library"}', "--format", "json"],
    )
    my_lib = (my_lib_res.get("data") or {}).get("space")
    if isinstance(my_lib, dict) and my_lib.get("space_id"):
        if not any(s.get("space_id") == my_lib["space_id"] for s in spaces):
            spaces.append(my_lib)

    docs: list[dict[str, Any]] = []
    seen_obj: set[str] = set()

    def walk(space: dict[str, Any], parent_token: str = "", depth: int = 0) -> None:
        sid = str(space.get("space_id") or "")
        sname = str(space.get("name") or "")
        stype = str(space.get("space_type") or "")
        if "归档" in sname:
            return
        args = ["wiki", "+node-list", "--as", "user", "--space-id", sid, "--format", "json"]
        if parent_token:
            args.extend(["--parent-node-token", parent_token])
        res = run_lark_json(bin_path, args)
        nodes = (res.get("data") or {}).get("nodes") or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            title = str(node.get("title") or "").strip()
            obj_token = str(node.get("obj_token") or "").strip()
            node_token = str(node.get("node_token") or "").strip()
            obj_type = str(node.get("obj_type") or "docx")
            if obj_token and title and title != "首页" and obj_token not in seen_obj:
                seen_obj.add(obj_token)
                cat = classify_document(title, sname, stype)
                docs.append(
                    {
                        "title": title,
                        "token": obj_token,
                        "node_token": node_token,
                        "doc_type": obj_type,
                        "source": f"知识库:{sname}",
                        "category": cat,
                        "category_label": CATEGORY_SPECS[cat]["label"],
                        "privacy_level": CATEGORY_SPECS[cat]["privacy_level"],
                        "default_recommended": CATEGORY_SPECS[cat]["default_recommended"],
                        "mapped_questions": CATEGORY_SPECS[cat]["mapped_questions"],
                    }
                )
            if node.get("has_child") and depth < max_depth and node_token:
                walk(space, node_token, depth + 1)

    for sp in spaces:
        if isinstance(sp, dict) and sp.get("space_id"):
            walk(sp, "", 0)

    return docs


def discover_chat_linked_docs(bin_path: str, existing_tokens: set[str], max_links: int = 16) -> list[dict[str, Any]]:
    urls: list[str] = []
    seen_urls: set[str] = set()
    for query in ("feishu.cn/wiki", "feishu.cn/docx"):
        res = run_lark_json(
            bin_path,
            [
                "im",
                "+messages-search",
                "--as",
                "user",
                "--query",
                query,
                "--page-size",
                "20",
                "--no-reactions",
                "--format",
                "json",
            ],
        )
        messages = (res.get("data") or {}).get("messages") or []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = str(msg.get("content") or "")
            for match in FEISHU_LINK_RE.findall(content):
                if match not in seen_urls:
                    seen_urls.add(match)
                    urls.append(match)
                    if len(urls) >= max_links:
                        break
        if len(urls) >= max_links:
            break

    discovered: list[dict[str, Any]] = []
    for url in urls:
        res = run_lark_json(
            bin_path,
            ["drive", "+inspect", "--as", "user", "--url", url, "--format", "json"],
        )
        data = res.get("data")
        if not isinstance(data, dict):
            continue
        title = str(data.get("title") or "").strip()
        token = str(data.get("token") or "").strip()
        doc_type = str(data.get("type") or "docx")
        if not title or not token or token in existing_tokens:
            continue
        if title in ("互补搭档协作名片", "《课题结项初审协作文档｜空白模板》"):
            continue
        existing_tokens.add(token)
        cat = classify_document(title, "群聊分享文档", "")
        discovered.append(
            {
                "title": title,
                "token": token,
                "node_token": str((data.get("wiki_node") or {}).get("node_token") or ""),
                "doc_type": doc_type,
                "source": "飞书群聊/会话分享链接",
                "category": cat,
                "category_label": CATEGORY_SPECS[cat]["label"],
                "privacy_level": CATEGORY_SPECS[cat]["privacy_level"],
                "default_recommended": CATEGORY_SPECS[cat]["default_recommended"],
                "mapped_questions": CATEGORY_SPECS[cat]["mapped_questions"],
            }
        )
    return discovered


def fetch_authorized_docs(
    bin_path: str,
    target_docs: list[dict[str, Any]],
    snippets_per_doc: int = 6,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for doc in target_docs:
        token = doc["token"]
        res = run_lark_json(
            bin_path,
            [
                "docs",
                "+fetch",
                "--as",
                "user",
                "--doc",
                token,
                "--doc-format",
                "markdown",
                "--scope",
                "full",
            ],
            timeout=15,
        )
        content = (
            ((res.get("data") or {}).get("document") or {}).get("content")
            or (res.get("data") or {}).get("markdown")
            or ""
        )
        if not isinstance(content, str) or not content.strip():
            continue
        headings: list[str] = []
        snippets: list[str] = []
        seen: set[str] = set()
        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("#"):
                h = scrub_text_line(stripped.lstrip("#").strip())
                if h and h not in headings and len(headings) < 6:
                    headings.append(h)
                continue
            cleaned = scrub_text_line(stripped)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                snippets.append(cleaned)
                if len(snippets) >= snippets_per_doc:
                    break
        results.append(
            {
                "title": doc["title"],
                "token": token,
                "category": doc["category"],
                "category_label": doc["category_label"],
                "mapped_questions": doc["mapped_questions"],
                "headings": headings,
                "deidentified_snippets": snippets,
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("discover", "fetch"),
        default="discover",
        help="'discover' lists document metadata + question mappings without reading body; 'fetch' reads user-authorized docs.",
    )
    parser.add_argument(
        "--tokens",
        type=str,
        default="",
        help="Comma-separated document tokens explicitly authorized by the user (for --mode fetch).",
    )
    parser.add_argument(
        "--categories",
        type=str,
        default="",
        help="Comma-separated category codes (e.g. 'B,C,D') authorized by the user (for --mode fetch).",
    )
    parser.add_argument("--max-docs", type=int, default=8)
    parser.add_argument("--snippets-per-doc", type=int, default=6)
    args = parser.parse_args()

    lark_bin = find_lark_cli()
    if not lark_bin:
        print(json.dumps({"status": "unavailable", "reason": "lark_cli_not_found"}, ensure_ascii=False))
        return 0

    if args.mode == "discover":
        wiki_docs = discover_wiki_nodes(lark_bin)
        seen_tokens = {d["token"] for d in wiki_docs}
        chat_docs = discover_chat_linked_docs(lark_bin, seen_tokens)
        all_docs = chat_docs + wiki_docs
        grouped: dict[str, dict[str, Any]] = {}
        for code, spec in CATEGORY_SPECS.items():
            cat_docs = [
                {
                    "title": d["title"],
                    "token": d["token"],
                    "source": d["source"],
                }
                for d in all_docs
                if d["category"] == code
            ]
            if cat_docs:
                grouped[code] = {
                    "category": code,
                    "label": spec["label"],
                    "default_recommended": spec["default_recommended"],
                    "privacy_level": spec["privacy_level"],
                    "mapped_questions": spec["mapped_questions"],
                    "interview_states": spec["interview_states"],
                    "document_count": len(cat_docs),
                    "documents": cat_docs[:12],
                }
        print(
            json.dumps(
                {
                    "status": "ok" if grouped else "empty",
                    "mode": "discover",
                    "consent_requirement": (
                        "MUST ask the user which document categories or specific documents they authorize "
                        "before calling `--mode fetch`. Never read Category E (personal_library) without explicit per-doc selection."
                    ),
                    "categories": grouped,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    # --mode fetch (requires explicit --tokens or --categories from user authorization)
    wanted_tokens = {t.strip() for t in args.tokens.split(",") if t.strip()}
    wanted_cats = {c.strip().upper() for c in args.categories.split(",") if c.strip()}
    if not wanted_tokens and not wanted_cats:
        print(
            json.dumps(
                {
                    "status": "error",
                    "reason": "missing_user_authorization",
                    "message": "Pass --tokens or --categories explicitly authorized by the user.",
                },
                ensure_ascii=False,
            )
        )
        return 1

    if wanted_tokens and not wanted_cats:
        all_docs = []
    else:
        wiki_docs = discover_wiki_nodes(lark_bin)
        seen_tokens = {d["token"] for d in wiki_docs}
        chat_docs = discover_chat_linked_docs(lark_bin, seen_tokens)
        all_docs = chat_docs + wiki_docs

    selected_docs: list[dict[str, Any]] = []
    selected_seen: set[str] = set()

    # Round-robin across requested categories so every authorized category gets represented
    if wanted_cats:
        by_cat: dict[str, list[dict[str, Any]]] = {c: [] for c in wanted_cats if c != "E"}
        for d in all_docs:
            if d["category"] in by_cat:
                by_cat[d["category"]].append(d)
        max_len = max((len(v) for v in by_cat.values()), default=0)
        for idx in range(max_len):
            for c in sorted(by_cat.keys()):
                if idx < len(by_cat[c]):
                    doc = by_cat[c][idx]
                    if doc["token"] not in selected_seen:
                        selected_seen.add(doc["token"])
                        selected_docs.append(doc)

    for d in all_docs:
        tok = d["token"]
        if tok in wanted_tokens and tok not in selected_seen:
            selected_seen.add(tok)
            selected_docs.append(d)

    # Also allow direct token fetch even if not in discovery cache
    for tok in wanted_tokens:
        if tok not in selected_seen:
            selected_seen.add(tok)
            selected_docs.append(
                {
                    "title": f"授权文档 ({tok})",
                    "token": tok,
                    "category": "B",
                    "category_label": CATEGORY_SPECS["B"]["label"],
                    "mapped_questions": CATEGORY_SPECS["B"]["mapped_questions"],
                }
            )

    fetched = fetch_authorized_docs(
        lark_bin,
        selected_docs[: max(1, args.max_docs)],
        snippets_per_doc=args.snippets_per_doc,
    )
    print(
        json.dumps(
            {
                "status": "ok" if fetched else "empty",
                "mode": "fetch",
                "usage_note": (
                    "Use authorized document snippets to ground RIASEC task hooks, scaffolding probes, "
                    "and DYL energy/calibration reflections. Never leak raw PII or third-party complaints."
                ),
                "authorized_documents": fetched,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
