#!/usr/bin/env python3
"""Run Naver Calendar commands against an already-running authenticated Chrome.

Chrome is owned by the persistent-session workflow. This process attaches through
remote debugging and intentionally never quits the browser. Credentials and raw
session values are never logged or persisted by this adapter.
"""
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


def observe_title_on_calendar(driver, base, title: str, timeout: float = 15.0) -> bool:
    goto_calendar(driver, base)
    return base.wait_for_exact_text(driver, title, timeout=timeout)


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
            "placeholder": el.get_attribute("placeholder"),
            "aria_label": el.get_attribute("aria-label"),
            "contenteditable": el.get_attribute("contenteditable"),
        }
    except WebDriverException:
        return {"unavailable": True}


def find_real_title_input(driver, base):
    """Prefer the title textarea observed on Naver Calendar /add."""
    driver.switch_to.default_content()
    selectors = [
        "textarea[placeholder='일정을 입력하세요.']",
        "textarea[placeholder*='일정']",
    ]
    for selector in selectors:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                if el.is_displayed():
                    return el
        except WebDriverException:
            continue
    return base.find_title_input(driver)


def delete_observed_title(driver, base, title: str, result: dict, result_path: Path) -> int:
    result["cleanup"]["attempted"] = True
    if not base.click_text(driver, [title], timeout=8):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Observed synthetic event could not be opened for cleanup."
        base.write_json(result_path, result)
        return 8

    time.sleep(1)
    if not base.click_text(driver, ["삭제"], timeout=4):
        base.open_more_menu(driver)
        if not base.click_text(driver, ["삭제", "일정 삭제"], timeout=7):
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Synthetic event could not be deleted through the visible UI."
            base.write_json(result_path, result)
            return 9

    time.sleep(0.7)
    base.click_text(driver, ["삭제", "확인", "예"], timeout=3)
    time.sleep(2)
    goto_calendar(driver, base, settle=1.5)

    cleanup_absent = not base.exact_text_present(driver, title)
    result["verification"]["evidence"]["cleanup_absence_observed"] = cleanup_absent
    result["cleanup"]["completed"] = cleanup_absent
    if not cleanup_absent:
        result["failure_class"] = "VERIFY_FAILED"
        result["message"] = "Synthetic event was opened for deletion, but absence could not be verified afterward."
        base.write_json(result_path, result)
        return 10
    return 0


def diagnose_form(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    result = base.result_template(command)
    result_path = output_dir / "result.json"
    diagnostics_path = output_dir / "form-structure.json"
    result["cleanup"] = {"requested": False, "attempted": False, "completed": True}
    result["execution"]["attempted"] = True

    goto_calendar(driver, base)
    if not base.wait_for_auth(driver, auth_timeout):
        result["failure_class"] = "AUTH_BOUNDARY"
        result["message"] = "Authenticated persistent session was not detected."
        base.write_json(result_path, result)
        return 3

    if not base.open_schedule_write_ui(driver, diagnostics_path):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Could not enter the schedule-writing UI for diagnostics."
        base.write_json(result_path, result)
        return 4

    time.sleep(0.8)
    structure = base.form_metadata(driver)
    candidate = find_real_title_input(driver, base)
    result["diagnostics"] = {
        "page_url_without_query": (driver.current_url or "").split("?", 1)[0],
        "form_structure": structure,
        "selected_title_candidate": safe_element_descriptor(candidate),
    }
    result["execution"]["completed"] = True
    result["verification"]["performed"] = True
    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = "Non-mutating schedule-form diagnostics captured without field values or session secrets."
    base.write_json(result_path, result)
    return 0


def recover_existing(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    result = base.result_template(command)
    result_path = output_dir / "result.json"
    title = (command.get("arguments") or {}).get("title")
    if not title or not isinstance(title, str):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Missing string arguments.title"
        base.write_json(result_path, result)
        return 2

    result["execution"]["attempted"] = True
    goto_calendar(driver, base)
    if not base.wait_for_auth(driver, auth_timeout):
        result["failure_class"] = "AUTH_BOUNDARY"
        result["message"] = "Authenticated persistent session was not detected."
        base.write_json(result_path, result)
        return 3

    result["verification"]["performed"] = True
    found = observe_title_on_calendar(driver, base, title, timeout=12)
    result["verification"]["evidence"]["created_title_observed"] = found
    result["execution"]["completed"] = True

    if found:
        code = delete_observed_title(driver, base, title, result, result_path)
        if code:
            return code
        result["message"] = "Residual synthetic event was observed and successfully deleted; absence verified."
    else:
        result["verification"]["evidence"]["cleanup_absence_observed"] = True
        result["cleanup"]["completed"] = True
        result["message"] = "No residual synthetic event was observable on the calendar; cleanup state is clear."

    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    base.write_json(result_path, result)
    base.log("VERIFIED_SUCCESS: residual synthetic event state checked and cleanup verified; browser kept alive.")
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

    driver.set_page_load_timeout(45)
    goto_calendar(driver, base)
    result["execution"]["attempted"] = True

    if not base.wait_for_auth(driver, auth_timeout):
        result["failure_class"] = "AUTH_BOUNDARY"
        result["message"] = "Authentication was not completed before the handoff timeout."
        base.write_json(result_path, result)
        return 3

    if not base.open_schedule_write_ui(driver, diagnostics_path):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Could not enter the schedule-writing UI after opening the schedule launcher."
        base.write_json(result_path, result)
        return 4

    time.sleep(0.5)
    base.write_json(diagnostics_path, base.form_metadata(driver))
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

    if not base.click_text(driver, ["저장", "완료", "등록"], timeout=12):
        driver.switch_to.default_content()
        if not base.click_text(driver, ["저장", "완료", "등록"], timeout=6):
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Could not locate the save action."
            base.write_json(result_path, result)
            return 6

    result["execution"]["completed"] = True
    result["verification"]["performed"] = True

    created = observe_title_on_calendar(driver, base, title, timeout=15)
    result["verification"]["evidence"]["created_title_observed"] = created
    if not created:
        result["failure_class"] = "VERIFY_FAILED"
        result["message"] = "Save was attempted using the observed title textarea, then the calendar was reloaded, but the nonce-bearing event title was not observed."
        base.write_json(result_path, result)
        return 7

    code = delete_observed_title(driver, base, title, result, result_path)
    if code:
        return code

    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = "Nonce-bearing event was created, calendar-observed, deleted, and absence-verified through the browser UI."
    base.write_json(result_path, result)
    base.log("VERIFIED_SUCCESS: create -> calendar observe -> delete -> absence verified; browser kept alive.")
    return 0


def execute(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    try:
        action = command.get("action")
        if action == "diagnose_schedule_form":
            return diagnose_form(driver, base, command, output_dir, auth_timeout)
        if action == "recover_verify_delete_event":
            return recover_existing(driver, base, command, output_dir, auth_timeout)
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
            driver.switch_to.default_content()
            driver.get(base.TARGET_URL)
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
