"""overlay_server のテスト"""
import pytest
from unittest.mock import Mock, patch


class TestOverlayServer:
    """overlay_serverモジュールのテスト"""

    def test_import_overlay_server(self):
        """overlay_serverモジュールがインポートできることを確認"""
        from src import overlay_server
        assert hasattr(overlay_server, 'start_server')
        assert hasattr(overlay_server, 'stop_server')
        assert hasattr(overlay_server, 'update_translation')

    def test_update_translation_exists(self):
        """update_translation関数が呼び出し可能であることを確認"""
        from src.overlay_server import update_translation
        assert callable(update_translation)

    def test_start_stop_server_exists(self):
        """start_server/stop_server関数が呼び出し可能であることを確認"""
        from src.overlay_server import start_server, stop_server
        assert callable(start_server)
        assert callable(stop_server)

    def test_run_server_thread_exists(self):
        """run_server_thread関数が呼び出し可能であることを確認"""
        from src.overlay_server import run_server_thread
        assert callable(run_server_thread)
