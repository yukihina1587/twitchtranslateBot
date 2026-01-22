from src.config import validate_config, DEFAULT_CONFIG


def test_validate_config_fills_defaults_and_clamps_mode():
    raw = {
        "translate_mode": "invalid",
        "voicevox_auto_start": "yes",  # truthy but not bool
        "deepl_api_key": None,
    }
    validated, changed = validate_config(raw)

    assert validated["translate_mode"] == "自動"
    assert validated["voicevox_auto_start"] is True
    assert validated["deepl_api_key"] == ""  # None -> default string
    # 任意の既定値は保たれる
    assert validated["twitch_client_id"] == DEFAULT_CONFIG["twitch_client_id"]
    assert changed is True
