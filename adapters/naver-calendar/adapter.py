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


def control_metadata_current_context(driver) -> list[dict]:
    """Safe structural diagnostics: no field values and no arbitrary page/private text."""
    data: list[dict] = []
    selector = "input,textarea,button,[role='button'],[contenteditable='true']"
    for el in driver.find_elements(By.CSS_SELECTOR, selector):
        try:
            if not el.is_displayed():
                continue
            typ = (el.get_attribute("type") or "").lower()
            if typ == "password":
                continue
            text = (el.text or "").strip()
            if len(text) > 40:
                text = text[:40] + "…"
            data.append(
                {
                    "tag": el.tag_name,
                    "type": typ,
                    "name": el.get_attribute("name"),
                    "placeholder": el.get_attribute("placeholder"),
                    "aria_label": el.get_attribute("aria-label"),
                    "contenteditable": el.get_attribute("contenteditable"),
                    "ui_text": text or None,
                }
            )
        except WebDriverException:
            continue
    return data[:80]


def form_metadata(driver) -> dict:
    """Describe form structure in default content and one iframe level without values."""
    payload: dict = {"default_controls": [], "frames": []}
    try:
        driver.switch_to.default_content()
        payload["default_controls"] = control_metadata_current_context(driver)
        frames = driver.find_elements(By.CSS_SELECTOR, "iframe,frame")
        for index, frame in enumerate(frames[:10]):
            entry = {"index": index, "controls": []}
            try:
                driver.switch_to.frame(frame)
                entry["controls"] = control_metadata_current_context(driver)
            except WebDriverException:
                entry["unavailable"] = True
            finally:
                driver.switch_to.default_content()
            payload["frames"].append(entry)
    except WebDriverException:
        pass
    return payload


def candidate_inputs_current_context(driver):
    selector = "input:not([type='hidden']):not([type='password']),textarea,[contenteditable='true']"
    return visible(driver.find_elements(By.CSS_SELECTOR, selector))


def rank_title_inputs(elements):
    preferred = []
    fallback = []
    for el in elements:
        try:
            blob = " ".join(
                filter(
                    None,
                    [
                        el.get_attribute("placeholder"),
                        el.get_attribute("aria-label"),
                        el.get_attribute("name"),
                        el.get_attribute("id"),
                        el.get_attribute("class"),
                    ],
                )
            ).lower()
            typ = (el.get_attribute("type") or "text").lower()
            editable = (el.get_attribute("contenteditable") or "").lower() == "true"
            if any(token in blob for token in ["제목", "일정 제목", "title", "subject", "summary"]):
                preferred.append(el)
            elif (typ in {"text", "", "search"} or editable) and not any(
                token in blob for token in ["검색", "search", "장소", "location", "메모", "memo"]
            ):
                fallback.append(el)
        except WebDriverException:
            continue
    return preferred or fallback or elements


def find_title_input(driver):
    """Find the title control in default content or one iframe level.

    On success the driver remains in the context containing the returned element.
    """
    driver.switch_to.default_content()
    ranked = rank_title_inputs(candidate_inputs_current_context(driver))
    if ranked:
        return ranked[0]

    frames = driver.find_elements(By.CSS_SELECTOR, "iframe,frame")
    for frame in frames[:10]:
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            ranked = rank_title_inputs(candidate_inputs_current_context(driver))
            if ranked:
                return ranked[0]
        except WebDriverException:
            continue
    driver.switch_to.default_content()
    return None


def open_schedule_write_ui(driver, diagnostics_path: Path) -> bool:
    """Enter Naver Calendar's schedule-writing surface.

    Mobile Calendar uses a two-step launcher: '일정 추가' opens a chooser and the
    chooser's '일정' button opens the actual schedule-writing form. Some layouts
    may open the form directly, so the second click is conditional.
    """
    driver.switch_to.default_content()
    if not click_text(driver, ["일정 추가"], timeout=12):
        return False

    time.sleep(0.7)

    # If a form is already visible, the current layout skipped the chooser.
    if find_title_input(driver) is not None:
        return True

    driver.switch_to.default_content()
    if not click_text(driver, ["일정"], timeout=6):
        write_json(diagnostics_path, form_metadata(driver))
        return False

    time.sleep(1.2)
    return True


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

        if not open_schedule_write_ui(driver, diagnostics_path):
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Could not enter the schedule-writing UI after opening the schedule launcher."
            write_json(result_path, result)
            return 4

        time.sleep(0.5)
        write_json(diagnostics_path, form_metadata(driver))

        title_input = find_title_input(driver)
        if title_input is None:
            result["failure_class"] = "ADAPTER_ERROR"
            result["message"] = "Could not identify a visible event-title input after entering schedule-writing UI."
            write_json(result_path, result)
            return 5

        title_input.click()
        title_input.send_keys(Keys.CONTROL, "a")
        title_input.send_keys(title)

        if not click_text(driver, ["저장", "완료", "등록"], timeout=12):
            # The form could live inside an iframe while the save button lives outside it.
            driver.switch_to.default_content()
            if not click_text(driver, ["저장", "완료", "등록"], timeout=6):
                result["failure_class"] = "ADAPTER_ERROR"
                result["message"] = "Could not locate the save action."
                write_json(result_path, result)
                return 6

        driver.switch_to.default_content()
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

        time.sleep(0.7)
        click_text(driver, ["삭제", "확인", "예"], timeout=3)
        time.sleep(2)

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

    except Exception as exc:
        result["failure_class"] = result.get("failure_class") or "ADAPTER_ERROR"
        result["message"] = f"Unexpected adapter failure: {type(exc).__name__}: {exc}"
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
