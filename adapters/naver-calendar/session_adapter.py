#!/usr/bin/env python3
"""Persistent Naver Calendar adapter for an already-authenticated Chrome session.

This adapter intentionally keeps Chrome alive. It supports non-mutating DOM
structure diagnosis and cleanup of the single synthetic EXP-002 event.
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
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
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


def ensure_auth(driver, base, timeout: int, result: dict, result_path: Path) -> bool:
    goto_calendar(driver, base)
    if base.wait_for_auth(driver, timeout):
        return True
    result["failure_class"] = "AUTH_BOUNDARY"
    result["message"] = "Authenticated persistent session was not detected."
    base.write_json(result_path, result)
    return False


def find_title_nodes(driver, title: str):
    xpath = f"//*[normalize-space(.)={json.dumps(title, ensure_ascii=False)}]"
    return visible(driver.find_elements(By.XPATH, xpath))


def safe_attrs(driver, element) -> dict:
    """Return structural attributes only; no arbitrary page text or field values."""
    try:
        attrs = driver.execute_script(
            """
            const el = arguments[0];
            const out = {};
            for (const a of el.attributes || []) {
              const n = a.name.toLowerCase();
              if (n === 'style' || n === 'value') continue;
              if (n.startsWith('aria-') || n.startsWith('data-') ||
                  ['id','class','role','href','title','tabindex','type'].includes(n)) {
                out[a.name] = a.value;
              }
            }
            return out;
            """,
            element,
        ) or {}
        return {"tag": element.tag_name, "attrs": attrs}
    except WebDriverException:
        return {"unavailable": True}


def title_ancestor_chain(driver, title: str, max_depth: int = 10) -> list[dict]:
    nodes = find_title_nodes(driver, title)
    if not nodes:
        return []
    chain = []
    cur = nodes[0]
    for depth in range(max_depth):
        desc = safe_attrs(driver, cur)
        desc["depth"] = depth
        chain.append(desc)
        try:
            cur = cur.find_element(By.XPATH, "..")
        except WebDriverException:
            break
    return chain


def diagnose_event_card(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    result = base.result_template(command)
    result_path = output_dir / "result.json"
    title = (command.get("arguments") or {}).get("title")
    result["cleanup"] = {"requested": False, "attempted": False, "completed": True}
    if not isinstance(title, str) or not title:
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Missing string arguments.title"
        base.write_json(result_path, result)
        return 2
    result["execution"]["attempted"] = True
    if not ensure_auth(driver, base, auth_timeout, result, result_path):
        return 3
    found = base.wait_for_exact_text(driver, title, timeout=12)
    result["verification"]["performed"] = True
    result["verification"]["evidence"]["created_title_observed"] = found
    if not found:
        result["failure_class"] = "VERIFY_FAILED"
        result["message"] = "Synthetic event title is no longer observable."
        base.write_json(result_path, result)
        return 7
    result["diagnostics"] = {
        "page_url_without_query": (driver.current_url or "").split("?", 1)[0],
        "title_ancestor_chain": title_ancestor_chain(driver, title),
    }
    result["execution"]["completed"] = True
    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = "Synthetic event card structure captured without private calendar text."
    base.write_json(result_path, result)
    return 0


def detail_or_edit_visible(driver) -> bool:
    try:
        for label in ["수정", "저장", "삭제"]:
            xpath = f"//*[self::button or self::a or @role='button'][contains(normalize-space(.), {json.dumps(label, ensure_ascii=False)})]"
            if visible(driver.find_elements(By.XPATH, xpath)):
                return True
    except WebDriverException:
        pass
    path = urlparse(driver.current_url or "").path
    return path not in {"/", "/daily"} and "/add" not in path


def click_candidate(driver, el) -> bool:
    attempts = [
        lambda: ActionChains(driver).move_to_element(el).click().perform(),
        lambda: el.click(),
        lambda: driver.execute_script("arguments[0].click();", el),
        lambda: driver.execute_script(
            """
            const e=arguments[0];
            const r=e.getBoundingClientRect();
            const x=r.left+r.width/2, y=r.top+r.height/2;
            const t=document.elementFromPoint(x,y) || e;
            for (const type of ['pointerdown','mousedown','pointerup','mouseup','click']) {
              t.dispatchEvent(new MouseEvent(type,{bubbles:true,cancelable:true,clientX:x,clientY:y,view:window}));
            }
            """,
            el,
        ),
    ]
    for fn in attempts:
        try:
            fn()
            time.sleep(0.8)
            if detail_or_edit_visible(driver):
                return True
        except Exception:
            continue
    return False


def open_event_card(driver, base, title: str) -> bool:
    goto_calendar(driver, base)
    if not base.wait_for_exact_text(driver, title, timeout=12):
        return False
    nodes = find_title_nodes(driver, title)
    for node in nodes:
        chain = []
        cur = node
        for _ in range(10):
            chain.append(cur)
            try:
                cur = cur.find_element(By.XPATH, "..")
            except WebDriverException:
                break
        # Prefer structural candidates carrying event-ish attributes/classes.
        scored = []
        for depth, el in enumerate(chain):
            try:
                attrs = safe_attrs(driver, el).get("attrs", {})
                blob = " ".join(str(v) for v in attrs.values()).lower()
                score = 0
                if attrs.get("href"): score += 100
                if attrs.get("role") in {"button", "link"}: score += 80
                if attrs.get("tabindex") is not None: score += 25
                if any(k in blob for k in ["schedule", "event", "item", "card", "plan", "todo"]): score += 50
                score += depth
                scored.append((score, el, attrs))
            except Exception:
                continue
        for _, el, attrs in sorted(scored, key=lambda x: x[0], reverse=True):
            href = attrs.get("href")
            if href:
                try:
                    parsed = urlparse(href)
                    if parsed.netloc in {"", "m.calendar.naver.com", "calendar.naver.com"}:
                        driver.get(href)
                        time.sleep(1.0)
                        if detail_or_edit_visible(driver):
                            return True
                        goto_calendar(driver, base, settle=0.8)
                except Exception:
                    pass
            if click_candidate(driver, el):
                return True
    return False


def click_text(driver, texts: list[str], timeout: float = 5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        for text in texts:
            xpath = f"//*[self::button or self::a or @role='button'][contains(normalize-space(.), {json.dumps(text, ensure_ascii=False)})]"
            for el in visible(driver.find_elements(By.XPATH, xpath)):
                try:
                    driver.execute_script("arguments[0].click();", el)
                    return True
                except Exception:
                    pass
        time.sleep(0.25)
    return False


def click_delete_control(driver) -> bool:
    selectors = [
        "button[aria-label*='삭제']", "button[title*='삭제']",
        "[role='button'][aria-label*='삭제']", "[role='button'][title*='삭제']",
        "button[class*='delete']", "button[class*='trash']",
        "a[class*='delete']", "a[class*='trash']",
    ]
    for sel in selectors:
        try:
            for el in visible(driver.find_elements(By.CSS_SELECTOR, sel)):
                driver.execute_script("arguments[0].click();", el)
                return True
        except Exception:
            pass
    return click_text(driver, ["삭제", "일정 삭제"], timeout=3)


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

    result["cleanup"]["attempted"] = True
    if not open_event_card(driver, base, title):
        result["failure_class"] = "ADAPTER_ERROR"
        result["diagnostics"] = {"title_ancestor_chain": title_ancestor_chain(driver, title)}
        result["message"] = "Synthetic event was visible but its event card could not be activated."
        base.write_json(result_path, result)
        return 8

    # Official mobile flow is event detail -> edit -> trash/delete.
    click_text(driver, ["수정"], timeout=5)
    time.sleep(0.8)
    if not click_delete_control(driver):
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = "Event card opened, but delete/trash control was not found."
        base.write_json(result_path, result)
        return 9
    time.sleep(0.5)
    click_text(driver, ["삭제", "확인", "예"], timeout=4)
    time.sleep(1.5)
    goto_calendar(driver, base)
    absent = not base.exact_text_present(driver, title)
    result["verification"]["evidence"]["cleanup_absence_observed"] = absent
    result["cleanup"]["completed"] = absent
    if not absent:
        result["failure_class"] = "VERIFY_FAILED"
        result["message"] = "Delete was attempted, but synthetic event absence could not be verified."
        base.write_json(result_path, result)
        return 10

    result["verification"]["passed"] = True
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = "Residual synthetic event was deleted and absence-verified; persistent browser retained."
    base.write_json(result_path, result)
    return 0


def execute(driver, base, command: dict, output_dir: Path, auth_timeout: int) -> int:
    try:
        action = command.get("action")
        if action == "diagnose_event_card":
            return diagnose_event_card(driver, base, command, output_dir, auth_timeout)
        if action == "recover_verify_delete_event":
            return recover_verify_delete(driver, base, command, output_dir, auth_timeout)
        result = base.result_template(command)
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = f"Unsupported cleanup-session action: {action}"
        base.write_json(output_dir / "result.json", result)
        return 2
    except Exception as exc:
        result = base.result_template(command)
        result["failure_class"] = "ADAPTER_ERROR"
        result["message"] = f"Unexpected cleanup adapter failure: {type(exc).__name__}: {exc}"
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
