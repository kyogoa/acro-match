# blueprints/callback.py
from flask import Blueprint, request, jsonify
import re
from utils.user import register_user_info
from utils.notify import send_line_message
from utils.logging_util import log_exception
from datetime import datetime
import unicodedata 

callback_bp = Blueprint("callback", __name__)

# 🧠 ユーザーごとの一時状態保存（名前）
user_states = {}  # user_id → {'name': str}

@callback_bp.route("/callback", methods=["POST"])
def handle_callback():
    data = request.get_json(silent=True) or {}
    print("📩 Webhook受信:", data)
    return "OK", 200

@callback_bp.route("", methods=["POST"])
def receive_callback():
    try:
        data = request.get_json(force=True)
        print("📩 Webhook受信:", data)
        events = data.get("events", [])

        for event in events:
            user_id = event.get("source", {}).get("userId")
            if not user_id:
                continue

            if event.get("type") == "follow":
                send_line_message(user_id, "ニックネームを送ってください！！\n講師登録でもニックネームとして扱います！")

            elif event.get("type") == "message":
                msg = event.get("message", {}).get("text", "").strip()
                
                 # 🔄 全角→半角へ変換（例：２００４０３０２ → 20040302）
                msg = unicodedata.normalize("NFKC", msg)

                # 生年月日単独パターン（例：20040302）
                if re.match(r"^\d{8}$", msg):
                    name = user_states.get(user_id, {}).get("name")
                    if name:
                        bday_formatted = f"{msg[:4]}年{int(msg[4:6])}月{int(msg[6:])}日"
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        register_user_info(name, bday_formatted, chat_liff_id=user_id)
                        send_line_message(user_id, f"{name} さん、生年月日 {bday_formatted} を登録しました！\nメニューから講師登録をしてください！")
                    continue  # ← ここで次のイベントへ

                # 名前（ニックネーム）だけが送られてきた場合
                user_states[user_id] = {'name': msg}
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                register_user_info(msg, "", chat_liff_id=user_id)
                send_line_message(user_id, f"{msg} さん、登録ありがとうございます！\n次に生年月日を送ってください！\n例：2004年3月2日 → 20040302")

        return "OK", 200
    except Exception as e:
        log_exception(e, context="LINE Callback 処理")
        return "Error", 500

@callback_bp.route("/interest", methods=["POST"])
def receive_interest():
    try:
        print("📨 興味あり受信:", request.json)
        return jsonify({"message": "受信OK"}), 200
    except Exception as e:
        log_exception(e, context="Callback /interest 処理")
        return "Error", 500
