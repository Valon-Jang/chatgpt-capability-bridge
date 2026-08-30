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
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
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


def goto_calendar(driver, base, settle: float = 1.5) -> None:
    driver.switch_to.default_content()
    driver.get(base.TARGET_URL)
    WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(settle)


def visible(elements):
    out = []
    for el in elements:
        try:
            if el.is_displayed():
                out.append(el)
        except WebDriverException:
            pass
    return out


def safe_desc(el) -> dict | None:
    if el is None:
        return None
    try:
        return {
            "tag": el.tag_name,
            "type": el.get_attribute("type"),
            "id": el.get_attribute("id"),
            "class": el.get_attribute("class"),
            "title": el.get_attribute("title"),
            "aria_label": el.get_attribute("aria-label"),
            "placeholder": el.get_attribute("placeholder"),
        }
    except WebDriverException:
        return {"unavailable": True}


def safe_action_controls(driver) -> list[dict]:
    controls = []
    driver.switch_to.default_content()
    for el in driver.find_elements(By.CSS_SELECTOR, "button,a,[role='button']"):
        try:
            if not el.is_displayed():
                continue
            text = (el.text or "").strip()
            if len(text) > 40:
                text = text[:40] + "…"
            controls.append({
                "tag": el.tag_name,
                "type": el.get_attribute("type"),
                "id": el.get_attribute("id"),
                "class": el.get_attribute("class"),
                "title": el.get_attribute("title"),
                "aria_label": el.get_attribute("aria-label"),
                "ui_text": text or None,
            })
        except WebDriverException:
            continue
    return controls[:100]


def ensure_auth(driver, base, timeout: int, result: dict, result_path: Path) -> bool:
    goto_calendar(driver, base)
    if base.wait_for_auth(driver, timeout):
        return True
    result["failure_class"] = "AUTH_BOUNDARY"
    result["message"] = "Authenticated persistent session was not detected."
    base.write_json(result_path, result)
    return False


def find_real_title_input(driver, base):
    driver.switch_to.default_content()
    for selector in ["textarea[placeholder='일정을 입력하세요.']", "textarea[placeholder*='일정']"]:
        for el in visible(driver.find_elements(By.CSS_SELECTOR, selector)):
            return el
    return base.find_title_input(driver)


def detail_open(driver) -> bool:
    try:
        if visible(driver.find_elements(By.XPATH, "//*[self::button or self::a or @role='button'][normalize-space(.)='수정']")):
            return True
    except WebDriverException:
        pass
    path = urlparse(driver.current_url or "").path
    return path not in {"/", "/daily"} and "add" not in path


def open_event_detail(driver, base, title: str, timeout: float = 12.0) -> bool:
    """Open the synthetic event by clicking its actual card/ancestor, not just text."""
    goto_calendar(driver, base)
    if not base.wait_for_exact_text(driver, title, timeout=timeout):
        return False

    xpath = f"//*[normalize-space(.)={json.dumps(title, ensure_ascii=False)}]"
    nodes = visible(driver.find_elements(By.XPATH, xpath))
    for node in nodes:
        chain = []
        cur = node
        for _ in range(8):
            try:
                chain.append(cur)
                cur = cur.find_element(By.XPATH, "..")
            except WebDriverException:
                break

        # Prefer interactive-looking ancestors before the raw text node.
        ranked = []
        for el in chain:
            try:
                tag = (el.tag_name or "").lower()
                role = (el.get_attribute("role") or "").lower()
                cls = (el.get_attribute("class") or "").lower()
                href = el.get_attribute("href") or ""
                score = 0
                if tag in {"a", "button"}: score += 50
                if role == "button": score += 40
                if href: score += 30
                if any(k in cls for k in ["schedule", "event", "item", "card", "plan"]): score += 20
                if el == node: score -= 5
                ranked.append((score, el, href))
            except WebDriverException:
                continue
        ranked.sort(key=lambda x: x[0], reverse=True)

        for _, target, href in ranked:
            try:
                ActionChains(driver).move_to_element(target).click().perform()
            except Exception:
                try:
                    target.click()
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", target)
                    except Exception:
                        continue
            time.sleep(0.9)
            if detail_open(driver):
                return True

            # If the card exposes a same-origin href, navigate directly as fallback.
            if href:
                try:
                    parsed = urlparse(href)
                    if parsed.netloc in {"m.calendar.naver.com", "calendar.naver.com"}:
                        driver.get(href)
                        time.sleep(1.0)
                        if detail_open(driver):
                            return True
                except Exception:
                    pass
    return False


def click_trash_on_edit(driver) -> bool:
    """Naver mobile web: detail -> 수정 -> trash icon in edit layer."""
    selectors = [
        "button[aria-label*='삭제']", "button[title*='삭제']",
        "[role='button'][aria-label*='삭제']", "[role='button'][title*='삭제']",
        "button[class*='delete']", "button[class*='trash']",
        "[role='button'][class*='delete']", "[role='button'][class*='trash']",
        "a[class*='delete']", "a[class*='trash']",
    ]
    for selector in selectors:
        for el in visible(driver.find_elements(By.CSS_SELECTOR, selector)):
            try:
                ActionChains(driver).move_to_element(el).click().perform()
                return True
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", el)
                    return True
                except Exception:
                    pass
    # Some builds expose textual delete in the edit layer.
    return False


