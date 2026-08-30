#!/usr/bin/env python3
"""Finalize the already-open EXP-002 Naver Calendar delete confirmation."""
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

def finalize(d,b,c,od,t):
    r=b.result_template(c);rp=od/'result.json';title=(c.get('arguments')or{}).get('title');r['execution']['attempted']=True;r['cleanup']['attempted']=True;r['verification']['performed']=True
    # Preserve current browser state: the delete confirmation popup was already opened by the prior probe.
    confirms=visible(d.find_elements(By.CSS_SELECTOR,'button.btn_confirm'))
    if not confirms:
        r['failure_class']='ADAPTER_ERROR';r['message']='Expected pending delete confirmation button was not visible.';b.write_json(rp,r);return 8
    try:confirms[0].click()
    except Exception:d.execute_script('arguments[0].click();',confirms[0])
    time.sleep(1.5)
    d.switch_to.default_content();d.get(b.TARGET_URL);WebDriverWait(d,20).until(lambda x:x.execute_script('return document.readyState')=='complete');time.sleep(1.5)
    if not b.wait_for_auth(d,t):r['failure_class']='AUTH_BOUNDARY';r['message']='Authentication was lost after delete confirmation.';b.write_json(rp,r);return 3
    absent=not b.exact_text_present(d,title);r['execution']['completed']=True;r['verification']['evidence']['cleanup_absence_observed']=absent;r['cleanup']['completed']=absent
    if not absent:r['failure_class']='VERIFY_FAILED';r['message']='Delete confirmation was clicked but exact-title absence was not verified.';b.write_json(rp,r);return 10
    r['verification']['passed']=True;r['status']='VERIFIED_SUCCESS';r['failure_class']=None;r['message']='Pending delete was confirmed and exact-title absence verified.';b.write_json(rp,r);return 0

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--command',required=True);ap.add_argument('--output-dir',required=True);ap.add_argument('--debugger-address',default='127.0.0.1:9222');ap.add_argument('--auth-timeout',type=int,default=60);a=ap.parse_args();b=load_base();c=json.loads(Path(a.command).read_text());o=webdriver.ChromeOptions();o.add_experimental_option('debuggerAddress',a.debugger_address);d=webdriver.Chrome(options=o);od=Path(a.output_dir)
    try:
        if c.get('action')=='confirm_pending_delete':return finalize(d,b,c,od,a.auth_timeout)
        r=b.result_template(c);r['failure_class']='ADAPTER_ERROR';r['message']='Unsupported finalization action';b.write_json(od/'result.json',r);return 2
    except Exception as e:
        r=b.result_template(c);r['failure_class']='ADAPTER_ERROR';r['message']=f'Unexpected finalization failure: {type(e).__name__}: {e}';od.mkdir(parents=True,exist_ok=True);(od/'traceback.txt').write_text(traceback.format_exc());b.write_json(od/'result.json',r);return 12
if __name__=='__main__':sys.exit(main())
