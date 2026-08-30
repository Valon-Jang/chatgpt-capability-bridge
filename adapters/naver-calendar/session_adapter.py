#!/usr/bin/env python3
"""Run one Naver Calendar command against an already-running Chrome session.

The Chrome process is owned by the persistent-session workflow. This process
attaches through Chrome remote debugging, executes one command, then detaches
without closing the browser. Credentials and cookie values are never printed or
persisted by this adapter.
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


def execute(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    result = base.result_template(command)
    result_path = output_dir / "result.json"
    diagnostics_path = output_dir / "form-structure.json"
    args = command.get("arguments") or {}
    title = args.get("title")
    if not title or not isinstance(title, str):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Missing string arguments.title"
        base.write_json(result_path, result)
        return 2

    try:
        driver.set_page_load_timeout(45)
        driver.switch_to.default_content()
        driver.get(base.TARGET_URL)
        result["execution"]["attempted"] = True

        if not base.wait_for_auth(driver, auth_timeout):
            result["failure_class"] = "AUTH_BOUNDARY"
            result["message"] = "Authentication was not completed before the handoff timeout."
            base.write_json(result_path, result)
            return 3

        driver.get(base.TARGET_URL)
        WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")

        if not base.open_schedule_write_ui(driver, diagnostics_path):
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Could not enter the schedule-writing UI after opening the schedule launcher."
            base.write_json(result_path, result)
            return 4

        time.sleep(0.5)
        base.write_json(diagnostics_path, base.form_metadata(driver))
        title_input = base.find_title_input(driver)
        if title_input is None:
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Could not identify a visible event-title input after entering schedule-writing UI."
            base.write_json(result_path, result)
            return 5

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

        driver.switch_to.default_content()
        result["execution"]["completed"] = True
        time.sleep(2)
        result["verification"]["performed"] = True
        created = base.wait_for_exact_text(driver, title, timeout=15)
        result["verification"]["evidence"]["created_title_observed"] = created
        if not created:
            result["failure_class"] = "VERIFY_FAILED"
            result["message"] = "Save was attempted but the nonce-bearing event title was not observed."
            base.write_json(result_path, result)
            return 7

        result["cleanup"]["attempted"] = True
        if not base.click_text(driver, [title], timeout=8):
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Created event was observed but could not be opened for cleanup."
            base.write_json(result_path, result)
            return 8

        time.sleep(1)
        if not base.click_text(driver, ["삭제"], timeout=4):
            base.open_more_menu(driver)
            if not base.click_text(driver, ["삭제", "일정 삭제"], timeout=7):
                result["failure_class"] = "ADAPTER_ERROR"
                result["message"] = "Created event could not be deleted through the visible UI."
                base.write_json(result_path, result)
                return 9

        time.sleep(0.7)
        base.click_text(driver, ["삭제", "확인", "예"], timeout=3)
        time.sleep(2)
        if title in driver.page_source:
            try:
                driver.back()
                time.sleep(1.5)
            except WebDriverException:
                pass

        cleanup_absent = not base.exact_text_present(driver, title)
        result["verification"]["evidence"]["cleanup_absence_observed"] = cleanup_absent
        result["cleanup"]["completed"] = cleanup_absent
        if not cleanup_absent:
            result["failure_class"] = "VERIFY_FAILED"
            result["message"] = "Event creation was verified, but cleanup absence could not be verified."
            base.write_json(result_path, result)
            return 10

        result["verification"]["passed"] = True
        result["status"] = "VERIFIED_SUCCESS"
        result["failure_class"] = None
        result["message"] = "Nonce-bearing event was created, observed, deleted, and absence-verified through the browser UI."
        base.write_json(result_path, result)
        base.log("VERIFIED_SUCCESS: create -> observe -> delete -> absence verified; browser kept alive.")
        return 0
    except Exception as exc:
        result["failure_class"] = result.get("failure_class") or "ADAPTER_ERROR"
        result["message"] = f"Unexpected attached-session adapter failure: {type(exc).__name__}: {exc}"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        base.write_json(result_path, result)
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
    parser.add_argument("--auth-timeout", type=int, default=20700)
    args = parser.parse_args()

    base = load_base()
    command = json.loads(Path(args.command).read_text(encoding="utf-8"))
    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", args.debugger_address)
    driver = webdriver.Chrome(options=options)
    # Intentionally do NOT call driver.quit(): Chrome is owned by the session workflow.
    return execute(driver, base, command, Path(args.output_dir), args.auth_timeout)


if __name__ == "__main__":
    sys.exit(main())
