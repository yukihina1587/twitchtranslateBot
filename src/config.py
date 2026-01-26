import json
import os
from datetime import datetime
from src.logger import logger

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "twitch_client_id": "",
    "twitch_access_token": "",  # 保存されたアクセストークン（自動ログイン用）
    "deepl_api_key": "",
    "channel_name": "",
    "translate_mode": "自動",
    "voicevox_url": "http://localhost:50021",
    "voicevox_speaker_id": 14,  # 冥鳴ひまり (Meimei Himari)
    "voicevox_engine_path": "",  # VOICEVOX Engineの実行ファイルパス
    "voicevox_auto_start": True,  # VOICEVOX Engineを自動起動するかどうか
    # Gladia STT設定
    "gladia_api_key": "",
    "gladia_usage_seconds": 0,  # 今月の使用秒数
    "gladia_reset_month": "",  # 最後にリセットした月 (例: "2025-12")
    "stt_provider": "gladia",  # 音声認識プロバイダー: "gladia" または "google"
    # イベント効果音
    "bits_sound_path": "",
    "subscription_sound_path": "",
    # 翻訳フィルタとカスタム辞書
    "translation_filters": [],
    "translation_dictionary": [],  # [{ "source": "原文", "target": "置換後" }]
    # コメント表示/出力設定
    "comment_log_bg": "#0E1728",
    "comment_log_fg": "#E8F0FF",
    "comment_log_font": "Consolas 11",
    "comment_bubble_style": "classic",  # classic / bubble / minimal
    "chat_html_output": False,
    "chat_html_path": "",
    "chat_html_newest_first": False,  # True: 上が新しい, False: 下が新しい
    # UI テーマ
    "ui_theme": "default",  # default / gradient / minimal / cyberpunk
}

VALID_TRANSLATE_MODES = {"自動", "英→日", "日→英"}
VALID_UI_THEMES = {"default", "gradient", "minimal", "cyberpunk"}

def validate_config(config_data):
    """
    設定値を検証し、不足値をデフォルトで補完する
    Returns: (validated_config, changed: bool)
    """
    changed = False
    validated = DEFAULT_CONFIG.copy()
    validated.update(config_data or {})

    # translate_mode
    if validated.get("translate_mode") not in VALID_TRANSLATE_MODES:
        logger.warning(f"translate_mode is invalid: {validated.get('translate_mode')}, fallback to 自動")
        validated["translate_mode"] = "自動"
        changed = True

    # ui_theme
    if validated.get("ui_theme") not in VALID_UI_THEMES:
        logger.warning(f"ui_theme is invalid: {validated.get('ui_theme')}, fallback to default")
        validated["ui_theme"] = "default"
        changed = True

    # ブール値はbool化
    for key in ["voicevox_auto_start"]:
        if not isinstance(validated.get(key), bool):
            validated[key] = bool(validated.get(key))
            changed = True

    # 文字列系はNone回避
    for key in [
        "twitch_client_id",
        "twitch_access_token",
        "deepl_api_key",
        "channel_name",
        "voicevox_url",
        "voicevox_engine_path",
        "gladia_api_key",
        "gladia_reset_month",
        "stt_provider",
        "bits_sound_path",
        "subscription_sound_path",
        "comment_log_bg",
        "comment_log_fg",
        "comment_log_font",
        "comment_bubble_style",
        "chat_html_path",
        "ui_theme",
    ]:
        if validated.get(key) is None:
            validated[key] = DEFAULT_CONFIG.get(key, "")
            changed = True

    # リスト系
    if not isinstance(validated.get("translation_filters"), list):
        validated["translation_filters"] = []
        changed = True

    if not isinstance(validated.get("translation_dictionary"), list):
        validated["translation_dictionary"] = []
        changed = True

    # ブール系
    for key in ["chat_html_output", "chat_html_newest_first"]:
        if not isinstance(validated.get(key), bool):
            validated[key] = bool(validated.get(key))
            changed = True

    # translation_dictionary の正規化
    normalized_dict = []
    for entry in validated.get("translation_dictionary", []):
        if not isinstance(entry, dict):
            changed = True
            continue
        src = entry.get("source", "")
        tgt = entry.get("target", "")
        if not src and not tgt:
            continue
        normalized_dict.append({"source": str(src), "target": str(tgt)})
    if normalized_dict != validated.get("translation_dictionary", []):
        validated["translation_dictionary"] = normalized_dict
        changed = True

    return validated, changed

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            validated, changed = validate_config(raw)
            if changed:
                save_config(validated)
            return validated
    except Exception as e:
        logger.error(f"Failed to load config: {e}", exc_info=True)
        return DEFAULT_CONFIG.copy()

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save config: {e}", exc_info=True)

def check_gladia_usage(config_data):
    """
    Gladiaの使用時間をチェックし、月の制限に達しているか確認
    10時間（36000秒）を超えている場合はGoogle SRに自動切り替え
    新しい月になっている場合は使用時間をリセット

    Returns:
        bool: Gladiaが使用可能な場合True、制限超過でFalse
    """
    current_month = datetime.now().strftime("%Y-%m")
    reset_month = config_data.get("gladia_reset_month", "")
    usage_seconds = config_data.get("gladia_usage_seconds", 0)

    # 新しい月になったらリセット
    if reset_month != current_month:
        config_data["gladia_usage_seconds"] = 0
        config_data["gladia_reset_month"] = current_month
        config_data["stt_provider"] = "gladia"  # Gladiaに戻す
        save_config(config_data)
        logger.info(f"Gladia usage reset for new month: {current_month}")
        return True

    # 10時間（36000秒）の制限チェック
    MAX_SECONDS = 36000  # 10時間
    if usage_seconds >= MAX_SECONDS:
        if config_data.get("stt_provider") != "google":
            config_data["stt_provider"] = "google"
            save_config(config_data)
            logger.warning(f"Gladia usage limit reached ({usage_seconds}s / {MAX_SECONDS}s). Switched to Google SR.")
        return False

    return True

def update_gladia_usage(config_data, seconds):
    """
    Gladiaの使用時間を更新

    Args:
        config_data: 設定データ
        seconds: 追加する秒数
    """
    config_data["gladia_usage_seconds"] = config_data.get("gladia_usage_seconds", 0) + seconds
    save_config(config_data)

    remaining = 36000 - config_data["gladia_usage_seconds"]
    logger.info(f"Gladia usage: {config_data['gladia_usage_seconds']}s / 36000s (Remaining: {remaining}s / {remaining/3600:.1f}h)")
