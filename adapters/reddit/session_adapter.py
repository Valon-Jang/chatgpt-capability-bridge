#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

from selenium import webdriver


def load_base():
    p = Path(os.environ.get('CB_ADAPTER_LIB', Path(__file__).with_name('adapter.py')))
    s = importlib.util.spec_from_file_location('cb_reddit_base', p)
    m = importlib.util.module_from_spec(s)
    assert s.loader is not None
    s.loader.exec_module(m)
    return m


def succeed(b, rp, r, msg, e=None):
    r['status'] = 'VERIFIED_SUCCESS'
    r['failure_class'] = None
    r['message'] = msg
    r['execution']['completed'] = True
    r['verification']['performed'] = True
    r['verification']['passed'] = True
    if e:
        r['verification']['evidence'].update(e)
    b.write_json(rp, r)
    return 0


def fail(b, rp, r, cls, msg, code=2, e=None):
    r['failure_class'] = cls
    r['message'] = msg
    if e:
        r['verification']['evidence'].update(e)
    b.write_json(rp, r)
    return code


def approved(command: dict, body: str):
    if command.get('approved') is not True:
        return False, 'Submit action requires approved=true.'
    expected = command.get('expected_text_sha256')
    actual = hashlib.sha256(body.encode('utf-8')).hexdigest()
    if not expected or expected != actual:
        return False, 'Approved text fingerprint does not match the current body.'
    return True, ''


def auth_status(d, b, c, rp, r):
    r['execution']['attempted'] = True
    b.navigate(d, b.HOME_URL)
    logged = b.is_logged_in(d)
    if logged:
        return succeed(b, rp, r, 'Reddit authenticated browser session is active.', {'logged_in': True, 'url': d.current_url})
    return fail(b, rp, r, 'AUTH_BOUNDARY', 'Reddit login is not active.', 3, {'logged_in': False, 'url': d.current_url})


def inspect_page(d, b, c, rp, r):
    url = (c.get('arguments') or {}).get('url') or b.TARGET_SUB
    b.navigate(d, url)
    r['execution']['attempted'] = True
    return succeed(b, rp, r, 'Reddit page controls inspected without submitting anything.', {
        'url': d.current_url,
        'title': d.title,
        'logged_in': b.is_logged_in(d),
        'controls': b.control_summary(d),
    })


def draft_comment(d, b, c, rp, r):
    a = c.get('arguments') or {}
    post_url = (a.get('post_url') or '').strip()
    body = (a.get('body') or '').strip()
    if not post_url or not body:
        return fail(b, rp, r, 'INVALID_COMMAND', 'draft_comment requires post_url and body.')
    b.navigate(d, b.to_old_reddit(post_url))
    ok, why = b.require_auth(d)
    if not ok:
        return fail(b, rp, r, 'AUTH_BOUNDARY', why, 3)
    textarea = b.top_level_comment_textarea(d)
    if textarea is None:
        return fail(b, rp, r, 'ADAPTER_ERROR', 'Top-level comment textarea was not found.', 8, {'controls': b.control_summary(d)})
    b.set_value(d, textarea, body)
    r['execution']['attempted'] = True
    return succeed(b, rp, r, 'Reddit comment draft filled; nothing was submitted.', {
        'post_url': d.current_url,
        'draft_body': body,
        'draft_text_sha256': b.sha256_text(body),
        'submit_available': b.submit_control(b.form_for(textarea)) is not None,
    })


def submit_comment(d, b, c, rp, r):
    a = c.get('arguments') or {}
    body = (a.get('body') or '').strip()
    ok, why = approved(c, body)
    if not ok:
        return fail(b, rp, r, 'APPROVAL_REQUIRED', why, 4)
    ok, auth_why = b.require_auth(d)
    if not ok:
        return fail(b, rp, r, 'AUTH_BOUNDARY', auth_why, 3)
    textarea = b.top_level_comment_textarea(d)
    if textarea is None or (textarea.get_attribute('value') or '').strip() != body:
        return fail(b, rp, r, 'STALE_DRAFT', 'Approved comment text is not present in the active draft.', 9)
    submit = b.submit_control(b.form_for(textarea))
    if submit is None:
        return fail(b, rp, r, 'ADAPTER_ERROR', 'Submit control for the comment draft was not found.', 8)
    waited = b.respect_cooldown('comment')
    r['execution']['attempted'] = True
    try:
        submit.click()
    except Exception:
        d.execute_script('arguments[0].click();', submit)
    time.sleep(1.2)
    b.ready(d)
    if not b.exact_text_present(d, body):
        return fail(b, rp, r, 'VERIFY_FAILED', 'Comment submission was attempted but exact text was not observed afterward.', 10, {'url': d.current_url, 'cooldown_waited_seconds': waited})
    b.record_activity('comment')
    return succeed(b, rp, r, 'Approved Reddit comment submitted and exact text observed.', {'url': d.current_url, 'cooldown_waited_seconds': waited, 'exact_text_observed': True})


