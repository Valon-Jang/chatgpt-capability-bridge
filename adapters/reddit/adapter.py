#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

HOME_URL = 'https://www.reddit.com/'
TARGET_SUB = 'https://www.reddit.com/r/LocalLLaMA/'
OLD_TARGET_SUB = 'https://old.reddit.com/r/LocalLLaMA/'
ACTIVITY_STATE = Path('/tmp/cb-reddit-activity.json')


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def result_template(command: dict) -> dict:
    return {
        'status': 'FAILED',
        'failure_class': None,
        'message': '',
        'action': command.get('action'),
        'command_id': command.get('command_id'),
        'execution': {'attempted': False, 'completed': False},
        'verification': {'performed': False, 'passed': False, 'evidence': {}},
    }


def visible(elements):
    out = []
    for e in elements:
        try:
            if e.is_displayed():
                out.append(e)
        except WebDriverException:
            pass
    return out


def ready(driver, timeout=20):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )


def navigate(driver, url):
    driver.switch_to.default_content()
    driver.get(url)
    ready(driver)
    time.sleep(0.8)


def is_logged_in(driver):
    try:
        cookies = {c.get('name', ''): c.get('value', '') for c in driver.get_cookies()}
        if cookies.get('reddit_session'):
            return True
        url = (driver.current_url or '').lower()
        if '/login' in url or '/register' in url:
            return False
        markers = driver.execute_script(
            "return Array.from(document.querySelectorAll('a,button')).slice(0,400).map(x=>((x.getAttribute('href')||'')+' '+(x.textContent||'')).toLowerCase());"
        )
        return any('/user/' in m or '/settings' in m or 'logout' in m or 'log out' in m for m in markers)
    except Exception:
        return False


def require_auth(driver):
    if is_logged_in(driver):
        return True, 'authenticated'
    navigate(driver, HOME_URL)
    if is_logged_in(driver):
        return True, 'authenticated'
    return False, 'Reddit login is required in the retained browser session.'


def control_summary(driver, limit=120):
    rows = []
    selector = "input,textarea,button,select,a,[contenteditable='true']"
    for e in visible(driver.find_elements(By.CSS_SELECTOR, selector))[:limit]:
        try:
            rows.append({
                'tag': e.tag_name,
                'type': e.get_attribute('type'),
                'name': e.get_attribute('name'),
                'id': e.get_attribute('id'),
                'class': (e.get_attribute('class') or '')[:180],
                'placeholder': e.get_attribute('placeholder'),
                'aria_label': e.get_attribute('aria-label'),
                'role': e.get_attribute('role'),
                'value': (e.get_attribute('value') or '')[:100],
                'text': (e.text or '')[:180],
                'href': (e.get_attribute('href') or '')[:240],
            })
        except WebDriverException:
            pass
    return rows


def to_old_reddit(url: str) -> str:
    if url.startswith('https://www.reddit.com/'):
        return 'https://old.reddit.com/' + url[len('https://www.reddit.com/'):]
    if url.startswith('http://www.reddit.com/'):
        return 'https://old.reddit.com/' + url[len('http://www.reddit.com/'):]
    return url


def set_value(driver, element, text: str) -> None:
    try:
        element.click()
        element.clear()
        element.send_keys(text)
        return
    except Exception:
        pass
    driver.execute_script(
        "arguments[0].value=arguments[1]; arguments[0].dispatchEvent(new Event('input',{bubbles:true})); arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
        element,
        text,
    )


def form_for(element):
    try:
        return element.find_element(By.XPATH, 'ancestor::form[1]')
    except Exception:
        return None


def submit_control(form):
    if form is None:
        return None
    candidates = visible(form.find_elements(By.CSS_SELECTOR, "button[type='submit'],input[type='submit']"))
    if not candidates:
        return None
    preferred = []
    for e in candidates:
        label = ' '.join([(e.text or ''), (e.get_attribute('value') or '')]).strip().lower()
        cls = (e.get_attribute('class') or '').lower()
        if 'save' in label or 'save' in cls or 'comment' in label or 'reply' in label:
            preferred.append(e)
    return preferred[0] if preferred else candidates[0]


def top_level_comment_textarea(driver):
    candidates = visible(driver.find_elements(By.CSS_SELECTOR, "form.usertext textarea[name='text'],textarea[name='text']"))
    if not candidates:
        return None
    # On a permalink page the top-level composer appears before inline reply composers.
    return candidates[0]


def exact_text_present(driver, text: str) -> bool:
    if not text:
        return False
    try:
        return text.strip() in driver.find_element(By.TAG_NAME, 'body').text
    except Exception:
        return False


def find_comment_thing(driver, author: str | None, snippet: str | None):
    things = visible(driver.find_elements(By.CSS_SELECTOR, '.thing.comment'))
    for thing in things:
        try:
            if author:
                a = thing.get_attribute('data-author') or ''
                if a.lower() != author.lower():
                    continue
            if snippet and snippet not in (thing.text or ''):
                continue
            return thing
        except Exception:
            continue
    return None


def open_reply_editor(driver, thing):
    if thing is None:
        return None
    triggers = visible(thing.find_elements(By.CSS_SELECTOR, '.reply-button a, a[data-event-action="comment"], a[data-event-action="reply"]'))
    if not triggers:
        triggers = visible(thing.find_elements(By.XPATH, ".//a[normalize-space()='reply']"))
    if not triggers:
        return None
    try:
        triggers[0].click()
    except Exception:
        driver.execute_script('arguments[0].click();', triggers[0])
    time.sleep(0.5)
    editors = visible(thing.find_elements(By.CSS_SELECTOR, "form.usertext textarea[name='text'], textarea[name='text']"))
    return editors[-1] if editors else None


def load_activity() -> dict:
    try:
        return json.loads(ACTIVITY_STATE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def record_activity(kind: str) -> None:
    write_json(ACTIVITY_STATE, {'last_submit_epoch': time.time(), 'last_kind': kind})


def respect_cooldown(kind: str) -> float:
    state = load_activity()
    last = float(state.get('last_submit_epoch') or 0)
    if not last:
        return 0.0
    min_gap = 30.0 if kind in ('comment', 'reply') else 300.0
    remaining = min_gap - (time.time() - last)
    if remaining > 0:
        time.sleep(remaining)
        return remaining
    return 0.0
