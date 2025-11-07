# app.py

from flask import Flask, jsonify, request, abort
import threading
import time
import os
import sys
import requests
import logging
import random
import socket
from datetime import datetime
from collections import deque
from urllib.parse import urlparse

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("app")

# Add src to path to import services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from services.monitor_service import MonitorService

app = Flask(__name__)
monitor_service = MonitorService()

# Shared status dict
status_data = {
    "last_ping": None,
    "keep_alive_url": None,
    "keep_alive_status": None,
    "monitor_interval": None,
    "recent_logs": deque(maxlen=3)
}

# Optional auth token to protect /status
STATUS_TOKEN = os.environ.get("STATUS_TOKEN")

def default_local_url():
    # Renderでは環境変数 PORT が与えられる（ローカルでの起動時は5000を使用）
    port = os.environ.get("PORT", "5000")
    return f"http://127.0.0.1:{port}/"  # 健康チェック用のルート（"/" が返すヘルス応答を用意）

def keep_alive_loop():
    # env-driven config
    enabled = os.environ.get("ENABLE_SELF_PING", "0") == "1"
    if not enabled:
        app.logger.info("Self-ping disabled (ENABLE_SELF_PING != 1).")
        return

    target_url = os.environ.get("KEEP_ALIVE_URL") or default_local_url()
    try:
        parsed = urlparse(target_url)
        if parsed.hostname in (None, ""):
            target_url = default_local_url()
    except Exception:
        target_url = default_local_url()

    interval = int(os.environ.get("KEEP_ALIVE_INTERVAL", 780))  # 秒
    jitter = int(os.environ.get("KEEP_ALIVE_JITTER_SEC", 30))
    headers = {"User-Agent": "SelfKeepAlive/1.0 (+https://yourproject.example)"}

    status_data["keep_alive_url"] = target_url
    status_data["monitor_interval"] = interval

    logger.info(f"Starting self-ping to {target_url} every {interval}s (jitter ±{jitter}s)")

    while True:
        try:
            # 少しランダム待ち（プロセス全体の同調回避）
            sleep_before = random.uniform(0, jitter)
            time.sleep(sleep_before)

            # HEAD を使って負荷を小さくする（GETに切替も可）
            resp = requests.head(target_url, timeout=10, headers=headers)
            timestamp = datetime.utcnow().isoformat()
            status_data["last_ping"] = timestamp
            status_data["keep_alive_status"] = resp.status_code
            status_data["recent_logs"].appendleft({"time": timestamp, "status": resp.status_code})
            if resp.status_code >= 200 and resp.status_code < 400:
                logger.info(f"Self-ping ok: {resp.status_code} -> {target_url}")
            else:
                logger.warning(f"Self-ping returned {resp.status_code} -> {target_url}")
        except requests.exceptions.RequestException as e:
            timestamp = datetime.utcnow().isoformat()
            logger.error(f"Self-ping failed: {e}")
            status_data["keep_alive_status"] = str(e)
            status_data["last_ping"] = timestamp
            status_data["recent_logs"].appendleft({"time": timestamp, "status": str(e)})
        # メイン間隔＋ランダムジッター（負荷分散）
        sleep_after = interval + random.uniform(-jitter, jitter)
        if sleep_after < 30:
            sleep_after = 30  # 最低 30s を確保
        time.sleep(sleep_after)

def start_background_threads():
    # 既存の monitor 起動を残す
    threading.Thread(target=start_monitoring, daemon=True).start()
    # keep-alive は env で制御
    if os.environ.get("ENABLE_SELF_PING", "0") == "1":
        threading.Thread(target=keep_alive_loop, daemon=True).start()
        logger.info("Started self-ping background thread.")
    else:
        threading.Thread(target=keep_alive_loop, daemon=True).start()  # 関数内で無効化チェックをしているので安全
        logger.info("Keep-alive thread initialized (disabled by env).")
        
@app.before_first_request
def _boot_self_ping():
    t = threading.Thread(target=keep_alive_loop, daemon=True)
    t.start()
    app.logger.info("[self-ping] background thread started.")

# /status を本体にも提供（トークン保護任意）
STATUS_TOKEN = os.environ.get("STATUS_TOKEN")

@app.route("/")
def health_check():
    return "Monitor App is running", 200

@app.route("/status")
def get_status():
    if STATUS_TOKEN:
        token = request.args.get("token")
        if token != STATUS_TOKEN:
            abort(403)
    return jsonify({
        "last_ping": status_data["last_ping"],
        "keep_alive_status": status_data["keep_alive_status"],
        "keep_alive_url": status_data["keep_alive_url"],
        "monitor_interval": status_data["monitor_interval"],
        "recent_logs": status_data["recent_logs"],
    }), 200

def start_monitoring():
    target_url = os.environ.get("TARGET_URL", "https://acro-match-w8t0.onrender.com")
    interval = int(os.environ.get("MONITOR_INTERVAL", 5))  # in minutes
    monitor_service.start_monitoring(target_url, interval=interval)

if __name__ == "__main__":
    # Fallback for local dev server
    app.run(host="0.0.0.0", port=5000)