def draft_reply(d, b, c, rp, r):
    a = c.get('arguments') or {}
    post_url = (a.get('post_url') or '').strip()
    body = (a.get('body') or '').strip()
    author = (a.get('target_author') or '').strip() or None
    snippet = (a.get('target_comment_snippet') or '').strip() or None
    if not post_url or not body or not (author or snippet):
        return fail(b, rp, r, 'INVALID_COMMAND', 'draft_reply requires post_url, body, and target_author or target_comment_snippet.')
    b.navigate(d, b.to_old_reddit(post_url))
    ok, why = b.require_auth(d)
    if not ok:
        return fail(b, rp, r, 'AUTH_BOUNDARY', why, 3)
    thing = b.find_comment_thing(d, author, snippet)
    if thing is None:
        return fail(b, rp, r, 'ADAPTER_ERROR', 'Target Reddit comment was not found.', 8)
    textarea = b.open_reply_editor(d, thing)
    if textarea is None:
        return fail(b, rp, r, 'ADAPTER_ERROR', 'Reply editor could not be opened.', 8)
    b.set_value(d, textarea, body)
    r['execution']['attempted'] = True
    return succeed(b, rp, r, 'Reddit reply draft filled; nothing was submitted.', {
        'post_url': d.current_url,
        'target_author': author,
        'target_comment_snippet': snippet,
        'draft_body': body,
        'draft_text_sha256': b.sha256_text(body),
        'submit_available': b.submit_control(b.form_for(textarea)) is not None,
    })


def submit_reply(d, b, c, rp, r):
    a = c.get('arguments') or {}
    body = (a.get('body') or '').strip()
    ok, why = approved(c, body)
    if not ok:
        return fail(b, rp, r, 'APPROVAL_REQUIRED', why, 4)
    ok, auth_why = b.require_auth(d)
    if not ok:
        return fail(b, rp, r, 'AUTH_BOUNDARY', auth_why, 3)
    candidates = b.visible(d.find_elements('css selector', "form.usertext textarea[name='text']"))
    textarea = next((x for x in candidates if (x.get_attribute('value') or '').strip() == body), None)
    if textarea is None:
        return fail(b, rp, r, 'STALE_DRAFT', 'Approved reply text is not present in an active reply draft.', 9)
    submit = b.submit_control(b.form_for(textarea))
    if submit is None:
        return fail(b, rp, r, 'ADAPTER_ERROR', 'Submit control for the reply draft was not found.', 8)
    waited = b.respect_cooldown('reply')
    r['execution']['attempted'] = True
    try:
        submit.click()
    except Exception:
        d.execute_script('arguments[0].click();', submit)
    time.sleep(1.2)
    b.ready(d)
    if not b.exact_text_present(d, body):
        return fail(b, rp, r, 'VERIFY_FAILED', 'Reply submission was attempted but exact text was not observed afterward.', 10, {'url': d.current_url, 'cooldown_waited_seconds': waited})
    b.record_activity('reply')
    return succeed(b, rp, r, 'Approved Reddit reply submitted and exact text observed.', {'url': d.current_url, 'cooldown_waited_seconds': waited, 'exact_text_observed': True})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--command', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--debugger-address', default='127.0.0.1:9222')
    ap.add_argument('--auth-timeout', type=int, default=60)
    a = ap.parse_args()
    b = load_base()
    c = json.loads(Path(a.command).read_text(encoding='utf-8'))
    od = Path(a.output_dir)
    od.mkdir(parents=True, exist_ok=True)
    rp = od / 'result.json'
    r = b.result_template(c)
    o = webdriver.ChromeOptions()
    o.add_experimental_option('debuggerAddress', a.debugger_address)
    d = webdriver.Chrome(options=o)
    try:
        handlers = {
            'auth_status': auth_status,
            'inspect_page': inspect_page,
            'draft_comment': draft_comment,
            'submit_comment': submit_comment,
            'draft_reply': draft_reply,
            'submit_reply': submit_reply,
        }
        handler = handlers.get(c.get('action'))
        if handler is None:
            return fail(b, rp, r, 'INVALID_COMMAND', f"Unsupported Reddit action: {c.get('action')}")
        return handler(d, b, c, rp, r)
    except Exception as e:
        (od / 'traceback.txt').write_text(traceback.format_exc(), encoding='utf-8')
        return fail(b, rp, r, 'ADAPTER_ERROR', f'Unexpected Reddit adapter failure: {type(e).__name__}: {e}', 12)


if __name__ == '__main__':
    sys.exit(main())
