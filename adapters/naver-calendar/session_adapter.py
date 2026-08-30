#!/usr/bin/env python3
"""Focused daily-view DOM diagnostic for EXP-002 cleanup."""
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

def title_node(d,title):
 xp=f"//*[normalize-space(.)={json.dumps(title,ensure_ascii=False)}]";xs=visible(d.find_elements(By.XPATH,xp));return xs[0] if xs else None

def tap(d,e):
 d.execute_script("""const e=arguments[0],r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;for(const t of ['pointerdown','mousedown','pointerup','mouseup','click'])e.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,clientX:x,clientY:y,view:window}));""",e)

def attrs(d,e):
 try:
  a=d.execute_script("""const o={};for(const x of arguments[0].attributes||[]){const n=x.name.toLowerCase();if(n==='style'||n==='value')continue;if(n.startsWith('data-')||n.startsWith('aria-')||['id','class','role','href','title','tabindex','type'].includes(n))o[x.name]=x.value;}return o;""",e) or {};return {'tag':e.tag_name,'attrs':a}
 except WebDriverException:return {'unavailable':True}

def chain(d,e):
 out=[];cur=e
 for depth in range(12):
  z=attrs(d,cur);z['depth']=depth;out.append(z)
  try:cur=cur.find_element(By.XPATH,'..')
  except WebDriverException:break
 return out

def diagnose(d,b,c,od,t):
 r=b.result_template(c);rp=od/'result.json';title=(c.get('arguments')or{}).get('title');r['cleanup']={'requested':False,'attempted':False,'completed':True};r['execution']['attempted']=True
 goto_calendar(d,b)
 if not b.wait_for_auth(d,t):r['failure_class']='AUTH_BOUNDARY';r['message']='Auth missing';b.write_json(rp,r);return 3
 if not b.wait_for_exact_text(d,title,12):r['failure_class']='VERIFY_FAILED';r['message']='Synthetic event not visible in month view';b.write_json(rp,r);return 7
 e=title_node(d,title);tap(d,e);time.sleep(1.0)
 if '/daily' not in (d.current_url or ''):r['failure_class']='ADAPTER_ERROR';r['message']='Month card did not open daily view';b.write_json(rp,r);return 8
 if not b.wait_for_exact_text(d,title,8):r['failure_class']='ADAPTER_ERROR';r['message']='Synthetic event not visible in daily view';b.write_json(rp,r);return 8
 e2=title_node(d,title);r['diagnostics']={'url':d.current_url,'daily_title_ancestor_chain':chain(d,e2)};r['execution']['completed']=True;r['verification']['performed']=True;r['verification']['evidence']['created_title_observed']=True;r['verification']['passed']=True;r['status']='VERIFIED_SUCCESS';r['failure_class']=None;r['message']='Daily-view synthetic event structure captured.';b.write_json(rp,r);return 0

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--command',required=True);ap.add_argument('--output-dir',required=True);ap.add_argument('--debugger-address',default='127.0.0.1:9222');ap.add_argument('--auth-timeout',type=int,default=60);a=ap.parse_args();b=load_base();c=json.loads(Path(a.command).read_text());o=webdriver.ChromeOptions();o.add_experimental_option('debuggerAddress',a.debugger_address);d=webdriver.Chrome(options=o);od=Path(a.output_dir)
 try:
  if c.get('action')=='diagnose_daily_event_card':return diagnose(d,b,c,od,a.auth_timeout)
  r=b.result_template(c);r['failure_class']='ADAPTER_ERROR';r['message']='Unsupported diagnostic action';b.write_json(od/'result.json',r);return 2
 except Exception as e:
  r=b.result_template(c);r['failure_class']='ADAPTER_ERROR';r['message']=f'Unexpected diagnostic failure: {type(e).__name__}: {e}';od.mkdir(parents=True,exist_ok=True);(od/'traceback.txt').write_text(traceback.format_exc());b.write_json(od/'result.json',r);return 12
if __name__=='__main__':sys.exit(main())
