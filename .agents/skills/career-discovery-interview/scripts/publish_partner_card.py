#!/usr/bin/env python3
"""Publish or update `career-discovery/partner-card.md` as a permanent shareable link.

Primary channel (`feishu`): Creates a Feishu Cloud Doc in the student's own Drive via
`lark-cli docs +create` on first run, saves the token locally in
`career-discovery/.card-link.json`, and updates the SAME URL in place via
`lark-cli docs +update --command overwrite` on future runs so the student's Feishu
profile bio link never changes.

Fallback channel (`gist`): Creates or edits a GitHub Gist via `gh gist` when `lark-cli`
is unavailable.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


def find_bin(name: str) -> str | None:
    for candidate in (
        Path.home() / ".local" / "bin" / name,
        Path.home() / ".homebrew" / "bin" / name,
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(name)


def run_cmd(cmd: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.setdefault("LARK_CLI_NO_PROXY_WARN", "1")
    return subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
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

    # If external link sharing is restricted by tenant policy, fall back to tenant_readable.
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
    share: str,
    confirm_share: bool,
) -> dict:
    state = load_state(state_path)
    doc_id = state.get("feishu_doc_id")
    url = state.get("feishu_url")
    content_arg = f"@{card_path}"

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
                "markdown",
                "--content",
                content_arg,
            ]
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
                "channel": "feishu",
                "action": "updated_in_place",
                "url": url or f"feishu://docx/{doc_id}",
                "share": applied_share,
                "warning": share_warn,
            }

    # Create new Feishu Cloud Doc
    crt = run_cmd(
        [
            lark_bin,
            "docs",
            "+create",
            "--as",
            "user",
            "--doc-format",
            "markdown",
            "--title",
            title,
            "--content",
            content_arg,
        ]
    )
    if crt.returncode != 0:
        return {
            "status": "error",
            "channel": "feishu",
            "error": (crt.stderr or crt.stdout).strip()[:300],
        }

    payload = json.loads(crt.stdout)
    doc = ((payload.get("data") or {}).get("document")) or {}
    new_doc_id = doc.get("document_id")
    new_url = doc.get("url")
    if not new_doc_id:
        return {"status": "error", "channel": "feishu", "error": "missing_document_id_in_response"}

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
        "channel": "feishu",
        "action": "created",
        "url": new_url,
        "share": applied_share,
        "warning": share_warn,
    }


def publish_gist(gh_bin: str, card_path: Path, state_path: Path, title: str, public: bool) -> dict:
    state = load_state(state_path)
    gist_id = state.get("gist_id")
    gist_url = state.get("gist_url")

    if gist_id:
        upd = run_cmd([gh_bin, "gist", "edit", gist_id, str(card_path)])
        if upd.returncode == 0:
            return {
                "status": "ok",
                "channel": "gist",
                "action": "updated_in_place",
                "url": gist_url or f"https://gist.github.com/{gist_id}",
            }

    cmd = [gh_bin, "gist", "create", str(card_path), "--desc", title]
    if public:
        cmd.append("--public")
    crt = run_cmd(cmd)
    if crt.returncode != 0:
        return {"status": "error", "channel": "gist", "error": (crt.stderr or crt.stdout).strip()[:300]}

    url = next((line.strip() for line in crt.stdout.splitlines() if line.strip().startswith("http")), "")
    new_id = url.rstrip("/").split("/")[-1] if url else ""
    state.update({"gist_id": new_id, "gist_url": url})
    save_state(state_path, state)
    return {"status": "ok", "channel": "gist", "action": "created", "url": url}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", type=Path, default=Path("career-discovery/partner-card.md"))
    parser.add_argument("--state", type=Path, default=Path("career-discovery/.card-link.json"))
    parser.add_argument("--title", default="互补搭档协作名片")
    parser.add_argument("--channel", choices=("auto", "feishu", "gist"), default="auto")
    parser.add_argument(
        "--share",
        choices=("none", "tenant_readable", "anyone_readable"),
        default="tenant_readable",
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

    lark_bin = find_bin("lark-cli")
    gh_bin = find_bin("gh")

    if args.channel in ("auto", "feishu") and lark_bin:
        res = publish_feishu(lark_bin, args.card, args.state, args.title, args.share, args.confirm_share)
        if res["status"] == "ok" or args.channel == "feishu":
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0 if res["status"] == "ok" else 1

    if args.channel in ("auto", "gist") and gh_bin:
        res = publish_gist(
            gh_bin,
            args.card,
            args.state,
            args.title,
            public=(args.confirm_share and args.share == "anyone_readable"),
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["status"] == "ok" else 1

    print(
        json.dumps(
            {
                "status": "unavailable",
                "reason": "neither_lark_cli_nor_gh_available",
                "hint": "Copy career-discovery/partner-card.md into a Feishu Cloud Doc manually.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
