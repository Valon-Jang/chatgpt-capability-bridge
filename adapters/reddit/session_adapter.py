#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,os,sys,traceback
from pathlib import Path
from selenium import webdriver

def load_base():
    p=Path(os.environ.get('CB_ADAPTER_LIB',Path(__file__).with_name('adapter.py')));s=importlib.util.spec_from_file_location('cb_reddit_base',p);m=importlib.util.module_from_spec(s);assert s.loader is not None;s.loader.exec_module(m);return m

def succeed(b,rp,r,msg,e=None):
    r['status']='VERIFIED_SUCCESS';r['failure_class']=None;r['message']=msg;r['execution']['completed']=True;r['verification']['performed']=True;r['verification']['passed']=True
    if e:r['verification']['evidence'].update(e)
    b.write_json(rp,r);return 0

def fail(b,rp,r,cls,msg,code=2,e=None):
    r['failure_class']=cls;r['message']=msg
    if e:r['verification']['evidence'].update(e)
    b.write_json(rp,r);return code

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--command',required=True);ap.add_argument('--output-dir',required=True);ap.add_argument('--debugger-address',default='127.0.0.1:9222');ap.add_argument('--auth-timeout',type=int,default=60);a=ap.parse_args()
    b=load_base();c=json.loads(Path(a.command).read_text(encoding='utf-8'));od=Path(a.output_dir);od.mkdir(parents=True,exist_ok=True);rp=od/'result.json';r=b.result_template(c)
    o=webdriver.ChromeOptions();o.add_experimental_option('debuggerAddress',a.debugger_address);d=webdriver.Chrome(options=o)
    try:
        action=c.get('action')
        if action=='auth_status':
            r['execution']['attempted']=True;b.navigate(d,b.HOME_URL);logged=b.is_logged_in(d)
            if logged:return succeed(b,rp,r,'Reddit authenticated browser session is active.',{'logged_in':True,'url':d.current_url})
            return fail(b,rp,r,'AUTH_BOUNDARY','Reddit login is not active.',3,{'logged_in':False,'url':d.current_url})
        if action=='inspect_page':
            url=(c.get('arguments') or {}).get('url') or b.TARGET_SUB;b.navigate(d,url);r['execution']['attempted']=True
            return succeed(b,rp,r,'Reddit page controls inspected without submitting anything.',{'url':d.current_url,'title':d.title,'logged_in':b.is_logged_in(d),'controls':b.control_summary(d)})
        return fail(b,rp,r,'INVALID_COMMAND',f'Unsupported Reddit action: {action}')
    except Exception as e:
        (od/'traceback.txt').write_text(traceback.format_exc(),encoding='utf-8');return fail(b,rp,r,'ADAPTER_ERROR',f'Unexpected Reddit adapter failure: {type(e).__name__}: {e}',12)

if __name__=='__main__':sys.exit(main())
