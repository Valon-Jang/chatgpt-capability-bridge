#!/usr/bin/env python3
"""Wait for Naver QR authentication without navigating away from the QR page.

Attaches to the persistent Chrome instance, polls only cookie names / safe page
state, and exits only after the authenticated Naver session is visible. It does
not print or persist cookie values, credentials, or tokens.
"""
from __future__ import annotations

import argparse
import time

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By


def authenticated(driver) -> bool:
    try:
        names = {c.get("name", "") for c in driver.get_cookies()}
        if {"NID_AUT", "NID_SES"}.issubset(names):
            return True
    except WebDriverException:
        pass

    try:
        body = driver.find_element(By.TAG_NAME, "body").text
        lowered = body.lower()
        # QR login completion can redirect away from the login surface before
        # both cookie names become observable in Selenium's current context.
        if "qr sign-in" not in lowered and "qr 코드 로그인" not in body and "qr코드 로그인" not in body:
            current = (driver.current_url or "").lower()
            if "nid.naver.com/nidlogin" not in current and "nid.naver.com/login" not in current:
                return True
    except WebDriverException:
        pass
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debugger-address", default="127.0.0.1:9222")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", args.debugger_address)
    driver = webdriver.Chrome(options=options)

    print("AUTH_REQUIRED: scan the published Naver QR; the QR page will remain open until authentication completes.", flush=True)
    end = time.time() + args.timeout
    while time.time() < end:
        if authenticated(driver):
            print("AUTHENTICATED: Naver session detected; command execution may now begin.", flush=True)
            return 0
        time.sleep(1)

    print("AUTH_BOUNDARY: QR authentication was not detected before timeout.", flush=True)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
