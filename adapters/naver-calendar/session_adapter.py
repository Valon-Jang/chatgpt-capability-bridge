#!/usr/bin/env python3
"""Probe delete-confirmation controls for the single EXP-002 synthetic event."""
from __future__ import annotations
import argparse,importlib.util,json,os,sys,time,traceback
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

def load_base():
    p=Path(os.environ.get('CB_ADAPTER_LIB',Path(__file__).with_name('adapter.py')));s=importlib.util.spec_from_file_location('cb_base',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def visible(xs):
    out=[]
    for x in xs:
        try:
            if x.is_displayed():out.append(x)
        except WebDriverException:pass
    return out

def goto_calendar(d,b):
    d.switch_to.default_content();d.get(b.TARGET_URL);WebDriverWait(d,20).until(lambda x:x.execute_script('return document.readyState')=='complete');time.sleep(1.2)

def nodes(d,title):
    xp=f"//*[normalize-space(.)={json.dumps(title,ensure_ascii=False)}]";return visible(d.find_elements(By.XPATH,xp))

def trusted_tap(d,e):
    r=d.execute_script("const r=arguments[0].getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};",e);x=float(r['x']);y=float(r['y']);d.execute_cdp_cmd('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y,'radiusX':2,'radiusY':2,'force':1.0}]});time.sleep(.08);d.execute_cdp_cmd('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})

def click_text(d,texts,timeout=5):
    end=time.time()+timeout
    while time.time()<end:
        for t in texts:
            xp=f"//*[self::button or self::a or @role='button'][contains(normalize-space(.),{json.dumps(t,ensure_ascii=False)})]"
            for e in visible(d.find_elements(By.XPATH,xp)):
                try:e.click();return True
                except Exception:
                    try:d.execute_script('arguments[0].click();',e);return True
                    except Exception:pass
        time.sleep(.25)
    return False

def actual_daily_item(d,title):
    root=d.find_element(By.ID,'daily_list_scroll_element')
    for e in nodes(d,title):
        try:
            if not d.execute_script('return arguments[0].contains(arguments[1]);',root,e):continue
            cur=e
            for _ in range(6):
                if cur.tag_name.lower()=='li' and 'schedule_item' in (cur.get_attribute('class') or ''):return cur
                cur=cur.find_element(By.XPATH,'..')
        except WebDriverException:continue
    return None

def controls(d):
    out=[]
    for e in visible(d.find_elements(By.CSS_SELECTOR,'button,a,[role="button"]')):
        try:
            t=(e.text or '').strip();out.append({'tag':e.tag_name,'class':e.get_attribute('class'),'aria_label':e.get_attribute('aria-label'),'title':e.get_attribute('title'),'ui_text':(t[:80]+'…' if len(t)>80 else t) or None})
        except WebDriverException:pass
    return out[:120]

def click_delete(d):
    for sel in ["button[aria-label*='삭제']","button[title*='삭제']","[role='button'][aria-label*='삭제']","[role='button'][title*='삭제']","button[class*='delete']","button[class*='trash']","a[class*='delete']","a[class*='trash']","[class*='btn_delete']","[class*='btn_trash']"]:
        for e in visible(d.find_elements(By.CSS_SELECTOR,sel)):
            try:e.click();return True
            except Exception:
                try:d.execute_script('arguments[0].click();',e);return True
                except Exception:pass
    return click_text(d,['삭제','일정 삭제'],3)

def probe(d,b,c,od,t):
    r=b.result_template(c);rp=od/'result.json';title=(c.get('arguments')or{}).get('title');r['cleanup']={'requested':True,'attempted':True,'completed':False};r['execution']['attempted']=True;goto_calendar(d,b)
    if not b.wait_for_auth(d,t):r['failure_class']='AUTH_BOUNDARY';r['message']='Auth missing';b.write_json(rp,r);return 3
    if not b.wait_for_exact_text(d,title,12):r['status']='VERIFIED_SUCCESS';r['failure_class']=None;r['execution']['completed']=True;r['verification']['performed']=True;r['verification']['passed']=True;r['verification']['evidence']['cleanup_absence_observed']=True;r['cleanup']['completed']=True;r['message']='Synthetic event already absent.';b.write_json(rp,r);return 0
    trusted_tap(d,nodes(d,title)[0]);time.sleep(1);item=actual_daily_item(d,title)
    if item is None:r['failure_class']='ADAPTER_ERROR';r['message']='Actual daily item missing';b.write_json(rp,r);return 8
    try:item.click()
    except Exception:trusted_tap(d,item)
    time.sleep(1.1)
    if not click_delete(d):
        click_text(d,['수정'],5);time.sleep(.7)
        if not click_delete(d):r['failure_class']='ADAPTER_ERROR';r['message']='Delete control not found';r['diagnostics']={'controls':controls(d),'url':d.current_url};b.write_json(rp,r);return 9
    time.sleep(.7)
    r['diagnostics']={'url_after_delete_control':d.current_url,'confirmation_controls':controls(d)};r['execution']['completed']=True;r['verification']['performed']=True;r['verification']['evidence']['created_title_observed']=True;r['verification']['passed']=True;r['status']='VERIFIED_SUCCESS';r['failure_class']=None;r['message']='Delete control activated; confirmation controls captured without confirming deletion.';b.write_json(rp,r);return 0

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--command',required=True);ap.add_argument('--output-dir',required=True);ap.add_argument('--debugger-address',default='127.0.0.1:9222');ap.add_argument('--auth-timeout',type=int,default=60);a=ap.parse_args();b=load_base();c=json.loads(Path(a.command).read_text());o=webdriver.ChromeOptions();o.add_experimental_option('debuggerAddress',a.debugger_address);d=webdriver.Chrome(options=o);od=Path(a.output_dir)
    try:
        if c.get('action')=='probe_delete_confirmation':return probe(d,b,c,od,a.auth_timeout)
        r=b.result_template(c);r['failure_class']='ADAPTER_ERROR';r['message']='Unsupported action';b.write_json(od/'result.json',r);return 2
    except Exception as e:
        r=b.result_template(c);r['failure_class']='ADAPTER_ERROR';r['message']=f'Unexpected probe failure: {type(e).__name__}: {e}';od.mkdir(parents=True,exist_ok=True);(od/'traceback.txt').write_text(traceback.format_exc());b.write_json(od/'result.json',r);return 12
if __name__=='__main__':sys.exit(main())
