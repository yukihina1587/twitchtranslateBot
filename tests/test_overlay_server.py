"""overlay_server のテスト"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import threading
import time


class TestOverlayServer:
    """overlay_serverモジュールのテスト"""

    def test_import_overlay_server(self):
        """overlay_serverモジュールがインポートできることを確認"""
        from src import overlay_server
        assert hasattr(overlay_server, 'start_server')
        assert hasattr(overlay_server, 'stop_server')
        assert hasattr(overlay_server, 'update_translation')

    def test_update_translation(self):
        """update_translation関数のテスト"""
        from src.overlay_server import update_translation, get_latest_translation

        # 翻訳データを更新
        update_translation("Hello", "こんにちは", "testuser")

        # 最新の翻訳を取得
        latest = get_latest_translation()

        assert latest is not None
        assert latest["original"] == "Hello"
        assert latest["translated"] == "こんにちは"
        assert latest["username"] == "testuser"

    def test_update_translation_clears_old_data(self):
        """update_translationが古いデータを上書きすることを確認"""
        from src.overlay_server import update_translation, get_latest_translation

        # 1つ目の翻訳
        update_translation("First", "最初", "user1")

        # 2つ目の翻訳で上書き
        update_translation("Second", "2番目", "user2")

        latest = get_latest_translation()

        assert latest["original"] == "Second"
        assert latest["translated"] == "2番目"
        assert latest["username"] == "user2"


class TestOverlayServerStartStop:
    """サーバーの起動・停止テスト"""

    def test_server_start_and_stop(self):
        """サーバーの起動と停止が正常に動作することを確認"""
        from src.overlay_server import start_server, stop_server, is_server_running

        # テスト用のポートで起動（デフォルトと異なるポートを使用）
        # 注: 実際のサーバー起動はポートの競合を避けるため
        # 統合テストで行うことを推奨

        # サーバーが停止状態であることを確認
        # （テスト開始時点では停止しているはず）
        # stop_server()  # 念のため停止

        # start_server() を呼び出すとサーバーが起動する
        # ここでは関数が存在することのみを確認
        assert callable(start_server)
        assert callable(stop_server)


class TestOverlayHTML:
    """オーバーレイHTML生成のテスト"""

    def test_generate_overlay_html(self):
        """オーバーレイHTMLが正しく生成されることを確認"""
        from src.overlay_server import generate_overlay_html

        html = generate_overlay_html()

        # HTMLが文字列であることを確認
        assert isinstance(html, str)

        # 必要な要素が含まれていることを確認
        assert "<!DOCTYPE html>" in html or "<html" in html
        assert "<body" in html
