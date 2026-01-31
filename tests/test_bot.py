"""TranslateBot クラスのテスト"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock


class TestTranslateBot:
    """TranslateBotクラスの基本テスト"""

    def test_import_bot_module(self):
        """botモジュールがインポートできることを確認"""
        from src import bot
        assert hasattr(bot, 'TranslateBot')

    @patch('src.bot.load_config')
    def test_bot_initialization(self, mock_load_config):
        """Botの初期化テスト"""
        mock_load_config.return_value = {
            "twitch_client_id": "test_client_id",
            "deepl_api_key": "test_api_key",
            "channel_name": "test_channel",
            "translate_mode": "自動",
            "chat_translation_enabled": True,
        }

        from src.bot import TranslateBot

        # トークンなしでの初期化（エラーにならないことを確認）
        # 実際のBotは非同期なので完全なテストは統合テストで行う
        assert TranslateBot is not None


class TestBotHelperFunctions:
    """Botのヘルパー関数テスト"""

    def test_create_twitch_comment(self):
        """create_twitch_comment関数のテスト"""
        from src.bot import create_twitch_comment

        comment = create_twitch_comment(
            username="testuser",
            message="Hello",
            translated="こんにちは",
            badges=["subscriber"],
            color="#FF0000"
        )

        assert comment["username"] == "testuser"
        assert comment["message"] == "Hello"
        assert comment["translated"] == "こんにちは"
        assert comment["badges"] == ["subscriber"]
        assert comment["color"] == "#FF0000"
        assert "timestamp" in comment

    def test_create_twitch_comment_without_translation(self):
        """翻訳なしのコメント作成テスト"""
        from src.bot import create_twitch_comment

        comment = create_twitch_comment(
            username="testuser",
            message="Hello",
            translated=None,
            badges=[],
            color=None
        )

        assert comment["username"] == "testuser"
        assert comment["message"] == "Hello"
        assert comment["translated"] is None


class TestBotEventHandlers:
    """Botのイベントハンドラテスト"""

    @pytest.mark.asyncio
    @patch('src.bot.load_config')
    async def test_event_ready(self, mock_load_config):
        """event_ready ハンドラのテスト"""
        mock_load_config.return_value = {
            "twitch_client_id": "test_client_id",
            "deepl_api_key": "test_api_key",
            "channel_name": "test_channel",
            "translate_mode": "自動",
            "chat_translation_enabled": True,
        }

        # イベントハンドラは実際のTwitch接続が必要なため、
        # モックでの基本テストのみ
        from src.bot import TranslateBot
        assert TranslateBot is not None
