#!/usr/bin/env python3
from __future__ import annotations
import json,time
from pathlib import Path
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

HOME_URL='https://www.reddit.com/'
TARGET_SUB='https://www.reddit.com/r/LocalLLaMA/'

def write_json(path: Path,payload: dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def result_template(command: dict)->dict:
    return {'status':'FAILED','failure_class':None,'message':'','action':command.get('action'),'command_id':command.get('command_id'),'execution':{'attempted':False,'completed':False},'verification':{'performed':False,'passed':False,'evidence':{}}}

def visible(elements):
    out=[]
    for e in elements:
        try:
            if e.is_displayed(): out.append(e)
        except WebDriverException: pass
    return out

def ready(driver,timeout=20):
    WebDriverWait(driver,timeout).until(lambda d:d.execute_script('return document.readyState')=='complete')

def navigate(driver,url):
    driver.switch_to.default_content();driver.get(url);ready(driver);time.sleep(0.8)

def is_logged_in(driver):
    try:
        cookies={c.get('name',''):c.get('value','') for c in driver.get_cookies()}
        if cookies.get('reddit_session'): return True
        url=(driver.current_url or '').lower()
        if '/login' in url or '/register' in url: return False
        markers=driver.execute_script("return Array.from(document.querySelectorAll('a,button')).slice(0,400).map(x=>((x.getAttribute('href')||'')+' '+(x.textContent||'')).toLowerCase());")
        return any('/user/' in m or '/settings' in m or 'logout' in m or 'log out' in m for m in markers)
    except Exception:return False

def control_summary(driver,limit=120):
    rows=[]
    for e in visible(driver.find_elements(By.CSS_SELECTOR,"input,textarea,button,select,a,[contenteditable='true']"))[:limit]:
        try:
            rows.append({'tag':e.tag_name,'type':e.get_attribute('type'),'name':e.get_attribute('name'),'id':e.get_attribute('id'),'class':(e.get_attribute('class') or '')[:180],'placeholder':e.get_attribute('placeholder'),'aria_label':e.get_attribute('aria-label'),'role':e.get_attribute('role'),'value':(e.get_attribute('value') or '')[:100],'text':(e.text or '')[:180],'href':(e.get_attribute('href') or '')[:240]})
        except WebDriverException:pass
    return rows