def delete_existing(driver, base, title: str, result: dict, result_path: Path) -> int:
    result["cleanup"]["attempted"] = True
    if not open_event_detail(driver, base, title):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Synthetic event was visible but its detail card could not be opened."
        result.setdefault("diagnostics", {})["calendar_actions"] = safe_action_controls(driver)
        base.write_json(result_path, result)
        return 8

    time.sleep(0.7)
    if not base.click_text(driver, ["수정"], timeout=6):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Event detail opened, but the mobile-web edit action was not found."
        result.setdefault("diagnostics", {})["detail_actions"] = safe_action_controls(driver)
        base.write_json(result_path, result)
        return 9

    time.sleep(1.0)
    if not click_trash_on_edit(driver):
        # Last-resort textual route if current UI renders delete as text.
        if not base.click_text(driver, ["삭제", "일정 삭제"], timeout=3):
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Edit layer opened, but the trash/delete control was not found."
            result.setdefault("diagnostics", {})["edit_actions"] = safe_action_controls(driver)
            base.write_json(result_path, result)
            return 10

    time.sleep(0.7)
    base.click_text(driver, ["삭제", "확인", "예"], timeout=4)
    time.sleep(1.5)
    goto_calendar(driver, base)
    absent = not base.exact_text_present(driver, title)
    result["verification"]["evidence"]["cleanup_absence_observed"] = absent
    result["cleanup"]["completed"] = absent
    if not absent:
        result["failure_class"] = "VERIFY_FAILED"
        result["message"] = "Delete was attempted, but synthetic event absence could not be verified."
        base.write_json(result_path, result)
        return 11
    return 0


def recover_verify_delete(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    result = base.result_template(command)
    result_path = output_dir / "result.json"
    title = (command.get("arguments") or {}).get("title")
    if not isinstance(title, str) or not title:
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
    code = delete_existing(driver, base, title, result, result_path)
    if code:
        return code
    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = "Residual synthetic event was observed, opened, deleted through edit/trash flow, and absence-verified."
    base.write_json(result_path, result)
    return 0


def create_verify_delete(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    result = base.result_template(command)
    result_path = output_dir / "result.json"
    diagnostics_path = output_dir / "form-structure.json"
    title = (command.get("arguments") or {}).get("title")
    if not isinstance(title, str) or not title:
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Missing string arguments.title"
        base.write_json(result_path, result)
        return 2
    result["execution"]["attempted"] = True
    if not ensure_auth(driver, base, auth_timeout, result, result_path):
        return 3
    if not base.open_schedule_write_ui(driver, diagnostics_path):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Could not enter schedule-writing UI."
        base.write_json(result_path, result)
        return 4
    time.sleep(0.5)
    title_input = find_real_title_input(driver, base)
    if title_input is None:
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Could not identify observed schedule-title textarea."
        base.write_json(result_path, result)
        return 5
    result["diagnostics"] = {"selected_title_candidate": safe_desc(title_input)}
    title_input.click()
    title_input.send_keys(Keys.CONTROL, "a")
    title_input.send_keys(title)
    if not base.click_text(driver, ["저장"], timeout=12):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Could not locate save action."
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
    code = delete_existing(driver, base, title, result, result_path)
    if code:
        return code
    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = "Nonce-bearing event was created, observed, deleted through edit/trash flow, and absence-verified."
    base.write_json(result_path, result)
    return 0


def diagnose_schedule_form(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    result = base.result_template(command)
    result_path = output_dir / "result.json"
    result["cleanup"] = {"requested": False, "attempted": False, "completed": True}
    result["execution"]["attempted"] = True
    if not ensure_auth(driver, base, auth_timeout, result, result_path):
        return 3
    diagnostics_path = output_dir / "form-structure.json"
    if not base.open_schedule_write_ui(driver, diagnostics_path):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Could not enter schedule-writing UI for diagnostics."
        base.write_json(result_path, result)
        return 4
    time.sleep(0.7)
    result["diagnostics"] = {
        "page_url_without_query": (driver.current_url or "").split("?", 1)[0],
        "form_structure": base.form_metadata(driver),
        "selected_title_candidate": safe_desc(find_real_title_input(driver, base)),
        "action_controls": safe_action_controls(driver),
    }
    result["execution"]["completed"] = True
    result["verification"]["performed"] = True
    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = "Non-mutating schedule-form diagnostics captured."
    base.write_json(result_path, result)
    return 0


def execute(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    try:
        action = command.get("action")
        if action == "recover_verify_delete_event":
            return recover_verify_delete(driver, base, command, output_dir, auth_timeout)
        if action == "create_verify_delete_event":
            return create_verify_delete(driver, base, command, output_dir, auth_timeout)
        if action == "diagnose_schedule_form":
            return diagnose_schedule_form(driver, base, command, output_dir, auth_timeout)
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
        return 12


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
