#!/usr/bin/env python3
"""Prepare Naver QR login in an already-running Chrome and capture the QR screen.

The screenshot is intended for a short-lived human authentication handoff.
No account password, MFA secret, cookie value, or session token is printed.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

LOGIN_URL = "https://nid.naver.com/nidlogin.login"


def visible(elements):
    out = []
    for el in elements:
        try:
            if el.is_displayed():
                out.append(el)
        except WebDriverException:
            pass
    return out


def click_qr(driver, timeout: float = 15.0) -> bool:
    texts = ["QR 코드 로그인", "QR코드 로그인", "QR코드", "QR 코드", "QR코드로 로그인"]
    end = time.time() + timeout
    while time.time() < end:
        for text in texts:
            literals = [
                f"//*[self::button or self::a or @role='button'][normalize-space(.)='{text}']",
                f"//*[self::button or self::a or @role='button'][contains(normalize-space(.), '{text}')]",
                f"//*[normalize-space(.)='{text}']",
            ]
            for xpath in literals:
                try:
                    for el in visible(driver.find_elements(By.XPATH, xpath)):
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                            driver.execute_script("arguments[0].click();", el)
                            return True
                        except WebDriverException:
                            continue
                except WebDriverException:
                    continue
        time.sleep(0.4)
    return False


def qr_surface_present(driver) -> bool:
    selectors = [
        "canvas",
        "img[src*='qr']",
        "img[alt*='QR']",
        "img[alt*='qr']",
        "[class*='qr'] img",
        "[class*='QR'] img",
    ]
    for selector in selectors:
        try:
            if visible(driver.find_elements(By.CSS_SELECTOR, selector)):
                return True
        except WebDriverException:
            pass
    try:
        body = driver.find_element(By.TAG_NAME, "body").text
        return "QR" in body and ("네이버 앱" in body or "스캔" in body or "로그인" in body)
    except WebDriverException:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debugger-address", default="127.0.0.1:9222")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", args.debugger_address)
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(45)
    driver.get(LOGIN_URL)
    time.sleep(1.5)

    if not click_qr(driver):
        print("QR_BOOTSTRAP_FAILED: QR login control not found", flush=True)
        return 2

    end = time.time() + 15
    while time.time() < end and not qr_surface_present(driver):
        time.sleep(0.5)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(output))
    print(f"QR_BOOTSTRAP_READY: screenshot={output}", flush=True)
    # Do not quit: Chrome belongs to the persistent workflow.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
