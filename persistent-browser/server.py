#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import threading
import time
import traceback
from pathlib import Path
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import Flask, Response, jsonify
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

DATA_DIR = Path(os.environ.get("BRIDGE_DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR = DATA_DIR / "chrome-profile"
PRIVATE_KEY_PATH = DATA_DIR / "bridge-private.pem"
PUBLIC_KEY_PATH = DATA_DIR / "bridge-public.pem"
QR_PATH = DATA_DIR / "naver-qr.png"
STATUS_PATH = DATA_DIR / "status.json"
LAST_ID_PATH = DATA_DIR / "last-command-id.txt"

COMMAND_URL = os.environ.get(
    "BRIDGE_COMMAND_URL",
    "https://raw.githubusercontent.com/Valon-Jang/chatgpt-capability-bridge/main/.bridge/mail-command.enc",
)
POLL_SECONDS = float(os.environ.get("BRIDGE_POLL_SECONDS", "1.0"))
DEBUGGER_ADDRESS = os.environ.get("BRIDGE_DEBUGGER_ADDRESS", "127.0.0.1:9222")
CHROME_BIN = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
DISPLAY = os.environ.get("DISPLAY", ":99")
PORT = int(os.environ.get("PORT", "8080"))

LOGIN_URL = "https://nid.naver.com/nidlogin.login"
MAIL_URL = "https://mail.naver.com"

app = Flask(__name__)
_runtime_lock = threading.RLock()
_driver: webdriver.Chrome | None = None
_chrome_proc: subprocess.Popen | None = None
_xvfb_proc: subprocess.Popen | None = None
_started_at = time.time()


def now() -> float:
    return time.time()


def write_status(state: str, **extra: Any) -> None:
    payload = {"state": state, "updated_at_epoch": now(), **extra}
    tmp = STATUS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATUS_PATH)


def read_status() -> dict[str, Any]:
    if STATUS_PATH.exists():
        try:
            return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"state": "starting", "updated_at_epoch": now()}


