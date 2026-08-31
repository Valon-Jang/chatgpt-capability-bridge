#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from selenium import webdriver
from selenium.webdriver.common.by import By

HOME = "https://news.hada.io/"
LOGIN = "https://news.hada.io/login"


def visible(elements):
    out = []
    for element in elements:
        try:
            if element.is_displayed():
                out.append(element)
        except Exception:
            pass
    return out


def logged_in(driver):
    if "/login" in (driver.current_url or ""):
        return False
    if visible(driver.find_elements(By.CSS_SELECTOR, 'a[href*="logout"]')):
        return True
    return not visible(driver.find_elements(By.CSS_SELECTOR, 'a[href="/login"],a[href$="/login"]'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debugger-address", default="127.0.0.1:9222")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()
    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", args.debugger_address)
    driver = webdriver.Chrome(options=options)
    if not driver.current_url or driver.current_url == "about:blank":
        driver.get(LOGIN)
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        if "/login" not in (driver.current_url or ""):
            driver.get(HOME)
            time.sleep(0.7)
            if logged_in(driver):
                print("GEEKNEWS_AUTH_OK", flush=True)
                return 0
            driver.get(LOGIN)
        time.sleep(2)
    print("GEEKNEWS_AUTH_TIMEOUT", flush=True)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
