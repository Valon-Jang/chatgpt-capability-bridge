#!/usr/bin/env python3
"""Focused persistent cleanup for the single EXP-002 synthetic Naver Calendar event."""
from __future__ import annotations
import argparse, importlib.util, json, os, sys, time, traceback
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


def load_base():
    p=Path(os.environ.get('CB_ADAPTER_LIB',Path(__file__).with_name('adapter.py'))
    s=importlib.util.spec_from_file_location('cb_base',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def visible(xs):
    out=[]
    for x in xs:
        try:
            if x.is_displayed():out.append(x)
        except WebDriverException:pass
    return out

def goto_calendar(d,b):
    d.switch_to.default_content();d.get(b.TARGET_URL);WebDriverWait(d,20).until(lambda x:x.execute_script('return document.readyState')=='complete');time.sleep(1.2)

def ensure_auth(d,b,t,r,rp):
    goto_calendar(d,b)
    if b.wait_for_auth(d,t):return True
    r['failure_class']='AUTH_BOUNDARY';r['message']='Authenticated persistent session was not detected.';b.write_json(rp,r);return False

def title_node(d,title):
    xp=f"//*[normalize-space(.)={json.dumps(title,ensure_ascii=False)}]";xs=visible(d.find_elements(By.XPATH,xp));return xs[0] if xs else None

def tap(d,e):
    d.execute_script("""const e=arguments[0],r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;try{e.dispatchEvent(new TouchEvent('touchstart',{bubbles:true,cancelable:true,touches:[]}));}catch(_){}for(const t of ['pointerdown','mousedown','pointerup','mouseup','click'])e.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,clientX:x,clientY:y,view:window}));""",e)

def click_text(d,texts,timeout=5):
    end=time.time()+timeout
    while time.time()<end:
        for t in texts:
            xp=f"//*[self::button or self::a or @role='button'][contains(normalize-space(.),{json.dumps(t,ensure_ascii=False)})]"
            for e in visible(d.find_elements(By.XPATH,xp)):
                try:d.execute_script('arguments[0].click();',e);return True
                except Exception:pass
        time.sleep(.25)
    return False

def controls(d):
    out=[]
    for e in visible(d.find_elements(By.CSS_SELECTOR,'button,a,[role="button"]')):
        try:
            t=(e.text or '').strip();out.append({'tag':e.tag_name,'class':e.get_attribute('class'),'aria_label':e.get_attribute('aria-label'),'title':e.get_attribute('title'),'ui_text':(t[:40]+'…' if len(t)>40 else t) or None})
        except WebDriverException:pass
    return out[:80]

def click_delete(d):
    for sel in ["button[aria-label*='삭제']","button[title*='삭제']","[role='button'][aria-label*='삭제']","button[class*='delete']","button[class*='trash']","a[class*='delete']","a[class*='trash']"]:
        for e in visible(d.find_elements(By.CSS_SELECTOR,sel)):
            try:d.execute_script('arguments[0].click();',e);return True
            except Exception:pass
    return click_text(d,['삭제','일정 삭제'],3)

def cleanup(d,b,c,od,timeout):
    r=b.result_template(c);rp=od/'result.json';title=(c.get('arguments') or {}).get('title');r['execution']['attempted']=True
    if not ensure_auth(d,b,timeout,r,rp):return 3
    found=b.wait_for_exact_text(d,title,12);r['verification']['performed']=True;r['verification']['evidence']['created_title_observed']=found
    if not found:
        r['execution']['completed']=True;r['cleanup']['completed']=True;r['verification']['evidence']['cleanup_absence_observed']=True;r['verification']['passed']=True;r['status']='VERIFIED_SUCCESS';r['failure_class']=None;r['message']='No residual synthetic event observable.';b.write_json(rp,r);return 0
    r['cleanup']['attempted']=True
    # Stage 1: month view card -> daily view.
    e=title_node(d,title)
    if e is None:r['failure_class']='ADAPTER_ERROR';r['message']='Synthetic title node missing in month view.';b.write_json(rp,r);return 8
    tap(d,e);time.sleep(1.1)
    # Stage 2: same event in daily view -> event detail.
    if '/daily' in (d.current_url or ''):
        if not b.wait_for_exact_text(d,title,8):r['failure_class']='ADAPTER_ERROR';r['message']='Daily view opened but synthetic event was not visible.';b.write_json(rp,r);return 8
        e2=title_node(d,title)
        if e2 is None:r['failure_class']='ADAPTER_ERROR';r['message']='Synthetic title node missing in daily view.';b.write_json(rp,r);return 8
        tap(d,e2);time.sleep(1.0)
    # Follow detail -> edit -> trash/delete. Detail may be same-route overlay.
    edit_clicked=click_text(d,['수정'],4)
    if edit_clicked:time.sleep(.7)
    if not click_delete(d):
        r['failure_class']='ADAPTER_ERROR';r['message']='Two-stage event navigation completed, but delete control was not found.';r['diagnostics']={'url':d.current_url,'controls':controls(d)};b.write_json(rp,r);return 9
    time.sleep(.5);click_text(d,['삭제','확인','예'],4);time.sleep(1.2);goto_calendar(d,b)
    absent=not b.exact_text_present(d,title);r['execution']['completed']=True;r['verification']['evidence']['cleanup_absence_observed']=absent;r['cleanup']['completed']=absent
    if not absent:r['failure_class']='VERIFY_FAILED';r['message']='Deletion was attempted but absence could not be verified.';b.write_json(rp,r);return 10
    r['verification']['passed']=True;r['status']='VERIFIED_SUCCESS';r['failure_class']=None;r['message']='Synthetic event deleted through month -> daily -> detail/edit flow and absence verified.';b.write_json(rp,r);return 0

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--command',required=True);ap.add_argument('--output-dir',required=True);ap.add_argument('--debugger-address',default='127.0.0.1:9222');ap.add_argument('--auth-timeout',type=int,default=60);a=ap.parse_args();b=load_base();c=json.loads(Path(a.command).read_text());o=webdriver.ChromeOptions();o.add_experimental_option('debuggerAddress',a.debugger_address);d=webdriver.Chrome(options=o);od=Path(a.output_dir)
    try:
        if c.get('action')=='recover_verify_delete_event':return cleanup(d,b,c,od,a.auth_timeout)
        r=b.result_template(c);r['failure_class']='ADAPTER_ERROR';r['message']='Unsupported cleanup action';b.write_json(od/'result.json',r);return 2
    except Exception as e:
        r=b.result_template(c);r['failure_class']='ADAPTER_ERROR';r['message']=f'Unexpected cleanup failure: {type(e).__name__}: {e}';od.mkdir(parents=True,exist_ok=True);(od/'traceback.txt').write_text(traceback.format_exc());b.write_json(od/'result.json',r);return 12
if __name__=='__main__':sys.exit(main())
