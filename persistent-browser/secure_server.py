#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import re
import threading
import time
import traceback

from flask import Response, jsonify, request

import server as base

LOGIN_TOKEN_PATH = base.DATA_DIR / "login-access-token.txt"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
BASIC_USER = "bridge"
BASIC_PASSWORD_SHA256 = "4d5f2fb1f112b4f125d3d86f3c8c2661b103c57257d77e18526cfc605421fb52"


def _token_ok() -> bool:
    auth = request.authorization
    if not auth or auth.username != BASIC_USER or not auth.password:
        return False
    supplied_hash = hashlib.sha256(auth.password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(BASIC_PASSWORD_SHA256, supplied_hash)


def _unauthorized() -> Response:
    return Response(
        "Authentication required",
        status=401,
        mimetype="text/plain",
        headers={"WWW-Authenticate": 'Basic realm="chatgpt-capability-bridge"'},
    )


def secure_status_endpoint():
    status = base.read_status()
    allowed = {
        "state",
        "updated_at_epoch",
        "browser_ready",
        "qr_ready",
        "command_id",
        "received_at_epoch",
        "sent_at_epoch",
        "timings",
    }
    return jsonify({key: value for key, value in status.items() if key in allowed})


def secure_login_page():
    if not _token_ok():
        return _unauthorized()
    try:
        if base.prepare_qr():
            return Response(
                "<html><body><h2>Naver authenticated</h2><p>You can close this page.</p></body></html>",
                mimetype="text/html",
            )
        stamp = int(base.now())
        return Response(
            f"""<!doctype html><html><head><meta charset='utf-8'><meta http-equiv='refresh' content='8'></head>
            <body style='font-family:sans-serif;max-width:900px;margin:30px auto'>
            <h2>Naver QR login</h2><p>Scan with the Naver app and complete the confirmation. This page refreshes automatically.</p>
            <img src='/qr.png?v={stamp}' style='max-width:100%;border:1px solid #ccc'>
            </body></html>""",
            mimetype="text/html",
        )
    except Exception as exc:
        return Response(f"Login preparation failed: {type(exc).__name__}", status=500)


def secure_qr_image():
    if not _token_ok():
        return _unauthorized()
    if not base.QR_PATH.exists():
        base.prepare_qr()
    if not base.QR_PATH.exists():
        return Response("QR not ready", status=404)
    return Response(base.QR_PATH.read_bytes(), mimetype="image/png")


base.app.view_functions["status_endpoint"] = secure_status_endpoint
base.app.view_functions["login_page"] = secure_login_page
base.app.view_functions["qr_image"] = secure_qr_image
app = base.app


def worker_loop() -> None:
    base.ensure_keypair()
    last_id = base.LAST_ID_PATH.read_text(encoding="utf-8").strip() if base.LAST_ID_PATH.exists() else ""
    base.write_status("idle", browser_ready=True)
    while True:
        text = None
        try:
            text = base.fetch_command_text()
            if not text or text == "PENDING" or text.startswith("#"):
                time.sleep(base.POLL_SECONDS)
                continue
            command = base.decrypt_command(text)
            command_id = str(command.get("id") or command.get("command_id") or "")
            if not command_id or command_id == last_id:
                time.sleep(base.POLL_SECONDS)
                continue

            action = str(command.get("action") or "")
            received = base.now()
            last_id = command_id
            base.LAST_ID_PATH.write_text(command_id, encoding="utf-8")

            if action == "configure_login_access":
                token = str(command.get("token") or "")
                if not TOKEN_RE.fullmatch(token):
                    raise RuntimeError("Invalid login token")
                LOGIN_TOKEN_PATH.write_text(token, encoding="utf-8")
                try:
                    LOGIN_TOKEN_PATH.chmod(0o600)
                except OSError:
                    pass
                base.write_status(
                    "login_access_ready",
                    command_id=command_id,
                    received_at_epoch=received,
                    browser_ready=True,
                )
                time.sleep(base.POLL_SECONDS)
                continue

            if action != "send_mail":
                raise RuntimeError("Unsupported action")

            base.write_status("sending", command_id=command_id, received_at_epoch=received)
            result = base.send_mail(command)
            result.update({"command_id": command_id, "received_at_epoch": received})
            base.write_status(**result)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            command_meta = {}
            if text:
                encoded = text.encode("utf-8")
                command_meta = {
                    "command_sha256": hashlib.sha256(encoded).hexdigest(),
                    "command_bytes": len(encoded),
                }
            if "AUTH_REQUIRED" in msg:
                try:
                    base.prepare_qr()
                except Exception:
                    pass
                base.write_status("auth_required", error="AUTH_REQUIRED", **command_meta)
            else:
                base.write_status("failed", error=msg, traceback=traceback.format_exc(limit=3), **command_meta)
        time.sleep(base.POLL_SECONDS)


if __name__ == "__main__":
    base.ensure_keypair()
    try:
        base.start_browser_runtime()
    except Exception as exc:
        base.write_status("browser_start_failed", error=f"{type(exc).__name__}: {exc}")
        raise
    threading.Thread(target=worker_loop, name="secure-command-worker", daemon=True).start()
    app.run(host="0.0.0.0", port=base.PORT, threaded=True, use_reloader=False)