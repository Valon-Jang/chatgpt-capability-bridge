#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from selenium import webdriver

SITE_MAP = {
    "reddit": ("adapters/reddit/adapter.py", "adapters/reddit/session_adapter.py"),
    "geeknews": ("adapters/geeknews/adapter.py", "adapters/geeknews/session_adapter.py"),
}
SITE_URLS = {
    "reddit": "https://www.reddit.com/r/LocalLLaMA/",
    "geeknews": "https://news.hada.io/",
    "hackernews": "https://news.ycombinator.com/",
}


def repo_text(path: str) -> str:
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}?ref=main"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "chatgpt-capability-bridge-community-hub",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return base64.b64decode(payload["content"]).decode("utf-8")


def write_result(path: Path, command: dict, status: str, message: str, evidence: dict | None = None, failure_class: str | None = None) -> int:
    result = {
        "status": status,
        "failure_class": failure_class,
        "message": message,
        "site": command.get("site"),
        "action": command.get("action"),
        "command_id": command.get("command_id"),
        "execution": {"attempted": True, "completed": status == "VERIFIED_SUCCESS"},
        "verification": {"performed": True, "passed": status == "VERIFIED_SUCCESS", "evidence": evidence or {}},
    }
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if status == "VERIFIED_SUCCESS" else 2


def hub_action(command: dict, output_dir: Path, debugger_address: str) -> int:
    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", debugger_address)
    driver = webdriver.Chrome(options=options)
    action = command.get("action")
    result_path = output_dir / "result.json"
    if action == "hub_status":
        tabs = []
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            tabs.append({"url": driver.current_url, "title": driver.title})
        return write_result(result_path, command, "VERIFIED_SUCCESS", "AI Community Hub browser session is active.", {"tabs": tabs, "supported_sites": sorted(SITE_MAP)})
    if action == "open_sites":
        requested = (command.get("arguments") or {}).get("sites") or ["reddit", "geeknews", "hackernews"]
        opened = []
        current_urls = []
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            current_urls.append(driver.current_url)
        for site in requested:
            url = SITE_URLS.get(site)
            if not url:
                continue
            if not any(url.split('/')[2] in existing for existing in current_urls):
                driver.execute_script("window.open(arguments[0], '_blank');", url)
                opened.append(site)
        return write_result(result_path, command, "VERIFIED_SUCCESS", "Requested community tabs opened without posting anything.", {"opened_sites": opened, "requested_sites": requested})
    return write_result(result_path, command, "FAILED", f"Unsupported hub action: {action}", failure_class="INVALID_COMMAND")


def delegate(command: dict, output_dir: Path, debugger_address: str, auth_timeout: int) -> int:
    site = command.get("site")
    if site not in SITE_MAP:
        return write_result(output_dir / "result.json", command, "FAILED", f"Unsupported community site: {site}", failure_class="INVALID_COMMAND")
    base_path, session_path = SITE_MAP[site]
    with tempfile.TemporaryDirectory(prefix=f"cb-community-{site}-") as tmp:
        tmp_path = Path(tmp)
        base_file = tmp_path / "adapter.py"
        session_file = tmp_path / "session_adapter.py"
        command_file = tmp_path / "command.json"
        base_file.write_text(repo_text(base_path), encoding="utf-8")
        session_file.write_text(repo_text(session_path), encoding="utf-8")
        forwarded = dict(command)
        forwarded.pop("site", None)
        command_file.write_text(json.dumps(forwarded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        env = os.environ.copy()
        env["CB_ADAPTER_LIB"] = str(base_file)
        code = subprocess.call([
            sys.executable,
            str(session_file),
            "--command", str(command_file),
            "--output-dir", str(output_dir),
            "--debugger-address", debugger_address,
            "--auth-timeout", str(auth_timeout),
        ], env=env)
        result_path = output_dir / "result.json"
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["site"] = site
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--command", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--debugger-address", default="127.0.0.1:9222")
    ap.add_argument("--auth-timeout", type=int, default=60)
    args = ap.parse_args()
    command = json.loads(Path(args.command).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if command.get("action") in {"hub_status", "open_sites"}:
        return hub_action(command, output_dir, args.debugger_address)
    return delegate(command, output_dir, args.debugger_address, args.auth_timeout)


if __name__ == "__main__":
    raise SystemExit(main())
