from flask import Flask, render_template, request, redirect, url_for, send_file, Response
from blueprints.alb import alb_bp
from blueprints.classroom import classroom_bp
from blueprints.callback import callback_bp
from blueprints.link import link_bp
from blueprints.admin import admin_bp
from dotenv import load_dotenv
import os
from flask_wtf import CSRFProtect
import threading, time, random, requests
from datetime import datetime
from urllib.parse import urlparse

# 直近3件の自己ping状態を保持（上の import 群の下あたりに配置）
status_data = {
    "last_ping": None,
    "keep_alive_url": None,
    "keep_alive_status": None,
    "monitor_interval": None,
    "recent_logs": [],  # 直近3件だけ
}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret-key")

csrf = CSRFProtect()
csrf.init_app(app)
csrf.exempt(callback_bp)

load_dotenv()

# Blueprintの登録
app.register_blueprint(alb_bp)
app.register_blueprint(classroom_bp, url_prefix="/classroom")
app.register_blueprint(callback_bp, url_prefix="/callback")
app.register_blueprint(link_bp)
app.register_blueprint(admin_bp)

@app.route("/")
def index():
    return Response("\U0001F4D8 Flask アプリ稼働中：/alb, /classroom, /callback, /link などのルートを確認してください。", content_type="text/plain; charset=utf-8")

def _default_local_url():
    port = os.environ.get("PORT", "5000")
    return f"http://127.0.0.1:{port}/"

def _keep_alive_loop(app):
    enabled = os.environ.get("ENABLE_SELF_PING", "0") == "1"
    if not enabled:
        app.logger.info("Self-ping disabled (ENABLE_SELF_PING != 1).")
        return

    target_url = os.environ.get("KEEP_ALIVE_URL") or _default_local_url()
    try:
        parsed = urlparse(target_url)
        if not parsed.hostname:
            target_url = _default_local_url()
    except Exception:
        target_url = _default_local_url()

    interval = int(os.environ.get("KEEP_ALIVE_INTERVAL", 780))   # 推奨 13 分
    jitter   = int(os.environ.get("KEEP_ALIVE_JITTER_SEC", 30))  # ±30 秒のジッター
    headers  = {"User-Agent": "SelfKeepAlive/1.0"}

    status_data["keep_alive_url"] = target_url
    status_data["monitor_interval"] = interval
    app.logger.info(f"[self-ping] -> {target_url} every {interval}s (±{jitter}s)")

    while True:
        try:
            time.sleep(random.uniform(0, jitter))  # 事前ジッター
            resp = requests.head(target_url, timeout=10, headers=headers)
            ts = datetime.utcnow().isoformat()
            status_data["last_ping"] = ts
            status_data["keep_alive_status"] = resp.status_code
            status_data["recent_logs"] = ([{"time": ts, "status": resp.status_code}] + _status["recent_logs"])[:3]
            if 200 <= resp.status_code < 400:
                app.logger.info(f"[self-ping] ok: {resp.status_code} -> {target_url}")
            else:
                app.logger.warning(f"[self-ping] status {resp.status_code} -> {target_url}")
        except requests.RequestException as e:
            ts = datetime.utcnow().isoformat()
            status_data["last_ping"] = ts
            status_data["keep_alive_status"] = str(e)
            status_data["recent_logs"] = ([{"time": ts, "status": str(e)}] + _status["recent_logs"])[:3]
            app.logger.error(f"[self-ping] failed: {e}")

        time.sleep(max(30, interval + random.uniform(-jitter, jitter)))  # 最低30秒は空ける

@app.before_first_request
def _boot_self_ping():
    t = threading.Thread(target=_keep_alive_loop, args=(app,), daemon=True)
    t.start()
    app.logger.info("[self-ping] background thread started.")

@app.route("/status")
def status():
    token_env = os.environ.get("STATUS_TOKEN")  # 設定しなければ誰でも見える
    if token_env:
        token = request.args.get("token")
        if token != token_env:
            return Response("Forbidden", status=403)
    return {
        "last_ping": _status["last_ping"],
        "keep_alive_status": _status["keep_alive_status"],
        "keep_alive_url": _status["keep_alive_url"],
        "monitor_interval": _status["monitor_interval"],
        "recent_logs": _status["recent_logs"],
    }, 200

if __name__ == "__main__":
    app.run(debug=True)