def ensure_keypair() -> None:
    if PRIVATE_KEY_PATH.exists() and PUBLIC_KEY_PATH.exists():
        return
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    PRIVATE_KEY_PATH.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    PUBLIC_KEY_PATH.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def start_browser_runtime() -> None:
    global _xvfb_proc, _chrome_proc, _driver
    with _runtime_lock:
        os.environ["DISPLAY"] = DISPLAY
        if _xvfb_proc is None or _xvfb_proc.poll() is not None:
            _xvfb_proc = subprocess.Popen(
                ["Xvfb", DISPLAY, "-screen", "0", "1440x900x24", "-ac"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            time.sleep(0.8)
        if _chrome_proc is None or _chrome_proc.poll() is not None:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            try:
                version = subprocess.check_output([CHROME_BIN, "--version"], text=True, stderr=subprocess.STDOUT).strip()
            except Exception as exc:
                version = f"version-read-failed:{type(exc).__name__}:{exc}"
            print(f"[bridge] chromium={version}", flush=True)
            _chrome_proc = subprocess.Popen(
                [
                    CHROME_BIN,
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-default-browser-check",
                    "--lang=ko-KR",
                    "--remote-debugging-address=127.0.0.1",
                    "--remote-debugging-port=9222",
                    f"--user-data-dir={PROFILE_DIR}",
                    "--window-position=0,0",
                    "--window-size=1440,900",
                    "about:blank",
                ],
                env=os.environ.copy(),
            )
        deadline = now() + 30
        while now() < deadline:
            try:
                r = requests.get("http://127.0.0.1:9222/json/version", timeout=1)
                if r.ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.3)
        else:
            raise RuntimeError(f"Chrome CDP endpoint did not become ready; exit_code={_chrome_proc.poll() if _chrome_proc else None}")
        if _driver is None:
            opts = webdriver.ChromeOptions()
            opts.add_experimental_option("debuggerAddress", DEBUGGER_ADDRESS)
            _driver = webdriver.Chrome(options=opts)
            _driver.set_page_load_timeout(35)


def driver() -> webdriver.Chrome:
    global _driver
    start_browser_runtime()
    assert _driver is not None
    try:
        _ = _driver.current_url
        return _driver
    except WebDriverException:
        _driver = None
        start_browser_runtime()
        assert _driver is not None
        return _driver


def visible(elements):
    out = []
    for el in elements:
        try:
            if el.is_displayed() and el.rect.get("width", 0) > 0 and el.rect.get("height", 0) > 0:
                out.append(el)
        except WebDriverException:
            pass
    return out


def cookie_names(d: webdriver.Chrome) -> set[str]:
    try:
        return {c.get("name", "") for c in d.get_cookies()}
    except WebDriverException:
        return set()


def is_authenticated(d: webdriver.Chrome, navigate: bool = False) -> bool:
    if navigate:
        d.switch_to.default_content()
        d.get(MAIL_URL)
        WebDriverWait(d, 20).until(
            lambda x: x.execute_script("return document.readyState") in {"interactive", "complete"}
        )
        time.sleep(0.5)
    names = cookie_names(d)
    if "NID_AUT" in names or "NID_SES" in names:
        return True
    return "nidlogin" not in (d.current_url or "").lower() and "mail.naver.com" in (d.current_url or "")


def click_qr(d: webdriver.Chrome, timeout: float = 12.0) -> bool:
    texts = ["QR 코드 로그인", "QR코드 로그인", "QR코드", "QR 코드", "QR코드로 로그인", "QR code"]
    end = now() + timeout
    while now() < end:
        for text in texts:
            for xpath in [
                f"//*[self::button or self::a or @role='button' or @role='tab'][normalize-space(.)='{text}']",
                f"//*[self::button or self::a or @role='button' or @role='tab'][contains(normalize-space(.), '{text}')]",
            ]:
                for el in visible(d.find_elements(By.XPATH, xpath)):
                    try:
                        d.execute_script("arguments[0].click();", el)
                        return True
                    except WebDriverException:
                        pass
        time.sleep(0.25)
    return False


def qr_present(d: webdriver.Chrome) -> bool:
    selectors = ["canvas", "img[src*='qr']", "img[src*='QR']", "img[alt*='QR']", "[class*='qr'] img", "[id*='qr'] img"]
    for selector in selectors:
        try:
            if visible(d.find_elements(By.CSS_SELECTOR, selector)):
                return True
        except WebDriverException:
            pass
    try:
        text = d.find_element(By.TAG_NAME, "body").text.lower()
        return "qr" in text and ("네이버 앱" in text or "naver app" in text or "로그인" in text)
    except WebDriverException:
        return False


def prepare_qr() -> bool:
    with _runtime_lock:
        d = driver()
        if is_authenticated(d, navigate=True):
            return True
        d.switch_to.default_content()
        d.get(LOGIN_URL)
        WebDriverWait(d, 20).until(
            lambda x: x.execute_script("return document.readyState") in {"interactive", "complete"}
        )
        time.sleep(0.5)
        if not click_qr(d):
            d.get(LOGIN_URL + "?mode=qrcode")
            time.sleep(1.0)
        deadline = now() + 10
        while now() < deadline and not qr_present(d):
            time.sleep(0.25)
        d.save_screenshot(str(QR_PATH))
        write_status("auth_required", qr_ready=QR_PATH.exists(), current_url=d.current_url)
        return False


def decrypt_command(envelope_text: str) -> dict[str, Any]:
    envelope = json.loads(envelope_text)
    key = serialization.load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)
    aes_key = key.decrypt(
        base64.b64decode(envelope["wrapped_key"]),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    nonce = base64.b64decode(envelope["nonce"])
    ciphertext = base64.b64decode(envelope["ciphertext"])
    plaintext = AESGCM(aes_key).decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))


def find_compose(d: webdriver.Chrome):
    for el in visible(d.find_elements(By.CSS_SELECTOR, "button,a,[role='button']")):
        try:
            label = " ".join(filter(None, [el.text, el.get_attribute("aria-label"), el.get_attribute("title")])).strip()
            if re.search(r"메일\s*쓰기", label):
                return el
        except WebDriverException:
            pass
    return None


def find_subject(d: webdriver.Chrome):
    selectors = [
        "input[placeholder*='제목']",
        "input[aria-label*='제목']",
        "input[name*='subject' i]",
        "input[id*='subject' i]",
        "input[id*='title' i]",
    ]
    for selector in selectors:
        els = visible(d.find_elements(By.CSS_SELECTOR, selector))
        if els:
            return els[0]
    ref = visible(d.find_elements(By.ID, "reference_input_element"))
    recipient = visible(d.find_elements(By.ID, "recipient_input_element"))
    if not ref:
        return None
    ref_y = ref[0].rect.get("y", 0)
    bad = set(ref + recipient)
    candidates = []
    for el in visible(d.find_elements(By.CSS_SELECTOR, "input[type='text'],input:not([type])")):
        if el in bad:
            continue
        rect = el.rect
        if rect.get("width", 0) > 400 and ref_y + 15 < rect.get("y", 0) < ref_y + 100:
            candidates.append(el)
    candidates.sort(key=lambda x: x.rect.get("y", 99999))
    return candidates[0] if candidates else None


