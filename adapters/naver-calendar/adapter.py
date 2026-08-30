#!/usr/bin/env python3
"""EXP-002 Naver Calendar browser adapter.

Uses only browser UI automation. It never asks for or prints credentials,
session-cookie values, OAuth tokens, or Naver Calendar API material.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Iterable

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

TARGET_URL = "https://m.calendar.naver.com/"


def log(message: str) -> None:
    print(message, flush=True)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def result_template(command: dict) -> dict:
    return {
        "protocol_version": "0.1",
        "command_id": command.get("command_id"),
        "adapter_id": "naver-calendar",
        "action": command.get("action"),
        "status": "FAILED",
        "failure_class": None,
        "execution": {"attempted": False, "completed": False},
        "verification": {
            "performed": False,
            "passed": False,
            "evidence": {
                "created_title_observed": False,
                "cleanup_absence_observed": False,
            },
        },
        "cleanup": {"requested": True, "attempted": False, "completed": False},
    }


def visible(elements: Iterable):
    return [el for el in elements if el.is_displayed()]


def click_text(driver, candidates: list[str], timeout: float = 12.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        for text in candidates:
            xpaths = [
                f"//*[self::button or self::a or @role='button'][normalize-space(.)={json.dumps(text, ensure_ascii=False)}]",
                f"//*[self::button or self::a or @role='button'][contains(normalize-space(.), {json.dumps(text, ensure_ascii=False)})]",
                f"//*[normalize-space(.)={json.dumps(text, ensure_ascii=False)}]",
            ]
            for xpath in xpaths:
                try:
                    for el in visible(driver.find_elements(By.XPATH, xpath)):
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                            driver.execute_script("arguments[0].click();", el)
                            return True
                        except WebDriverException:
                            continue
                except WebDriverException:
                    continue
        time.sleep(0.35)
    return False


def exact_text_present(driver, text: str) -> bool:
    try:
        return bool(visible(driver.find_elements(By.XPATH, f"//*[normalize-space(.)={json.dumps(text, ensure_ascii=False)}]")))
    except WebDriverException:
        return text in driver.page_source


def wait_for_exact_text(driver, text: str, timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if exact_text_present(driver, text):
            return True
        time.sleep(0.5)
    return False


def authenticated(driver) -> bool:
    """Use cookie names only; never log or persist cookie values."""
    try:
        names = {c.get("name", "") for c in driver.get_cookies()}
        if {"NID_AUT", "NID_SES"}.issubset(names):
            return True
    except WebDriverException:
        pass

    try:
        text = driver.find_element(By.TAG_NAME, "body").text
        if "로그인이 필요합니다" not in text and "로그인" not in text and "내 캘린더" in text:
            return True
    except WebDriverException:
        pass
    return False


def wait_for_auth(driver, timeout_seconds: int) -> bool:
    if authenticated(driver):
        return True
    log("AUTH_REQUIRED: authenticate directly in the interactive browser; credentials stay outside Chat and logs.")
    end = time.time() + timeout_seconds
    while time.time() < end:
        if authenticated(driver):
            log("AUTHENTICATED: target session detected without exposing credential/session values.")
            return True
        time.sleep(2)
    return False


def form_metadata(driver) -> list[dict]:
    """Safe structural diagnostics: never include field values or page/private text."""
    data: list[dict] = []
    for el in driver.find_elements(By.CSS_SELECTOR, "input,textarea,button,[role='button']"):
        try:
            if not el.is_displayed():
                continue
            typ = (el.get_attribute("type") or "").lower()
            if typ == "password":
                continue
            data.append(
                {
                    "tag": el.tag_name,
                    "type": typ,
                    "name": el.get_attribute("name"),
                    "placeholder": el.get_attribute("placeholder"),
                    "aria_label": el.get_attribute("aria-label"),
                }
            )
        except WebDriverException:
            continue
    return data[:80]


def find_title_input(driver):
    inputs = visible(driver.find_elements(By.CSS_SELECTOR, "input:not([type='hidden']):not([type='password']), textarea"))
    preferred = []
    fallback = []
    for el in inputs:
        try:
            blob = " ".join(
                filter(
                    None,
                    [
                        el.get_attribute("placeholder"),
                        el.get_attribute("aria-label"),
                        el.get_attribute("name"),
                    ],
                )
            ).lower()
            typ = (el.get_attribute("type") or "text").lower()
            if any(token in blob for token in ["제목", "일정", "title", "subject"]):
                preferred.append(el)
            elif typ in {"text", "", "search"} and "검색" not in blob and "search" not in blob:
                fallback.append(el)
        except WebDriverException:
            continue
    return (preferred or fallback or inputs)[0] if (preferred or fallback or inputs) else None


def open_more_menu(driver) -> bool:
    if click_text(driver, ["더보기", "메뉴"], timeout=3):
        return True
    selectors = [
        "button[aria-label*='더보기']",
        "button[title*='더보기']",
        "[role='button'][aria-label*='더보기']",
        "button[aria-label*='More']",
        "button[title*='More']",
    ]
    for selector in selectors:
        try:
            for el in visible(driver.find_elements(By.CSS_SELECTOR, selector)):
                driver.execute_script("arguments[0].click();", el)
                return True
        except WebDriverException:
            continue
    return False


def run(command_path: Path, output_dir: Path, auth_timeout: int) -> int:
    command = json.loads(command_path.read_text(encoding="utf-8"))
    result = result_template(command)
    result_path = output_dir / "result.json"
    diagnostics_path = output_dir / "form-structure.json"

    args = command.get("arguments") or {}
    title = args.get("title")
    if not title or not isinstance(title, str):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Missing string arguments.title"
        write_json(result_path, result)
        return 2

    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--lang=ko-KR")
    options.add_argument("--user-data-dir=/tmp/cb-exp002-chrome")
    options.binary_location = os.environ.get("CHROME_BIN", "/usr/bin/google-chrome")

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)
        driver.get(TARGET_URL)
        result["execution"]["attempted"] = True

        if not wait_for_auth(driver, auth_timeout):
            result["failure_class"] = "AUTH_BOUNDARY"
            result["message"] = "Authentication was not completed before the handoff timeout."
            write_json(result_path, result)
            return 3

        driver.get(TARGET_URL)
        WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")

        if not click_text(driver, ["일정 추가"], timeout=12):
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Could not locate the schedule-add UI."
            write_json(result_path, result)
            return 4

        time.sleep(1.5)
        write_json(diagnostics_path, {"controls": form_metadata(driver)})

        title_input = find_title_input(driver)
        if title_input is None:
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Could not identify a visible event-title input."
            write_json(result_path, result)
            return 5

        title_input.click()
        title_input.send_keys(Keys.CONTROL, "a")
        title_input.send_keys(title)

        if not click_text(driver, ["저장", "완료", "등록"], timeout=12):
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Could not locate the save action."
            write_json(result_path, result)
            return 6

        result["execution"]["completed"] = True
        time.sleep(2)
        result["verification"]["performed"] = True

        created = wait_for_exact_text(driver, title, timeout=15)
        result["verification"]["evidence"]["created_title_observed"] = created
        if not created:
            result["failure_class"] = "VERIFY_FAILED"
            result["message"] = "Save was attempted but the nonce-bearing event title was not observed."
            write_json(result_path, result)
            return 7

        # Cleanup through the same browser UI.
        result["cleanup"]["attempted"] = True
        if not click_text(driver, [title], timeout=8):
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Created event was observed but could not be opened for cleanup."
            write_json(result_path, result)
            return 8

        time.sleep(1)
        if not click_text(driver, ["삭제"], timeout=4):
            open_more_menu(driver)
            if not click_text(driver, ["삭제", "일정 삭제"], timeout=7):
                result["failure_class"] = "ADAPTER_ERROR"
                result["message"] = "Created event could not be deleted through the visible UI."
                write_json(result_path, result)
                return 9

        # Confirm deletion if the target asks for confirmation.
        time.sleep(0.7)
        click_text(driver, ["삭제", "확인", "예"], timeout=3)
        time.sleep(2)

        # Return to the main calendar if the target leaves us in a detail route.
        if title in driver.page_source:
            try:
                driver.back()
                time.sleep(1.5)
            except WebDriverException:
                pass

        cleanup_absent = not exact_text_present(driver, title)
        result["verification"]["evidence"]["cleanup_absence_observed"] = cleanup_absent
        result["cleanup"]["completed"] = cleanup_absent

        if not cleanup_absent:
            result["failure_class"] = "VERIFY_FAILED"
            result["message"] = "Event creation was verified, but cleanup absence could not be verified."
            write_json(result_path, result)
            return 10

        result["verification"]["passed"] = True
        result["status"] = "VERIFIED_SUCCESS"
        result["failure_class"] = None
        result["message"] = "Nonce-bearing event was created, observed, deleted, and absence-verified through the browser UI."
        write_json(result_path, result)
        log("VERIFIED_SUCCESS: create -> observe -> delete -> absence verified.")
        return 0

    except Exception as exc:  # keep result machine-readable even on unexpected target/runtime failures
        result["failure_class"] = result.get("failure_class") or "ADAPTER_ERROR"
        result["message"] = f"Unexpected adapter failure: {type(exc).__name__}: {exc}"
        # Store traceback locally for Actions diagnostics; it should contain no credentials by design.
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        write_json(result_path, result)
        return 11
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--output-dir", default="artifacts/exp002")
    parser.add_argument("--auth-timeout", type=int, default=1200)
    args = parser.parse_args()
    return run(Path(args.command), Path(args.output_dir), args.auth_timeout)


if __name__ == "__main__":
    sys.exit(main())
