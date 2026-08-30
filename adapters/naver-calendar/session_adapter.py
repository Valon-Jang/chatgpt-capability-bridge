#!/usr/bin/env python3
"""Persistent Naver Calendar adapter for an already-authenticated Chrome session."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait


def load_base():
    path = Path(os.environ.get("CB_ADAPTER_LIB", Path(__file__).with_name("adapter.py")))
    spec = importlib.util.spec_from_file_location("cb_naver_calendar_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load adapter library: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def goto_calendar(driver, base, settle: float = 2.0) -> None:
    driver.switch_to.default_content()
    driver.get(base.TARGET_URL)
    WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(settle)


def safe_element_descriptor(el) -> dict | None:
    if el is None:
        return None
    try:
        return {
            "tag": el.tag_name,
            "type": el.get_attribute("type"),
            "name": el.get_attribute("name"),
            "id": el.get_attribute("id"),
            "class": el.get_attribute("class"),
            "title": el.get_attribute("title"),
            "placeholder": el.get_attribute("placeholder"),
            "aria_label": el.get_attribute("aria-label"),
            "contenteditable": el.get_attribute("contenteditable"),
        }
    except WebDriverException:
        return {"unavailable": True}


def safe_action_controls(driver) -> list[dict]:
    """Visible action-control structure only; never capture input values or arbitrary page text."""
    controls: list[dict] = []
    driver.switch_to.default_content()
    for el in driver.find_elements(By.CSS_SELECTOR, "button,a,[role='button']"):
        try:
            if not el.is_displayed():
                continue
            text = (el.text or "").strip()
            if len(text) > 50:
                text = text[:50] + "…"
            controls.append(
                {
                    "tag": el.tag_name,
                    "type": el.get_attribute("type"),
                    "id": el.get_attribute("id"),
                    "class": el.get_attribute("class"),
                    "title": el.get_attribute("title"),
                    "aria_label": el.get_attribute("aria-label"),
                    "ui_text": text or None,
                }
            )
        except WebDriverException:
            continue
    return controls[:100]


def find_real_title_input(driver, base):
    driver.switch_to.default_content()
    for selector in [
        "textarea[placeholder='일정을 입력하세요.']",
        "textarea[placeholder*='일정']",
    ]:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                if el.is_displayed():
                    return el
        except WebDriverException:
            continue
    return base.find_title_input(driver)


def ensure_auth(driver, base, auth_timeout: int, result: dict, result_path: Path) -> bool:
    goto_calendar(driver, base)
    if base.wait_for_auth(driver, auth_timeout):
        return True
    result["failure_class"] = "AUTH_BOUNDARY"
    result["message"] = "Authenticated persistent session was not detected."
    base.write_json(result_path, result)
    return False


def open_existing_event(driver, base, title: str, timeout: float = 12.0) -> bool:
    goto_calendar(driver, base)
    if not base.wait_for_exact_text(driver, title, timeout=timeout):
        return False
    return base.click_text(driver, [title], timeout=8)


def diagnose_schedule_form(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    result = base.result_template(command)
    result_path = output_dir / "result.json"
    diagnostics_path = output_dir / "form-structure.json"
    result["cleanup"] = {"requested": False, "attempted": False, "completed": True}
    result["execution"]["attempted"] = True
    if not ensure_auth(driver, base, auth_timeout, result, result_path):
        return 3
    if not base.open_schedule_write_ui(driver, diagnostics_path):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Could not enter the schedule-writing UI for diagnostics."
        base.write_json(result_path, result)
        return 4
    time.sleep(0.8)
    candidate = find_real_title_input(driver, base)
    result["diagnostics"] = {
        "page_url_without_query": (driver.current_url or "").split("?", 1)[0],
        "form_structure": base.form_metadata(driver),
        "action_controls": safe_action_controls(driver),
        "selected_title_candidate": safe_element_descriptor(candidate),
    }
    result["execution"]["completed"] = True
    result["verification"]["performed"] = True
    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = "Non-mutating schedule-form diagnostics captured."
    base.write_json(result_path, result)
    return 0


def diagnose_event_detail(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    result = base.result_template(command)
    result_path = output_dir / "result.json"
    title = (command.get("arguments") or {}).get("title")
    result["cleanup"] = {"requested": False, "attempted": False, "completed": True}
    if not title or not isinstance(title, str):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Missing string arguments.title"
        base.write_json(result_path, result)
        return 2
    result["execution"]["attempted"] = True
    if not ensure_auth(driver, base, auth_timeout, result, result_path):
        return 3
    result["verification"]["performed"] = True
    if not open_existing_event(driver, base, title):
        result["failure_class"] = "VERIFY_FAILED"
        result["message"] = "Synthetic event title was not observable/openable for detail diagnostics."
        base.write_json(result_path, result)
        return 7
    result["verification"]["evidence"]["created_title_observed"] = True
    time.sleep(1.0)
    result["diagnostics"] = {
        "page_url_without_query": (driver.current_url or "").split("?", 1)[0],
        "detail_form_structure": base.form_metadata(driver),
        "detail_action_controls": safe_action_controls(driver),
    }
    result["execution"]["completed"] = True
    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = "Non-mutating event-detail diagnostics captured."
    base.write_json(result_path, result)
    return 0


def delete_open_event(driver, base, title: str, result: dict, result_path: Path) -> int:
    result["cleanup"]["attempted"] = True
    if not base.click_text(driver, ["삭제", "일정 삭제"], timeout=4):
        base.open_more_menu(driver)
        if not base.click_text(driver, ["삭제", "일정 삭제"], timeout=7):
            result.setdefault("diagnostics", {})["detail_action_controls"] = safe_action_controls(driver)
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Synthetic event could not be deleted through the visible UI."
            base.write_json(result_path, result)
            return 9
    time.sleep(0.7)
    base.click_text(driver, ["삭제", "확인", "예"], timeout=3)
    time.sleep(2)
    goto_calendar(driver, base, settle=1.5)
    absent = not base.exact_text_present(driver, title)
    result["verification"]["evidence"]["cleanup_absence_observed"] = absent
    result["cleanup"]["completed"] = absent
    if not absent:
        result["failure_class"] = "VERIFY_FAILED"
        result["message"] = "Deletion was attempted, but synthetic event absence could not be verified."
        base.write_json(result_path, result)
        return 10
    return 0


def recover_verify_delete(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    result = base.result_template(command)
    result_path = output_dir / "result.json"
    title = (command.get("arguments") or {}).get("title")
    if not title or not isinstance(title, str):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Missing string arguments.title"
        base.write_json(result_path, result)
        return 2
    result["execution"]["attempted"] = True
    if not ensure_auth(driver, base, auth_timeout, result, result_path):
        return 3
    result["verification"]["performed"] = True
    goto_calendar(driver, base)
    found = base.wait_for_exact_text(driver, title, timeout=12)
    result["verification"]["evidence"]["created_title_observed"] = found
    result["execution"]["completed"] = True
    if not found:
        result["verification"]["evidence"]["cleanup_absence_observed"] = True
        result["cleanup"]["completed"] = True
        result["verification"]["passed"] = True
        result["status"] = "VERIFIED_SUCCESS"
        result["failure_class"] = None
        result["message"] = "No residual synthetic event was observable; cleanup state is clear."
        base.write_json(result_path, result)
        return 0
    if not base.click_text(driver, [title], timeout=8):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Observed synthetic event could not be opened for cleanup."
        base.write_json(result_path, result)
        return 8
    time.sleep(1)
    code = delete_open_event(driver, base, title, result, result_path)
    if code:
        return code
    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = "Residual synthetic event was observed, deleted, and absence-verified."
    base.write_json(result_path, result)
    return 0


def create_verify_delete(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    result = base.result_template(command)
    result_path = output_dir / "result.json"
    diagnostics_path = output_dir / "form-structure.json"
    title = (command.get("arguments") or {}).get("title")
    if not title or not isinstance(title, str):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Missing string arguments.title"
        base.write_json(result_path, result)
        return 2
    result["execution"]["attempted"] = True
    if not ensure_auth(driver, base, auth_timeout, result, result_path):
        return 3
    if not base.open_schedule_write_ui(driver, diagnostics_path):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Could not enter the schedule-writing UI."
        base.write_json(result_path, result)
        return 4
    time.sleep(0.5)
    title_input = find_real_title_input(driver, base)
    if title_input is None:
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Could not identify the actual schedule-title textarea."
        base.write_json(result_path, result)
        return 5
    result["diagnostics"] = {"selected_title_candidate": safe_element_descriptor(title_input)}
    title_input.click()
    title_input.send_keys(Keys.CONTROL, "a")
    title_input.send_keys(title)
    if not base.click_text(driver, ["저장"], timeout=12):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Could not locate the save action."
        base.write_json(result_path, result)
        return 6
    result["execution"]["completed"] = True
    result["verification"]["performed"] = True
    goto_calendar(driver, base)
    created = base.wait_for_exact_text(driver, title, timeout=15)
    result["verification"]["evidence"]["created_title_observed"] = created
    if not created:
        result["failure_class"] = "VERIFY_FAILED"
        result["message"] = "Event title was not observed after save and calendar reload."
        base.write_json(result_path, result)
        return 7
    if not base.click_text(driver, [title], timeout=8):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Created synthetic event could not be opened for cleanup."
        base.write_json(result_path, result)
        return 8
    time.sleep(1)
    code = delete_open_event(driver, base, title, result, result_path)
    if code:
        return code
    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = "Nonce-bearing event was created, observed, deleted, and absence-verified."
    base.write_json(result_path, result)
    return 0


def execute(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    try:
        action = command.get("action")
        if action == "diagnose_schedule_form":
            return diagnose_schedule_form(driver, base, command, output_dir, auth_timeout)
        if action == "diagnose_event_detail":
            return diagnose_event_detail(driver, base, command, output_dir, auth_timeout)
        if action == "recover_verify_delete_event":
            return recover_verify_delete(driver, base, command, output_dir, auth_timeout)
        if action == "create_verify_delete_event":
            return create_verify_delete(driver, base, command, output_dir, auth_timeout)
        result = base.result_template(command)
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = f"Unsupported session action: {action}"
        base.write_json(output_dir / "result.json", result)
        return 2
    except Exception as exc:
        result = base.result_template(command)
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = f"Unexpected attached-session adapter failure: {type(exc).__name__}: {exc}"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        base.write_json(output_dir / "result.json", result)
        try:
            goto_calendar(driver, base)
        except Exception:
            pass
        return 11


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--debugger-address", default="127.0.0.1:9222")
    parser.add_argument("--auth-timeout", type=int, default=60)
    args = parser.parse_args()
    base = load_base()
    command = json.loads(Path(args.command).read_text(encoding="utf-8"))
    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", args.debugger_address)
    driver = webdriver.Chrome(options=options)
    return execute(driver, base, command, Path(args.output_dir), args.auth_timeout)


if __name__ == "__main__":
    sys.exit(main())
