#!/usr/bin/env python3
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
from selenium.webdriver.common.by import By


def load_base():
    path = Path(os.environ.get("CB_ADAPTER_LIB", Path(__file__).with_name("adapter.py")))
    spec = importlib.util.spec_from_file_location("cb_geeknews_base", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def succeed(base, result_path: Path, result: dict, message: str, evidence: dict | None = None) -> int:
    result["status"] = "VERIFIED_SUCCESS"
    result["failure_class"] = None
    result["message"] = message
    result["execution"]["completed"] = True
    result["verification"]["performed"] = True
    result["verification"]["passed"] = True
    if evidence:
        result["verification"]["evidence"].update(evidence)
    base.write_json(result_path, result)
    return 0


def fail(base, result_path: Path, result: dict, cls: str, message: str, code: int = 2, evidence: dict | None = None) -> int:
    result["failure_class"] = cls
    result["message"] = message
    if evidence:
        result["verification"]["evidence"].update(evidence)
    base.write_json(result_path, result)
    return code


def require_approved(command: dict, body: str | None = None) -> tuple[bool, str]:
    if command.get("approved") is not True:
        return False, "Submit action requires approved=true from the user-approved command."
    expected = command.get("expected_text_sha256")
    if body is not None and expected and expected != __import__("hashlib").sha256(body.encode()).hexdigest():
        return False, "approved command text fingerprint does not match the current draft body."
    return True, ""


def inspect_page(driver, base, command, result_path, result):
    args = command.get("arguments") or {}
    url = args.get("url") or driver.current_url or base.HOME_URL
    if url != driver.current_url:
        base.navigate(driver, url)
    result["execution"]["attempted"] = True
    evidence = {
        "url": driver.current_url,
        "title": driver.title,
        "logged_in": base.is_logged_in(driver),
        "controls": base.control_summary(driver),
    }
    return succeed(base, result_path, result, "Page controls inspected without submitting anything.", evidence)


def auth_status(driver, base, command, result_path, result):
    result["execution"]["attempted"] = True
    if "/login" in (driver.current_url or ""):
        logged = base.is_logged_in(driver)
    else:
        base.navigate(driver, base.HOME_URL)
        logged = base.is_logged_in(driver)
    if logged:
        return succeed(base, result_path, result, "GeekNews authenticated browser session is active.", {"logged_in": True, "url": driver.current_url})
    return fail(base, result_path, result, "AUTH_BOUNDARY", "GeekNews login is not active in the retained browser session.", 3, {"logged_in": False, "url": driver.current_url})


def draft_comment(driver, base, command, result_path, result):
    args = command.get("arguments") or {}
    topic_url = args.get("topic_url")
    body = (args.get("body") or "").strip()
    if not topic_url or not body:
        return fail(base, result_path, result, "INVALID_COMMAND", "draft_comment requires topic_url and non-empty body.")
    base.navigate(driver, topic_url)
    ok, why = base.require_auth(driver)
    if not ok:
        return fail(base, result_path, result, "AUTH_BOUNDARY", why, 3)
    textarea = base.largest_textarea(driver)
    if textarea is None:
        return fail(base, result_path, result, "ADAPTER_ERROR", "No visible comment textarea was found.", 8, {"controls": base.control_summary(driver)})
    base.set_value(textarea, body)
    result["execution"]["attempted"] = True
    return succeed(base, result_path, result, "Comment draft filled; nothing was submitted.", {
        "topic_url": driver.current_url,
        "draft_body": body,
        "draft_text_sha256": base.sha256_text(body),
        "submit_available": base.submit_control(base.form_for(textarea)) is not None,
    })


def submit_comment(driver, base, command, result_path, result):
    args = command.get("arguments") or {}
    body = (args.get("body") or "").strip()
    approved, why = require_approved(command, body)
    if not approved:
        return fail(base, result_path, result, "APPROVAL_REQUIRED", why, 4)
    ok, auth_why = base.require_auth(driver)
    if not ok:
        return fail(base, result_path, result, "AUTH_BOUNDARY", auth_why, 3)
    textareas = [t for t in base.visible_textareas(driver) if (t.get_attribute("value") or "").strip() == body]
    if not textareas:
        return fail(base, result_path, result, "STALE_DRAFT", "Approved comment text is not present in a visible draft textarea.", 9)
    textarea = textareas[0]
    submit = base.submit_control(base.form_for(textarea))
    if submit is None:
        return fail(base, result_path, result, "ADAPTER_ERROR", "No submit control was found for the approved comment draft.", 8)
    waited = base.respect_cooldown("comment")
    result["execution"]["attempted"] = True
    try:
        submit.click()
    except Exception:
        driver.execute_script("arguments[0].click();", submit)
    time.sleep(1.2)
    base.ready(driver)
    present = base.exact_text_present(driver, body)
    if not present:
        return fail(base, result_path, result, "VERIFY_FAILED", "Comment submit was attempted but exact comment text was not observed afterward.", 10, {"cooldown_waited_seconds": waited, "url": driver.current_url})
    base.record_activity("comment")
    return succeed(base, result_path, result, "Approved comment submitted and exact text observed.", {"cooldown_waited_seconds": waited, "url": driver.current_url, "exact_text_observed": True})


def draft_reply(driver, base, command, result_path, result):
    args = command.get("arguments") or {}
    topic_url = args.get("topic_url")
    body = (args.get("body") or "").strip()
    author = args.get("target_author")
    snippet = args.get("target_comment_snippet")
    if not topic_url or not body or not (author or snippet):
        return fail(base, result_path, result, "INVALID_COMMAND", "draft_reply requires topic_url, body, and target_author or target_comment_snippet.")
    base.navigate(driver, topic_url)
    ok, why = base.require_auth(driver)
    if not ok:
        return fail(base, result_path, result, "AUTH_BOUNDARY", why, 3)
    trigger = base.find_reply_trigger(driver, author, snippet)
    if trigger is None:
        return fail(base, result_path, result, "ADAPTER_ERROR", "Target reply trigger was not found.", 8, {"controls": base.control_summary(driver)})
    try:
        trigger.click()
    except Exception:
        driver.execute_script("arguments[0].click();", trigger)
    time.sleep(0.6)
    textarea = base.largest_textarea(driver)
    if textarea is None:
        return fail(base, result_path, result, "ADAPTER_ERROR", "Reply trigger was activated but no visible textarea was found.", 8, {"url": driver.current_url, "controls": base.control_summary(driver)})
    base.set_value(textarea, body)
    result["execution"]["attempted"] = True
    return succeed(base, result_path, result, "Reply draft filled; nothing was submitted.", {
        "topic_url": driver.current_url,
        "target_author": author,
        "target_comment_snippet": snippet,
        "draft_body": body,
        "draft_text_sha256": base.sha256_text(body),
        "submit_available": base.submit_control(base.form_for(textarea)) is not None,
    })


def submit_reply(driver, base, command, result_path, result):
    args = command.get("arguments") or {}
    body = (args.get("body") or "").strip()
    approved, why = require_approved(command, body)
    if not approved:
        return fail(base, result_path, result, "APPROVAL_REQUIRED", why, 4)
    ok, auth_why = base.require_auth(driver)
    if not ok:
        return fail(base, result_path, result, "AUTH_BOUNDARY", auth_why, 3)
    textareas = [t for t in base.visible_textareas(driver) if (t.get_attribute("value") or "").strip() == body]
    if not textareas:
        return fail(base, result_path, result, "STALE_DRAFT", "Approved reply text is not present in a visible draft textarea.", 9)
    textarea = textareas[0]
    submit = base.submit_control(base.form_for(textarea))
    if submit is None:
        return fail(base, result_path, result, "ADAPTER_ERROR", "No submit control was found for the approved reply draft.", 8)
    waited = base.respect_cooldown("reply")
    result["execution"]["attempted"] = True
    try:
        submit.click()
    except Exception:
        driver.execute_script("arguments[0].click();", submit)
    time.sleep(1.2)
    base.ready(driver)
    if not base.exact_text_present(driver, body):
        return fail(base, result_path, result, "VERIFY_FAILED", "Reply submit was attempted but exact reply text was not observed afterward.", 10, {"cooldown_waited_seconds": waited, "url": driver.current_url})
    base.record_activity("reply")
    return succeed(base, result_path, result, "Approved reply submitted and exact text observed.", {"cooldown_waited_seconds": waited, "url": driver.current_url, "exact_text_observed": True})


def fill_post_fields(driver, base, args: dict):
    fields = base.visible(driver.find_elements(By.CSS_SELECTOR, "input,textarea"))
    assigned = {}
    values = {
        "title": (args.get("title") or "").strip(),
        "url": (args.get("url") or "").strip(),
        "body": (args.get("body") or "").strip(),
    }
    for field in fields:
        meta = " ".join(filter(None, [field.get_attribute("name"), field.get_attribute("id"), field.get_attribute("placeholder")])).lower()
        tag = field.tag_name.lower()
        key = None
        if "title" in meta or "제목" in meta:
            key = "title"
        elif "url" in meta or "link" in meta or "링크" in meta:
            key = "url"
        elif tag == "textarea" or "text" in meta or "body" in meta or "내용" in meta or "desc" in meta:
            key = "body"
        if key and values[key] and key not in assigned:
            base.set_value(field, values[key])
            assigned[key] = field
    return assigned


def draft_post(driver, base, command, result_path, result):
    args = command.get("arguments") or {}
    if not (args.get("title") or "").strip():
        return fail(base, result_path, result, "INVALID_COMMAND", "draft_post requires a title.")
    base.navigate(driver, base.SUBMIT_URL)
    ok, why = base.require_auth(driver)
    if not ok:
        return fail(base, result_path, result, "AUTH_BOUNDARY", why, 3)
    assigned = fill_post_fields(driver, base, args)
    if "title" not in assigned:
        return fail(base, result_path, result, "ADAPTER_ERROR", "Post title field could not be identified.", 8, {"controls": base.control_summary(driver)})
    title = (args.get("title") or "").strip()
    composite = json.dumps({k: (args.get(k) or "").strip() for k in ("title", "url", "body")}, ensure_ascii=False, sort_keys=True)
    result["execution"]["attempted"] = True
    return succeed(base, result_path, result, "Post draft filled; nothing was submitted.", {
        "draft_fields": sorted(assigned.keys()),
        "draft_title": title,
        "draft_text_sha256": base.sha256_text(composite),
        "controls": base.control_summary(driver, limit=40),
    })


def submit_post(driver, base, command, result_path, result):
    args = command.get("arguments") or {}
    composite = json.dumps({k: (args.get(k) or "").strip() for k in ("title", "url", "body")}, ensure_ascii=False, sort_keys=True)
    approved, why = require_approved(command, composite)
    if not approved:
        return fail(base, result_path, result, "APPROVAL_REQUIRED", why, 4)
    ok, auth_why = base.require_auth(driver)
    if not ok:
        return fail(base, result_path, result, "AUTH_BOUNDARY", auth_why, 3)
    title = (args.get("title") or "").strip()
    title_fields = []
    for field in base.visible(driver.find_elements(By.CSS_SELECTOR, "input,textarea")):
        if (field.get_attribute("value") or "").strip() == title:
            title_fields.append(field)
    if not title_fields:
        return fail(base, result_path, result, "STALE_DRAFT", "Approved post title is not present in the current draft form.", 9)
    form = base.form_for(title_fields[0])
    submit = base.submit_control(form)
    if submit is None:
        return fail(base, result_path, result, "ADAPTER_ERROR", "No submit control was found for the approved post draft.", 8)
    waited = base.respect_cooldown("post")
    result["execution"]["attempted"] = True
    try:
        submit.click()
    except Exception:
        driver.execute_script("arguments[0].click();", submit)
    time.sleep(1.5)
    base.ready(driver)
    if not base.exact_text_present(driver, title):
        return fail(base, result_path, result, "VERIFY_FAILED", "Post submit was attempted but exact title was not observed afterward.", 10, {"cooldown_waited_seconds": waited, "url": driver.current_url})
    base.record_activity("post")
    return succeed(base, result_path, result, "Approved post submitted and title observed.", {"cooldown_waited_seconds": waited, "url": driver.current_url, "title_observed": True})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--command", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--debugger-address", default="127.0.0.1:9222")
    ap.add_argument("--auth-timeout", type=int, default=60)
    args = ap.parse_args()

    base = load_base()
    command = json.loads(Path(args.command).read_text(encoding="utf-8"))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "result.json"
    result = base.result_template(command)

    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", args.debugger_address)
    driver = webdriver.Chrome(options=options)

    try:
        action = command.get("action")
        handlers = {
            "inspect_page": inspect_page,
            "auth_status": auth_status,
            "draft_comment": draft_comment,
            "submit_comment": submit_comment,
            "draft_reply": draft_reply,
            "submit_reply": submit_reply,
            "draft_post": draft_post,
            "submit_post": submit_post,
        }
        handler = handlers.get(action)
        if handler is None:
            return fail(base, result_path, result, "INVALID_COMMAND", f"Unsupported GeekNews action: {action}")
        return handler(driver, base, command, result_path, result)
    except Exception as exc:
        (out_dir / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return fail(base, result_path, result, "ADAPTER_ERROR", f"Unexpected GeekNews adapter failure: {type(exc).__name__}: {exc}", 12)


if __name__ == "__main__":
    sys.exit(main())
