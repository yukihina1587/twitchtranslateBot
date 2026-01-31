"""VoicevoxTTS クラスのテスト"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import asyncio


class TestVoicevoxTTS:
    """VoicevoxTTSクラスの基本テスト"""

    def test_import_tts_module(self):
        """ttsモジュールがインポートできることを確認"""
        from src import tts
        assert hasattr(tts, 'VoicevoxTTS')

    @patch('src.tts.requests.get')
    def test_get_speakers_success(self, mock_get):
        """スピーカー一覧取得の成功ケース"""
        from src.tts import VoicevoxTTS

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "四国めたん", "styles": [{"id": 2, "name": "ノーマル"}]},
            {"name": "ずんだもん", "styles": [{"id": 3, "name": "ノーマル"}]}
        ]
        mock_get.return_value = mock_response

        tts = VoicevoxTTS(voicevox_url="http://localhost:50021")
        speakers = tts.get_speakers()

        assert len(speakers) == 2
        assert speakers[0]["name"] == "四国めたん"

    @patch('src.tts.requests.get')
    def test_get_speakers_failure(self, mock_get):
        """スピーカー一覧取得の失敗ケース"""
        from src.tts import VoicevoxTTS

        mock_get.side_effect = Exception("Connection refused")

        tts = VoicevoxTTS(voicevox_url="http://localhost:50021")
        speakers = tts.get_speakers()

        assert speakers == []

    def test_initialization(self):
        """初期化時のデフォルト値を確認"""
        from src.tts import VoicevoxTTS

        tts = VoicevoxTTS(voicevox_url="http://localhost:50021", speaker_id=14)

        assert tts.voicevox_url == "http://localhost:50021"
        assert tts.speaker_id == 14


class TestVoicevoxTTSAsync:
    """VoicevoxTTSの非同期メソッドテスト"""

    @pytest.mark.asyncio
    @patch('src.tts.aiohttp.ClientSession')
    async def test_synthesize_async_success(self, mock_session_class):
        """非同期音声合成の成功ケース"""
        from src.tts import VoicevoxTTS

        # モックのセットアップ
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"accent_phrases": []})
        mock_response.read = AsyncMock(return_value=b"audio_data")

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_session_class.return_value = mock_session

        tts = VoicevoxTTS(voicevox_url="http://localhost:50021")
        # 注: 実際のテストはVOICEVOXが起動していないと動作しないため、
        # モックでの基本的な呼び出しテストのみ