def find_body(d: webdriver.Chrome):
    top_selectors = [
        "[contenteditable='true'][role='textbox']",
        "div[contenteditable='true']",
        "textarea[placeholder*='내용']",
        "textarea[aria-label*='내용']",
    ]
    d.switch_to.default_content()
    for selector in top_selectors:
        els = visible(d.find_elements(By.CSS_SELECTOR, selector))
        if els:
            return (None, els[0])
    frames = d.find_elements(By.TAG_NAME, "iframe")
    for idx, frame in enumerate(frames):
        try:
            d.switch_to.default_content()
            d.switch_to.frame(frame)
            for selector in ["body[contenteditable='true']", "[contenteditable='true']", "textarea"]:
                els = visible(d.find_elements(By.CSS_SELECTOR, selector))
                if els:
                    return (idx, els[0])
        except WebDriverException:
            continue
    d.switch_to.default_content()
    return (None, None)


def set_recipient(d: webdriver.Chrome, to: str, subject_el) -> None:
    recipient = visible(d.find_elements(By.ID, "recipient_input_element"))
    if not recipient:
        raise RuntimeError("recipient_input_element not found")
    el = recipient[0]
    d.execute_script(
        """
        const el=arguments[0], value=arguments[1];
        const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
        setter.call(el,''); el.dispatchEvent(new Event('input',{bubbles:true}));
        setter.call(el,value); el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true})); el.focus();
        """,
        el,
        to,
    )
    time.sleep(0.45)
    exact = visible(d.find_elements(By.XPATH, f"//*[normalize-space(.)={json.dumps(to)}]"))
    if exact:
        d.execute_script("arguments[0].click();", exact[0])
    elif subject_el is not None:
        d.execute_script("arguments[0].click();", subject_el)
    time.sleep(0.15)


def send_mail(command: dict[str, Any]) -> dict[str, Any]:
    timings: dict[str, float] = {}
    t0 = now()
    to = str(command["to"])
    subject = str(command.get("subject", ""))
    body = str(command.get("body", ""))
    with _runtime_lock:
        d = driver()
        d.switch_to.default_content()
        d.get(MAIL_URL)
        WebDriverWait(d, 20).until(
            lambda x: x.execute_script("return document.readyState") in {"interactive", "complete"}
        )
        time.sleep(0.5)
        timings["open_mail_s"] = round(now() - t0, 3)
        if not is_authenticated(d):
            raise RuntimeError("AUTH_REQUIRED")
        t = now()
        compose = None
        deadline = now() + 10
        while now() < deadline and compose is None:
            compose = find_compose(d)
            if compose is None:
                time.sleep(0.2)
        if compose is None:
            raise RuntimeError("Compose button not found")
        d.execute_script("arguments[0].click();", compose)
        WebDriverWait(d, 12).until(lambda x: bool(visible(x.find_elements(By.ID, "recipient_input_element"))))
        timings["compose_open_s"] = round(now() - t, 3)
        t = now()
        subject_el = find_subject(d)
        set_recipient(d, to, subject_el)
        subject_el = find_subject(d)
        if subject_el is None:
            raise RuntimeError("Subject field not found")
        subject_el.clear()
        subject_el.send_keys(subject)
        timings["recipient_subject_s"] = round(now() - t, 3)
        t = now()
        frame_idx, body_el = find_body(d)
        if body_el is None:
            raise RuntimeError("Body editor not found")
        body_el.click()
        body_el.send_keys(body)
        d.switch_to.default_content()
        timings["body_s"] = round(now() - t, 3)
        t = now()
        recipient = visible(d.find_elements(By.ID, "recipient_input_element"))
        recipient_value = recipient[0].get_attribute("value") if recipient else ""
        page_text = d.find_element(By.TAG_NAME, "body").text
        if recipient_value != to and to not in page_text:
            raise RuntimeError("Exact recipient readback failed")
        subject_check = find_subject(d)
        subject_value = subject_check.get_attribute("value") if subject_check else ""
        if subject and subject_value != subject and subject not in page_text:
            raise RuntimeError("Subject readback failed")
        timings["readback_s"] = round(now() - t, 3)
        t = now()
        send_el = None
        for el in visible(d.find_elements(By.CSS_SELECTOR, "button,a,[role='button']")):
            try:
                label = " ".join(filter(None, [el.text, el.get_attribute("aria-label"), el.get_attribute("title")])).strip()
                if label in {"보내기", "메일 보내기", "Send"}:
                    send_el = el
                    break
            except WebDriverException:
                pass
        if send_el is None:
            raise RuntimeError("Send button not found")
        d.execute_script("arguments[0].click();", send_el)
        deadline = now() + 12
        sent = False
        while now() < deadline:
            time.sleep(0.2)
            d.switch_to.default_content()
            text = ""
            try:
                text = d.find_element(By.TAG_NAME, "body").text
            except WebDriverException:
                pass
            url = d.current_url or ""
            if "/done" in url or re.search(r"메일을\s*보냈|발송.*완료|보내기\s*완료", text):
                sent = True
                break
            dialogs = visible(d.find_elements(By.CSS_SELECTOR, "[role='dialog'],dialog"))
            if dialogs:
                for btn in visible(d.find_elements(By.CSS_SELECTOR, "button,a,[role='button']")):
                    try:
                        label = " ".join(filter(None, [btn.text, btn.get_attribute("aria-label"), btn.get_attribute("title")])).strip()
                        if label in {"확인", "보내기", "Send"}:
                            d.execute_script("arguments[0].click();", btn)
                            break
                    except WebDriverException:
                        pass
        timings["send_confirm_s"] = round(now() - t, 3)
        timings["total_browser_s"] = round(now() - t0, 3)
        if not sent:
            raise RuntimeError(f"Send completion not observed; url={d.current_url}")
        return {"ok": True, "state": "sent", "url": d.current_url, "timings": timings, "sent_at_epoch": now()}


