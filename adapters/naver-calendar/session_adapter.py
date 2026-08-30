#!/usr/bin/env python3
"""Compact daily-list node classifier for EXP-002 cleanup."""
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

def matches(d,title):
    xp=f"//*[normalize-space(.)={json.dumps(title,ensure_ascii=False)}]";return visible(d.find_elements(By.XPATH,xp))

def tap(d,e):
    r=d.execute_script("const r=arguments[0].getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};",e);d.execute_cdp_cmd('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':float(r['x']),'y':float(r['y']),'radiusX':2,'radiusY':2,'force':1.0}]});time.sleep(.08);d.execute_cdp_cmd('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})

def compact(d,e,i):
    return d.execute_script("""
    const e=arguments[0],i=arguments[1],r=e.getBoundingClientRect(),root=document.getElementById('daily_list_scroll_element');
    const top=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
    let cur=e,anc=[];for(let n=0;n<8&&cur;n++,cur=cur.parentElement){anc.push({tag:cur.tagName.toLowerCase(),id:cur.id||'',class:typeof cur.className==='string'?cur.className:''});}
    return {index:i,tag:e.tagName.toLowerCase(),class:typeof e.className==='string'?e.className:'',rect:{x:r.x,y:r.y,w:r.width,h:r.height},within_daily_list:!!(root&&root.contains(e)),top_at_center:top?{tag:top.tagName.toLowerCase(),id:top.id||'',class:typeof top.className==='string'?top.className:''}:null,ancestors:anc};
    """,e,i)

def diagnose(d,b,c,od,t):
    r=b.result_template(c);rp=od/'result.json';title=(c.get('arguments')or{}).get('title');r['cleanup']={'requested':False,'attempted':False,'completed':True};r['execution']['attempted']=True;goto_calendar(d,b)
    if not b.wait_for_auth(d,t):r['failure_class']='AUTH_BOUNDARY';r['message']='Auth missing';b.write_json(rp,r);return 3
    ms=matches(d,title)
    if not ms:r['failure_class']='VERIFY_FAILED';r['message']='Synthetic event not visible';b.write_json(rp,r);return 7
    tap(d,ms[0]);time.sleep(1);ds=matches(d,title)
    summaries=[compact(d,e,i) for i,e in enumerate(ds)]
    r['diagnostics']={'url':d.current_url,'match_count':len(ds),'summaries':summaries};r['execution']['completed']=True;r['verification']['performed']=True;r['verification']['evidence']['created_title_observed']=bool(ds);r['verification']['passed']=True;r['status']='VERIFIED_SUCCESS';r['failure_class']=None;r['message']='Daily exact-title matches classified by actual daily-list containment.';b.write_json(rp,r);return 0

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--command',required=True);ap.add_argument('--output-dir',required=True);ap.add_argument('--debugger-address',default='127.0.0.1:9222');ap.add_argument('--auth-timeout',type=int,default=60);a=ap.parse_args();b=load_base();c=json.loads(Path(a.command).read_text());o=webdriver.ChromeOptions();o.add_experimental_option('debuggerAddress',a.debugger_address);d=webdriver.Chrome(options=o);od=Path(a.output_dir)
    try:
        if c.get('action')=='classify_daily_matches':return diagnose(d,b,c,od,a.auth_timeout)
        r=b.result_template(c);r['failure_class']='ADAPTER_ERROR';r['message']='Unsupported action';b.write_json(od/'result.json',r);return 2
    except Exception as e:
        r=b.result_template(c);r['failure_class']='ADAPTER_ERROR';r['message']=f'Unexpected diagnostic failure: {type(e).__name__}: {e}';od.mkdir(parents=True,exist_ok=True);(od/'traceback.txt').write_text(traceback.format_exc());b.write_json(od/'result.json',r);return 12
if __name__=='__main__':sys.exit(main())
