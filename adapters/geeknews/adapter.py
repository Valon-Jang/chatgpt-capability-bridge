#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

HOME_URL = "https://news.hada.io/"
LOGIN_URL = "https://news.hada.io/login"
SUBMIT_URL = "https://news.hada.io/submit"
ACTIVITY_STATE = Path("/tmp/cb-geeknews-activity.json")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def result_template(command: dict) -> dict:
    return {
        "status": "FAILED",
        "failure_class": None,
        "message": "",
        "action": command.get("action"),
        "command_id": command.get("command_id"),
        "execution": {"attempted": False, "completed": False},
        "verification": {"performed": False, "passed": False, "evidence": {}},
    }


def visible(elements):
    out = []
    for element in elements:
        try:
            if element.is_displayed():
                out.append(element)
        except WebDriverException:
            pass
    return out


def ready(driver, timeout: int = 20) -> None:
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def navigate(driver, url: str) -> None:
    driver.switch_to.default_content()
    driver.get(url)
    ready(driver)
    time.sleep(0.5)


def is_logged_in(driver) -> bool:
    try:
        login_links = visible(driver.find_elements(By.CSS_SELECTOR, 'a[href="/login"],a[href$="/login"]'))
        logout_links = visible(driver.find_elements(By.CSS_SELECTOR, 'a[href*="logout"]'))
        if logout_links:
            return True
        if login_links:
            return False
        # On the login page, the password field is a reliable negative signal.
        if "/login" in (driver.current_url or ""):
            return False
        pw = visible(driver.find_elements(By.CSS_SELECTOR, 'input[type="password"]'))
        return not pw
    except WebDriverException:
        return False


def require_auth(driver) -> tuple[bool, str]:
    if is_logged_in(driver):
        return True, "already authenticated"
    current = driver.current_url or ""
    if "/login" not in current:
        navigate(driver, HOME_URL)
    if is_logged_in(driver):
        return True, "authenticated"
    return False, "GeekNews login is required in the retained browser session."


def control_summary(driver, limit: int = 80) -> list[dict]:
    selector = "input,textarea,button,select,a"
    rows = []
    for element in visible(driver.find_elements(By.CSS_SELECTOR, selector))[:limit]:
        try:
            rows.append(
                {
                    "tag": element.tag_name,
                    "type": element.get_attribute("type"),
                    "name": element.get_attribute("name"),
                    "id": element.get_attribute("id"),
                    "class": element.get_attribute("class"),
                    "placeholder": element.get_attribute("placeholder"),
                    "value": (element.get_attribute("value") or "")[:120],
                    "text": (element.text or "")[:160],
                    "href": (element.get_attribute("href") or "")[:240],
                }
            )
        except WebDriverException:
            pass
    return rows


def visible_textareas(driver):
    return visible(driver.find_elements(By.TAG_NAME, "textarea"))


def largest_textarea(driver):
    candidates = visible_textareas(driver)
    if not candidates:
        return None
    def score(el):
        try:
            size = el.size
            return int(size.get("width", 0)) * int(size.get("height", 0))
        except Exception:
            return 0
    return max(candidates, key=score)


def set_value(element, text: str) -> None:
    element.click()
    try:
        element.clear()
    except Exception:
        pass
    element.send_keys(text)


def form_for(element):
    try:
        return element.find_element(By.XPATH, "ancestor::form[1]")
    except Exception:
        return None


def submit_control(form):
    if form is None:
        return None
    candidates = visible(form.find_elements(By.CSS_SELECTOR, 'button,input[type="submit"]'))
    if not candidates:
        return None
    preferred = []
    for el in candidates:
        label = " ".join([(el.text or ""), (el.get_attribute("value") or "")]).strip().lower()
        if any(token in label for token in ("댓글", "등록", "답변", "작성", "저장", "submit", "post")):
            preferred.append(el)
    return preferred[0] if preferred else candidates[0]


def exact_text_present(driver, text: str) -> bool:
    if not text:
        return False
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        return text.strip() in body_text
    except Exception:
        return False


def find_reply_trigger(driver, author: str | None, snippet: str | None):
    # Prefer author anchors, then climb only to a local ancestor containing a reply trigger.
    roots = []
    if author:
        for anchor in visible(driver.find_elements(By.XPATH, f'//a[normalize-space()={json.dumps(author)}]')):
            try:
                root = anchor.find_element(By.XPATH, "ancestor::*[.//a[contains(normalize-space(.),'답변달기')] or .//button[contains(normalize-space(.),'답변달기')]][1]")
                roots.append(root)
            except Exception:
                pass
    if not roots and snippet:
        xpath_literal = json.dumps(snippet[:80])
        for node in visible(driver.find_elements(By.XPATH, f'//*[contains(normalize-space(.), {xpath_literal})]')):
            try:
                root = node.find_element(By.XPATH, "ancestor-or-self::*[.//a[contains(normalize-space(.),'답변달기')] or .//button[contains(normalize-space(.),'답변달기')]][1]")
                roots.append(root)
            except Exception:
                pass
    for root in roots:
        try:
            if snippet and snippet not in (root.text or ""):
                continue
            triggers = visible(root.find_elements(By.XPATH, ".//a[contains(normalize-space(.),'답변달기')] | .//button[contains(normalize-space(.),'답변달기')]"))
            if triggers:
                return triggers[0]
        except Exception:
            continue
    return None


def load_activity() -> dict:
    try:
        return json.loads(ACTIVITY_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def record_activity(kind: str) -> None:
    write_json(ACTIVITY_STATE, {"last_submit_epoch": time.time(), "last_kind": kind})


def respect_cooldown(kind: str) -> float:
    """Simple burst protection; this is not a bot-evasion mechanism."""
    state = load_activity()
    last = float(state.get("last_submit_epoch") or 0)
    if not last:
        return 0.0
    min_gap = 300.0 if kind == "post" else 30.0
    remaining = min_gap - (time.time() - last)
    if remaining > 0:
        time.sleep(remaining)
        return remaining
    return 0.0
