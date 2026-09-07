#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import threading
import time

from flask import Response, jsonify, redirect, request
from selenium.webdriver.common.keys import Keys

import server as base
import secure_server as secure

secure.LOGIN_PASSWORD_SHA256 = os.environ.get(
    "BRIDGE_LOGIN_PASSWORD_SHA256",
    secure.LOGIN_PASSWORD_SHA256,
).strip().lower()

YOUTUBE_STUDIO_URL = "https://studio.youtube.com/"
BROWSER_LOCK = threading.RLock()


def _login_form(error: bool = False, status: int = 200) -> Response:
    error_html = "<p style='color:#ff6b6b'>비밀번호가 틀렸습니다.</p>" if error else ""
    response = Response(
        f"""<!doctype html><html><head><meta charset='utf-8'>
        <meta name='viewport' content='width=device-width,initial-scale=1,maximum-scale=1'>
        <title>Luna YouTube Mobile Bridge</title></head>
        <body style='font-family:system-ui,sans-serif;max-width:560px;margin:44px auto;padding:0 20px;background:#0f0f0f;color:#fff'>
        <h2>Luna YouTube Mobile Bridge</h2>
        <p style='color:#bbb'>전용 클라우드 브라우저를 여는 임시 비밀번호를 입력하세요.</p>
        {error_html}
        <form method='post' action='/login'>
          <input name='password' type='password' autocomplete='one-time-code' required
                 style='box-sizing:border-box;width:100%;font-size:18px;padding:14px;margin:8px 0 14px;border-radius:10px'>
          <button type='submit' style='width:100%;font-size:17px;padding:13px;border-radius:10px'>YouTube 연결 화면 열기</button>
        </form>
        </body></html>""",
        status=status,
        mimetype="text/html",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def mobile_login_page():
    if request.method == "POST":
        if not secure._password_ok():
            return _login_form(error=True, status=401)
        response = redirect("/youtube", code=303)
        response.set_cookie(
            secure.LOGIN_COOKIE,
            secure._session_token(),
            max_age=secure.LOGIN_COOKIE_MAX_AGE,
            secure=True,
            httponly=True,
            samesite="Lax",
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    if not secure._session_ok():
        return _login_form()
    return redirect("/youtube", code=302)


def _require_session():
    if not secure._session_ok():
        return Response("AUTH_REQUIRED", status=401, mimetype="text/plain")
    return None


def _state():
    with BROWSER_LOCK:
        d = base.driver()
        url = d.current_url or ""
        title = d.title or ""
        lower = url.lower()
        connected = "studio.youtube.com" in lower and "accounts.google.com" not in lower
        return {"url": url, "title": title, "connected": connected}


def youtube_page():
    if not secure._session_ok():
        return redirect("/login", code=302)
    try:
        with BROWSER_LOCK:
            d = base.driver()
            current = (d.current_url or "").lower()
            if "studio.youtube.com" not in current and "accounts.google.com" not in current:
                d.get(YOUTUBE_STUDIO_URL)
    except Exception:
        pass
    response = Response(
        """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Luna YouTube Mobile Bridge</title>
<style>
body{margin:0;background:#0f0f0f;color:#fff;font-family:system-ui,-apple-system,sans-serif}
.wrap{max-width:760px;margin:auto;padding:12px} h2{font-size:19px;margin:4px 0 8px}
#state{font-size:12px;color:#aaa;margin-bottom:8px;word-break:break-all}
.screenbox{background:#222;border:1px solid #333;border-radius:10px;overflow:hidden}
#screen{display:block;width:100%;height:auto;touch-action:manipulation}
.controls{display:grid;grid-template-columns:1fr auto;gap:8px;margin-top:10px}
#text{font-size:16px;padding:12px;border-radius:9px;border:1px solid #444;background:#191919;color:#fff;min-width:0}
button{font-size:15px;padding:11px 12px;border:0;border-radius:9px;background:#2a2a2a;color:#fff}
button.primary{background:#ff0033}.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.note{font-size:12px;color:#999;line-height:1.45;margin-top:10px}
</style></head>
<body><div class="wrap">
<h2>공대루나 · YouTube 연결</h2><div id="state">브라우저 준비 중…</div>
<div class="screenbox"><img id="screen" src="/youtube/screen.png?t=0" alt="cloud browser"></div>
<div class="controls"><input id="text" type="text" autocomplete="off" autocapitalize="off" placeholder="선택한 칸에 입력"><button id="send">입력</button></div>
<div class="row">
<button class="primary" id="open">YouTube Studio</button>
<button data-key="ENTER">Enter</button><button data-key="TAB">Tab</button><button data-key="BACKSPACE">⌫</button>
<button data-scroll="-550">↑</button><button data-scroll="550">↓</button><button id="refresh">새로고침</button>
</div>
<div class="note">위 화면을 터치하면 같은 위치가 클라우드 Chrome에서 눌립니다. 이메일/비밀번호 입력칸을 먼저 터치한 뒤 아래 입력칸으로 입력하세요. 입력 문자열은 파일이나 애플리케이션 로그에 기록하지 않습니다. Google 로그인과 2단계 인증은 본인이 직접 완료하세요.</div>
</div>
<script>
const img=document.getElementById('screen'),state=document.getElementById('state'),text=document.getElementById('text');let busy=false;
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});if(!r.ok)throw new Error(await r.text());return r.json().catch(()=>({}));}
function reload(){img.src='/youtube/screen.png?t='+Date.now();}
async function poll(){try{const r=await fetch('/youtube/state',{cache:'no-store'});const j=await r.json();state.textContent=(j.connected?'✅ 연결됨 · ':'')+(j.title||'')+' · '+(j.url||'');}catch(e){state.textContent='상태 확인 실패';}}
img.addEventListener('click',async e=>{if(busy)return;busy=true;try{const r=img.getBoundingClientRect();const x=(e.clientX-r.left)*(img.naturalWidth/r.width);const y=(e.clientY-r.top)*(img.naturalHeight/r.height);await post('/youtube/tap',{x,y});setTimeout(reload,220);setTimeout(poll,320);}finally{busy=false;}});
document.getElementById('send').onclick=async()=>{const v=text.value;if(!v)return;await post('/youtube/type',{text:v});text.value='';setTimeout(reload,220);setTimeout(poll,320);};
document.querySelectorAll('[data-key]').forEach(b=>b.onclick=async()=>{await post('/youtube/key',{key:b.dataset.key});setTimeout(reload,180);});
document.querySelectorAll('[data-scroll]').forEach(b=>b.onclick=async()=>{await post('/youtube/scroll',{dy:Number(b.dataset.scroll)});setTimeout(reload,180);});
document.getElementById('open').onclick=async()=>{await post('/youtube/open',{});setTimeout(reload,450);setTimeout(poll,650);};
document.getElementById('refresh').onclick=()=>{reload();poll();};
setInterval(reload,1800);setInterval(poll,2500);poll();
</script></body></html>""",
        mimetype="text/html",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def youtube_screen():
    auth = _require_session()
    if auth:
        return auth
    try:
        with BROWSER_LOCK:
            png = base.driver().get_screenshot_as_png()
        response = Response(png, mimetype="image/png")
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response
    except Exception as exc:
        return Response(f"SCREEN_FAILED:{type(exc).__name__}", status=500)


def youtube_state():
    auth = _require_session()
    if auth:
        return auth
    try:
        return jsonify(_state())
    except Exception as exc:
        return jsonify({"connected": False, "error": type(exc).__name__}), 500


def youtube_open():
    auth = _require_session()
    if auth:
        return auth
    try:
        with BROWSER_LOCK:
            base.driver().get(YOUTUBE_STUDIO_URL)
        return jsonify(_state())
    except Exception as exc:
        return jsonify({"ok": False, "error": type(exc).__name__}), 500


def youtube_tap():
    auth = _require_session()
    if auth:
        return auth
    payload = request.get_json(silent=True) or {}
    x, y = float(payload.get("x", 0)), float(payload.get("y", 0))
    if not (0 <= x <= 1440 and 0 <= y <= 900):
        return jsonify({"ok": False, "error": "coordinate_out_of_range"}), 400
    with BROWSER_LOCK:
        d = base.driver()
        d.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        d.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        d.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
    return jsonify({"ok": True})


def youtube_type():
    auth = _require_session()
    if auth:
        return auth
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", ""))
    if not text or len(text) > 2048:
        return jsonify({"ok": False, "error": "invalid_text"}), 400
    with BROWSER_LOCK:
        base.driver().switch_to.active_element.send_keys(text)
    return jsonify({"ok": True})


def youtube_key():
    auth = _require_session()
    if auth:
        return auth
    payload = request.get_json(silent=True) or {}
    mapping = {"ENTER": Keys.ENTER, "TAB": Keys.TAB, "BACKSPACE": Keys.BACKSPACE, "ESCAPE": Keys.ESCAPE}
    key = mapping.get(str(payload.get("key", "")).upper())
    if key is None:
        return jsonify({"ok": False, "error": "unsupported_key"}), 400
    with BROWSER_LOCK:
        base.driver().switch_to.active_element.send_keys(key)
    return jsonify({"ok": True})


def youtube_scroll():
    auth = _require_session()
    if auth:
        return auth
    payload = request.get_json(silent=True) or {}
    dy = max(-1200, min(1200, float(payload.get("dy", 0))))
    with BROWSER_LOCK:
        base.driver().execute_cdp_cmd(
            "Input.dispatchMouseEvent",
            {"type": "mouseWheel", "x": 720, "y": 450, "deltaX": 0, "deltaY": dy},
        )
    return jsonify({"ok": True})


base.app.view_functions["login_page"] = mobile_login_page
base.app.view_functions["login_post"] = mobile_login_page
base.app.add_url_rule("/youtube", endpoint="youtube_page", view_func=youtube_page, methods=["GET"])
base.app.add_url_rule("/youtube/screen.png", endpoint="youtube_screen", view_func=youtube_screen, methods=["GET"])
base.app.add_url_rule("/youtube/state", endpoint="youtube_state", view_func=youtube_state, methods=["GET"])
base.app.add_url_rule("/youtube/open", endpoint="youtube_open", view_func=youtube_open, methods=["POST"])
base.app.add_url_rule("/youtube/tap", endpoint="youtube_tap", view_func=youtube_tap, methods=["POST"])
base.app.add_url_rule("/youtube/type", endpoint="youtube_type", view_func=youtube_type, methods=["POST"])
base.app.add_url_rule("/youtube/key", endpoint="youtube_key", view_func=youtube_key, methods=["POST"])
base.app.add_url_rule("/youtube/scroll", endpoint="youtube_scroll", view_func=youtube_scroll, methods=["POST"])
app = base.app


if __name__ == "__main__":
    base.ensure_keypair()
    base.start_browser_runtime()
    threading.Thread(target=secure.worker_loop, name="secure-command-worker", daemon=True).start()
    app.run(host="0.0.0.0", port=base.PORT, threaded=True, use_reloader=False)
