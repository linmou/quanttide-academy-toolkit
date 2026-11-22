#!/usr/bin/env python3
"""Read-only, PII-scrubbed Feishu group scene sampler for career-discovery-interview.

Samples recent group-chat discussions (never DMs) via the student's local `lark-cli`
if available and authenticated, strips all names/IDs/@mentions, and returns concise
topical snippets so the interviewer can craft recognizable 'Aha!' scene examples.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

BASE_KEYWORDS = (
    "量潮",
    "实训",
    "基地",
    "学院",
    "游戏",
    "小说",
    "漫剧",
    "研究",
    "秘书",
    "治理",
    "课程",
    "运营",
    "工作",
    "开发",
)

NOISE_PATTERNS = re.compile(
    r"^(\+1|收到|好的|哈哈+|谢谢.*|赞|ok|OK|\[图片\]|\[表情\]|\[贴纸\]|!\[Image\].*|<audio.*|<video.*|<file.*)$"
)
ID_PATTERNS = re.compile(r"\b(?:ou|oc|on|cli|img|file|om)_[A-Za-z0-9_-]{6,}\b")
AT_MENTION = re.compile(r"@[^\s@,:：，。！？!?\]]{1,20}")
URL_PATTERN = re.compile(r"https?://\S+")
SPEAKER_PREFIX = re.compile(r"^\[[^\]]+\]\s*[^:：\n]{1,30}[:：]\s*")
HEADER_META = re.compile(r"^\*\*.*?\*\*\s*")


def find_lark_cli() -> str | None:
    local_bin = Path.home() / ".local" / "bin" / "lark-cli"
    if local_bin.is_file() and os.access(local_bin, os.X_OK):
        return str(local_bin)
    return shutil.which("lark-cli")


def run_lark(bin_path: str, args: list[str], timeout: int = 12) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.setdefault("LARK_CLI_NO_PROXY_WARN", "1")
    return subprocess.run(
        [bin_path, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        check=False,
    )


def scrub_line(raw: str) -> str:
    line = raw.strip()
    if not line or line.startswith(("#", "---", "```", "> ")):
        return ""
    line = SPEAKER_PREFIX.sub("", line)
    line = HEADER_META.sub("", line)
    line = AT_MENTION.sub("某成员", line)
    line = ID_PATTERNS.sub("", line)
    line = URL_PATTERN.sub("[链接]", line)
    line = re.sub(r"\s+", " ", line).strip(" -•\t")
    if len(line) < 10 or NOISE_PATTERNS.match(line):
        return ""
    return line[:110]


def extract_snippets_from_output(stdout: str, max_items: int) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()

    # Try JSON parse first; fall back to line-based concise markdown parsing.
    try:
        payload = json.loads(stdout)
        data = payload.get("data") if isinstance(payload, dict) else None
        items = []
        if isinstance(data, dict):
            items = data.get("items") or data.get("messages") or []
        elif isinstance(payload, list):
            items = payload
        for item in items:
            if not isinstance(item, dict):
                continue
            body = item.get("content") or item.get("text") or ""
            if isinstance(body, dict):
                body = body.get("text") or json.dumps(body, ensure_ascii=False)
            elif isinstance(body, str) and body.startswith("{"):
                try:
                    parsed = json.loads(body)
                    if isinstance(parsed, dict):
                        body = parsed.get("text") or parsed.get("title") or ""
                except json.JSONDecodeError:
                    pass
            if not isinstance(body, str):
                continue
            for raw_line in body.splitlines():
                cleaned = scrub_line(raw_line)
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    snippets.append(cleaned)
                    if len(snippets) >= max_items:
                        return snippets
    except json.JSONDecodeError:
        for raw_line in stdout.splitlines():
            cleaned = scrub_line(raw_line)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                snippets.append(cleaned)
                if len(snippets) >= max_items:
                    return snippets

    return snippets


def categorize_group(name: str) -> str:
    for kw in BASE_KEYWORDS:
        if kw in name:
            return f"{kw}相关群聊"
    return "近期活跃群聊"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-chats", type=int, default=3)
    parser.add_argument("--snippets-per-chat", type=int, default=5)
    args = parser.parse_args()

    lark_bin = find_lark_cli()
    if not lark_bin:
        print(json.dumps({"status": "unavailable", "reason": "lark_cli_not_found"}, ensure_ascii=False))
        return 0

    try:
        chats_proc = run_lark(
            lark_bin,
            ["im", "+chat-list", "--as", "user", "--sort", "active_time", "--page-size", "20", "--format", "json"],
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({"status": "unavailable", "reason": "timeout"}, ensure_ascii=False))
        return 0

    if chats_proc.returncode != 0:
        print(json.dumps({"status": "unavailable", "reason": "unauthenticated_or_error"}, ensure_ascii=False))
        return 0

    try:
        chats_payload = json.loads(chats_proc.stdout)
    except json.JSONDecodeError:
        print(json.dumps({"status": "unavailable", "reason": "invalid_chat_list_json"}, ensure_ascii=False))
        return 0

    data = chats_payload.get("data") if isinstance(chats_payload, dict) else {}
    raw_chats = (data.get("items") or data.get("chats") or []) if isinstance(data, dict) else []
    candidates: list[tuple[int, str, str]] = []
    for item in raw_chats:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("chat_id") or "")
        name = str(item.get("name") or "")
        if not cid.startswith("oc_"):
            continue
        score = 1 if any(kw in name for kw in BASE_KEYWORDS) else 0
        candidates.append((score, cid, name))

    # Prefer keyword-matched base groups while preserving recent-activity order.
    selected = sorted(candidates, key=lambda x: -x[0])[: max(1, args.max_chats)]

    topics = []
    for _, cid, name in selected:
        try:
            msg_proc = run_lark(
                lark_bin,
                [
                    "im",
                    "+chat-messages-list",
                    "--as",
                    "user",
                    "--chat-id",
                    cid,
                    "--page-size",
                    "25",
                    "--no-reactions",
                    "--format",
                    "json",
                ],
            )
        except subprocess.TimeoutExpired:
            continue
        if msg_proc.returncode != 0:
            continue
        snippets = extract_snippets_from_output(msg_proc.stdout, args.snippets_per_chat)
        if snippets:
            topics.append(
                {
                    "group_theme": categorize_group(name),
                    "recent_scene_fragments": snippets,
                }
            )

    print(
        json.dumps(
            {
                "status": "ok" if topics else "empty",
                "usage_note": "Use only as soft, non-literal 'Aha!' scene inspiration; never quote verbatim or imply surveillance.",
                "sampled_themes": topics,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
