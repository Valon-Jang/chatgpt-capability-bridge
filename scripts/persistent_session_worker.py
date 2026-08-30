#!/usr/bin/env python3
"""Persistent command worker for Capability Bridge browser sessions.

Keeps one browser alive, polls a repository command file, hot-loads the latest
adapter code for each new command, publishes structured results back to the
repository, and remains alive after adapter success or failure.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"
REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]
COMMAND_PATH = os.environ.get("CB_COMMAND_PATH", "experiments/session/exp002-command.json")
RESULT_PATH = os.environ.get("CB_RESULT_PATH", "experiments/session/exp002-result.json")
STATUS_PATH = os.environ.get("CB_STATUS_PATH", "experiments/session/exp002-status.json")
ADAPTER_PATH = os.environ.get("CB_ADAPTER_PATH", "adapters/naver-calendar/adapter.py")
SESSION_ADAPTER_PATH = os.environ.get("CB_SESSION_ADAPTER_PATH", "adapters/naver-calendar/session_adapter.py")
DEBUGGER_ADDRESS = os.environ.get("CB_DEBUGGER_ADDRESS", "127.0.0.1:9222")
POLL_SECONDS = int(os.environ.get("CB_POLL_SECONDS", "5"))
SOFT_LIMIT_SECONDS = int(os.environ.get("CB_SOFT_LIMIT_SECONDS", "20700"))  # 5h45m
AUTH_TIMEOUT_SECONDS = int(os.environ.get("CB_AUTH_TIMEOUT_SECONDS", str(SOFT_LIMIT_SECONDS)))


def request(path: str, method: str = "GET", payload: dict | None = None):
    url = f"{API}/repos/{REPO}/contents/{urllib.parse.quote(path, safe='/')}"
    if method == "GET":
        url += "?ref=main"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "chatgpt-capability-bridge-session-worker",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def read_text(path: str) -> str | None:
    try:
        item = request(path)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    return base64.b64decode(item["content"]).decode("utf-8")


def put_text(path: str, text: str, message: str) -> None:
    sha = None
    try:
        sha = request(path).get("sha")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    payload = {
        "message": message,
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    request(path, "PUT", payload)


def publish_json(path: str, payload: dict, message: str) -> None:
    put_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", message)


def status(state: str, **extra) -> None:
    payload = {
        "session_state": state,
        "updated_at_epoch": int(time.time()),
        **extra,
    }
    try:
        publish_json(STATUS_PATH, payload, f"Session status: {state} [skip ci]")
    except Exception as exc:
        print(f"STATUS_PUBLISH_WARNING: {type(exc).__name__}: {exc}", flush=True)


def run_command(command_text: str) -> dict:
    tmp = Path("/tmp/cb-persistent-session")
    tmp.mkdir(parents=True, exist_ok=True)
    command_file = tmp / "command.json"
    base_file = tmp / "adapter.py"
    session_file = tmp / "session_adapter.py"
    output_dir = tmp / "output"
    if output_dir.exists():
        for p in output_dir.iterdir():
            if p.is_file():
                p.unlink()
    else:
        output_dir.mkdir(parents=True)

    command_file.write_text(command_text, encoding="utf-8")
    base_text = read_text(ADAPTER_PATH)
    session_text = read_text(SESSION_ADAPTER_PATH)
    if base_text is None or session_text is None:
        return {
            "status": "FAILED",
            "failure_class": "SUBSTRATE_BOUNDARY",
            "message": "Latest adapter source could not be fetched from the repository.",
        }
    base_file.write_text(base_text, encoding="utf-8")
    session_file.write_text(session_text, encoding="utf-8")

    env = os.environ.copy()
    env["CB_ADAPTER_LIB"] = str(base_file)
    code = subprocess.call(
        [
            sys.executable,
            str(session_file),
            "--command",
            str(command_file),
            "--output-dir",
            str(output_dir),
            "--debugger-address",
            DEBUGGER_ADDRESS,
            "--auth-timeout",
            str(AUTH_TIMEOUT_SECONDS),
        ],
        env=env,
    )
    result_file = output_dir / "result.json"
    if result_file.exists():
        result = json.loads(result_file.read_text(encoding="utf-8"))
    else:
        result = {
            "status": "FAILED",
            "failure_class": "SUBSTRATE_BOUNDARY",
            "message": f"Session adapter exited {code} without a Result Envelope.",
        }
    result["session_adapter_exit_code"] = code
    result["persistent_browser_retained"] = True
    return result


def main() -> int:
    started = time.time()
    last_command_id = None
    status("SESSION_STARTING", browser_retained=True, hard_platform_limit="GitHub-hosted job: 6h")
    print("SESSION_WORKER_READY: browser will remain alive after command success/failure.", flush=True)

    while time.time() - started < SOFT_LIMIT_SECONDS:
        try:
            command_text = read_text(COMMAND_PATH)
            if not command_text:
                time.sleep(POLL_SECONDS)
                continue
            command = json.loads(command_text)
            if command.get("session_control") == "stop" or command.get("action") == "stop_session":
                status("STOP_REQUESTED", last_command_id=last_command_id)
                print("SESSION_STOP_REQUESTED", flush=True)
                return 0

            command_id = command.get("command_id")
            if not command_id or command_id == last_command_id:
                time.sleep(POLL_SECONDS)
                continue

            last_command_id = command_id
            status("COMMAND_RUNNING", command_id=command_id, browser_retained=True)
            print(f"COMMAND_RECEIVED: {command_id}", flush=True)
            result = run_command(command_text)
            result["session_command_id"] = command_id
            publish_json(RESULT_PATH, result, f"Session result for {command_id} [skip ci]")
            status(
                "SESSION_IDLE",
                last_command_id=command_id,
                last_result_status=result.get("status"),
                last_failure_class=result.get("failure_class"),
                browser_retained=True,
            )
            print(
                f"COMMAND_COMPLETE: {command_id} status={result.get('status')} failure={result.get('failure_class')}; session remains alive.",
                flush=True,
            )
        except Exception as exc:
            print(f"SESSION_LOOP_WARNING: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(POLL_SECONDS)

    status("HOSTED_RUNNER_LIMIT_APPROACHING", last_command_id=last_command_id, browser_retained=True)
    print("HOSTED_RUNNER_LIMIT_APPROACHING: session worker is yielding before GitHub's 6h hard limit.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