def fetch_command_text() -> str | None:
    try:
        sep = "&" if "?" in COMMAND_URL else "?"
        r = requests.get(
            f"{COMMAND_URL}{sep}_={int(now() * 1000)}",
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            timeout=10,
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.text.strip()
    except requests.RequestException as exc:
        write_status("command_transport_error", error=f"{type(exc).__name__}: {exc}")
        return None


def worker_loop() -> None:
    ensure_keypair()
    last_id = LAST_ID_PATH.read_text(encoding="utf-8").strip() if LAST_ID_PATH.exists() else ""
    write_status("idle", browser_ready=True)
    while True:
        try:
            text = fetch_command_text()
            if not text or text == "PENDING" or text.startswith("#"):
                time.sleep(POLL_SECONDS)
                continue
            command = decrypt_command(text)
            command_id = str(command.get("id") or command.get("command_id") or "")
            if not command_id or command_id == last_id:
                time.sleep(POLL_SECONDS)
                continue
            last_id = command_id
            LAST_ID_PATH.write_text(command_id, encoding="utf-8")
            received = now()
            write_status("sending", command_id=command_id, received_at_epoch=received)
            if command.get("action") != "send_mail":
                raise RuntimeError("Unsupported action")
            result = send_mail(command)
            result.update({"command_id": command_id, "received_at_epoch": received})
            write_status(**result)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            if "AUTH_REQUIRED" in msg:
                try:
                    prepare_qr()
                except Exception:
                    pass
                write_status("auth_required", error=msg, traceback=traceback.format_exc(limit=3))
            else:
                write_status("failed", error=msg, traceback=traceback.format_exc(limit=3))
        time.sleep(POLL_SECONDS)


@app.get("/health")
def health():
    s = read_status()
    return jsonify(ok=True, uptime_s=round(now() - _started_at, 1), browser_process_alive=bool(_chrome_proc and _chrome_proc.poll() is None), state=s.get("state"))


@app.get("/status")
def status_endpoint():
    return jsonify(read_status())


@app.get("/public-key")
def public_key():
    ensure_keypair()
    return Response(PUBLIC_KEY_PATH.read_text(encoding="utf-8"), mimetype="text/plain")


@app.get("/login")
def login_page():
    try:
        if prepare_qr():
            return Response("<html><body><h2>Naver authenticated</h2><p>You can close this page.</p></body></html>", mimetype="text/html")
        stamp = int(now())
        return Response(
            f"""<!doctype html><html><head><meta charset='utf-8'><meta http-equiv='refresh' content='8'></head>
            <body style='font-family:sans-serif;max-width:900px;margin:30px auto'>
            <h2>Naver QR login</h2><p>Scan with the Naver app and complete the confirmation. This page refreshes automatically.</p>
            <img src='/qr.png?v={stamp}' style='max-width:100%;border:1px solid #ccc'>
            </body></html>""",
            mimetype="text/html",
        )
    except Exception as exc:
        return Response(f"Login preparation failed: {type(exc).__name__}: {exc}", status=500)


@app.get("/qr.png")
def qr_image():
    if not QR_PATH.exists():
        prepare_qr()
    if not QR_PATH.exists():
        return Response("QR not ready", status=404)
    return Response(QR_PATH.read_bytes(), mimetype="image/png")


if __name__ == "__main__":
    ensure_keypair()
    try:
        start_browser_runtime()
    except Exception as exc:
        write_status("browser_start_failed", error=f"{type(exc).__name__}: {exc}")
        raise
    threading.Thread(target=worker_loop, name="command-worker", daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)
