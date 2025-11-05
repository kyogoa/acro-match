# blueprints/link.py
from flask import Blueprint, request, jsonify
from utils.user import register_user_info
from utils.sheets import append_row_if_new_user
from datetime import datetime
from utils.logging_util import log_exception

link_bp = Blueprint("link", __name__)

@link_bp.route("/link/liff", methods=["POST"])
def link_liff_unified():
    try:
        data = request.get_json(force=True) or {}
        # パターンA: 初期リンク（ensureLinked）
        #  { "userId": "Uxxxxxxxx" }
        if "userId" in data:
            user_id = data.get("userId", "").strip()
            if not user_id:
                return jsonify({"ok": False, "error": "userId missing"}), 400
            # 必要なら最低限の登録（name/birthdayは空で可）
            register_user_info(name="", birthday="", app_liff_id=user_id)
            return jsonify({"ok": True, "mode": "ensure"}), 200

        # パターンB: 送信直前の冪等リンク
        #  { "nickname": "...", "birthday4": "MMDD", "liff_id": "Uxxxxxxxx" }
        nickname = (data.get("nickname") or "").strip()
        birthday4 = (data.get("birthday4") or "").strip()
        liff_id   = (data.get("liff_id") or "").strip()
        if not (nickname and birthday4 and liff_id):
            return jsonify({"ok": False, "error": "missing params"}), 400

        # ここは既存コードの意図に合わせて柔軟に（8桁/表記は要件に応じて）
        birthday_full = f"2000{birthday4}" if len(birthday4) == 4 else ""
        register_user_info(nickname, birthday_full, app_liff_id=liff_id)

        # ログ保存（必要なら）
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            append_row_if_new_user("アルバイト登録", [nickname, birthday4, liff_id, timestamp])
        except Exception:
            # シート書き込み失敗は致命でない
            pass

        return jsonify({"ok": True, "mode": "pre-submit"}), 200

    except Exception as e:
        log_exception(e, context="/link/liff unified")
        return jsonify({"ok": False, "error": "internal"}), 500