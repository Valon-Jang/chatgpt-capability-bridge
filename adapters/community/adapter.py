#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def result_template(command: dict) -> dict:
    return {
        "status": "FAILED",
        "failure_class": None,
        "message": "",
        "site": command.get("site"),
        "action": command.get("action"),
        "command_id": command.get("command_id"),
        "execution": {"attempted": False, "completed": False},
        "verification": {"performed": False, "passed": False, "evidence": {}},
    }
