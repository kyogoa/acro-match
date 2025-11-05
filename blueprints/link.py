# blueprints/link.py
from flask import Blueprint, request, jsonify
from utils.user import register_user_info
from utils.sheets import append_row_if_new_user
from datetime import datetime
from utils.logging_util import log_exception

link_bp = Blueprint("link", __name__)

@link_bp.route(methods=["POST"])
def submit():
    try:
        data = request.get_json()
        print("📩 アルバイト登録データ受信:", data)

        name = data.get("name")
        birthday4 = data.get("birthday4")
        user_id = data.get("userId")  # ← アプリの LIFF ID

        birthday_full = f"2000年{birthday4[:2]}月{birthday4[2:]}日" if len(birthday4) == 4 else ""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        register_user_info(name, birthday_full, app_liff_id=user_id)

        # ログ保存（アルバイト登録シート）
        append_row_if_new_user("アルバイト登録", [name, birthday4, user_id, timestamp])
        return "OK", 200

    except Exception as e:
        print("❌ エラー:", e)
        return "Error", 500

@link_bp.route("/link/liff", methods=["POST"])
def link_liff_id():
    try:
        data = request.get_json(force=True)
        nickname = data.get("nickname", "").strip()
        birthday4 = data.get("birthday4", "").strip()
        liff_id = data.get("liff_id", "").strip()

        if not (nickname and birthday4 and liff_id):
            return jsonify({"error": "パラメータ不足"}), 400

        birthday8 = f"2000{int(birthday4):02d}" if len(birthday4) == 2 else f"2000{birthday4}"

        register_user_info(nickname, birthday8, app_liff_id=liff_id)
        return jsonify({"message": "LIFF連携成功"}), 200

    except Exception as e:
        log_exception(e, context="/link/liff API")
        return jsonify({"error": "内部エラー"}), 500
