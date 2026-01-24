import speech_recognition as sr
from src.translator import translate_text_sync, should_filter, apply_translation_dictionary
from src.logger import logger
from src.config import check_gladia_usage, update_gladia_usage
import threading
import time
import pyaudio
import asyncio
import json
import base64
import requests

# Gladia関連のインポート（websocketsが利用可能かチェック）
try:
    import websockets
    GLADIA_AVAILABLE = True
except ImportError:
    GLADIA_AVAILABLE = False
    logger.warning("websockets not installed. Only Google SR will be available.")

class VoiceTranslator:
    def __init__(self, mode_getter, api_key_getter, callback, config_data=None):
        """
        mode_getter: Function returning current translation mode ('英→日', etc.)
        api_key_getter: Function returning DeepL API Key
        callback: Function(text, translated_text) to handle result
        config_data: Configuration dictionary (for Gladia settings)
        """
        self.r = sr.Recognizer()
        # マイクの初期化は起動時に行うと固まることがあるため遅延させる
        self.mic = None
        self.mode_getter = mode_getter
        self.api_key_getter = api_key_getter
        self.callback = callback
        self.config_data = config_data or {}
        self.stop_listening = None

        # Gladia関連
        self.gladia_client = None
        self.gladia_thread = None
        self.gladia_running = False
        self.audio_start_time = None  # 使用時間追跡用

    def start(self):
        """音声認識を開始"""
        logger.info("VoiceTranslator.start() called")
        # プロバイダーを決定（Gladia使用可能かチェック）
        provider = self.config_data.get("stt_provider", "google")
        gladia_api_key = self.config_data.get("gladia_api_key", "")

        logger.info(f"Voice recognition provider: {provider}")
        logger.info(f"Gladia API key configured: {bool(gladia_api_key)}")
        logger.info(f"Gladia SDK available: {GLADIA_AVAILABLE}")

        # Gladiaが選択されているが、APIキーがない、またはSDKがインストールされていない場合はGoogle SRにフォールバック
        if provider == "gladia":
            if not GLADIA_AVAILABLE:
                logger.warning("Gladia SDK not available. Falling back to Google SR.")
                provider = "google"
            elif not gladia_api_key:
                logger.warning("Gladia API key not configured. Falling back to Google SR.")
                provider = "google"
            elif not check_gladia_usage(self.config_data):
                logger.warning("Gladia usage limit reached. Using Google SR.")
                provider = "google"

        try:
            if provider == "gladia":
                return self._start_gladia()
            else:
                return self._start_google_sr()
        except Exception as e:
            logger.error(f"Failed to start voice recognition: {e}", exc_info=True)
            return False

    def _start_google_sr(self):
        """Google Speech Recognitionを開始"""
        try:
            logger.info("Starting Google Speech Recognition...")
            # マイクの初期化が重い環境があるためここで遅延初期化する
            if self.mic is None:
                try:
                    self.mic = sr.Microphone()
                except OSError as e:
                    logger.error(f"Failed to access microphone: {e}", exc_info=True)
                    return False
                except Exception as mic_err:
                    logger.error(f"Failed to initialize microphone: {mic_err}", exc_info=True)
                    return False

            logger.info("Adjusting for ambient noise...")
            with self.mic as source:
                self.r.adjust_for_ambient_noise(source, duration=1)

            logger.info("Starting background listening...")
            # phrase_time_limitを付けて定期的に結果を返すようにする
            self.stop_listening = self.r.listen_in_background(
                self.mic, self.process_audio, phrase_time_limit=6
            )
            logger.info("Google SR started successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to start Google SR: {e}", exc_info=True)
            return False

    def _start_gladia(self):
        """Gladiaリアルタイム音声認識を開始"""
        if not GLADIA_AVAILABLE:
            logger.error("Gladia SDK is not available.")
            return False

        try:
            logger.info("Starting Gladia real-time transcription...")
            gladia_api_key = self.config_data.get("gladia_api_key", "")

            if not gladia_api_key:
                logger.error("Gladia API key is required but not provided.")
                return False

            # 別スレッドでGladiaを実行
            self.gladia_running = True
            self.audio_start_time = time.time()
            self.gladia_thread = threading.Thread(target=self._run_gladia_stream, daemon=True)
            self.gladia_thread.start()

            logger.info("Gladia started successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to start Gladia: {e}", exc_info=True)
            return False

    def _run_gladia_stream(self):
        """Gladiaでの音声ストリーミング処理（別スレッドで実行）"""
        p = None
        stream = None
        try:
            logger.info("Gladia: Starting _run_gladia_stream")
            # PyAudioでマイク入力を取得
            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000

            logger.info("Gladia: Initializing PyAudio")
            p = pyaudio.PyAudio()
            logger.info("Gladia: Opening microphone stream")
            stream = p.open(format=FORMAT,
                          channels=CHANNELS,
                          rate=RATE,
                          input=True,
                          frames_per_buffer=CHUNK)

            logger.info("Gladia: Microphone stream opened.")

            # 言語設定
            mode = self.mode_getter()
            language = 'ja' if mode in ['日→英', '自動'] else 'en'

            # Gladia APIの実装
            # 注: 実際のGladia SDKの使用方法に応じて調整が必要
            # ここでは簡略化した例を示します
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(self._gladia_websocket_stream(stream, language))
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Gladia stream error: {e}", exc_info=True)
        finally:
            # PyAudioリソースの確実な解放
            if stream is not None:
                try:
                    logger.info("Gladia: Closing audio stream...")
                    stream.stop_stream()
                    stream.close()
                    logger.info("Gladia: Audio stream closed.")
                except Exception as e:
                    logger.error(f"Failed to close audio stream: {e}", exc_info=True)

            if p is not None:
                try:
                    logger.info("Gladia: Terminating PyAudio...")
                    p.terminate()
                    logger.info("Gladia: PyAudio terminated.")
                except Exception as e:
                    logger.error(f"Failed to terminate PyAudio: {e}", exc_info=True)

            self.gladia_running = False
            # 使用時間を記録
            if self.audio_start_time:
                elapsed = time.time() - self.audio_start_time
                update_gladia_usage(self.config_data, int(elapsed))
                self.audio_start_time = None

    async def _gladia_websocket_stream(self, audio_stream, language):
        """Gladia WebSocketストリーミング（非同期）"""
        try:
            gladia_api_key = self.config_data.get("gladia_api_key", "")

            # Step 1: Initialize live session via POST request
            logger.info(f"Gladia: Initializing live session (language={language})")

            init_url = "https://api.gladia.io/v2/live"
            headers = {
                "X-Gladia-Key": gladia_api_key,
                "Content-Type": "application/json"
            }

            config = {
                "encoding": "wav/pcm",
                "sample_rate": 16000,
                "bit_depth": 16,
                "channels": 1,
                "language_config": {
                    "languages": [language],
                    "code_switching": False
                },
                "messages_config": {
                    "receive_partial_transcripts": False,
                    "receive_final_transcripts": True
                }
            }

            response = requests.post(init_url, headers=headers, json=config, timeout=10)
            response.raise_for_status()

            session_data = response.json()
            ws_url = session_data.get("url")
            session_id = session_data.get("id")

            if not ws_url:
                logger.error("Gladia: Failed to get WebSocket URL from response")
                return

            logger.info(f"Gladia: Session initialized (id={session_id})")

            # Step 2: Connect to WebSocket
            async with websockets.connect(ws_url) as ws:
                logger.info("Gladia: WebSocket connected, starting audio stream")

                # Create tasks for sending and receiving
                send_task = asyncio.create_task(self._gladia_send_audio(ws, audio_stream))
                receive_task = asyncio.create_task(self._gladia_receive_transcripts(ws))

                # Wait for both tasks to complete
                await asyncio.gather(send_task, receive_task)

                logger.info("Gladia: WebSocket session ended")

        except requests.exceptions.RequestException as e:
            logger.error(f"Gladia session initialization error: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Gladia WebSocket error: {e}", exc_info=True)

    async def _gladia_send_audio(self, ws, audio_stream):
        """音声データをGladiaに送信（非同期）"""
        try:
            CHUNK = 1024
            logger.info("Gladia: Starting audio transmission")
            chunk_count = 0

            while self.gladia_running:
                # 音声データを読み取り
                data = audio_stream.read(CHUNK, exception_on_overflow=False)

                # base64エンコード
                chunk_b64 = base64.b64encode(data).decode("utf-8")

                # JSONメッセージを作成して送信
                message = json.dumps({
                    "type": "audio_chunk",
                    "data": {
                        "chunk": chunk_b64
                    }
                })

                await ws.send(message)
                chunk_count += 1

                # 5秒ごとにログ出力（デバッグ用）
                if chunk_count % 500 == 0:
                    logger.info(f"Gladia: Sent {chunk_count} audio chunks")

                await asyncio.sleep(0.01)  # 少し待機

            # 録音停止メッセージを送信
            logger.info("Gladia: Sending stop_recording message")
            stop_message = json.dumps({"type": "stop_recording"})
            await ws.send(stop_message)

        except Exception as e:
            logger.error(f"Gladia audio send error: {e}", exc_info=True)

    async def _gladia_receive_transcripts(self, ws):
        """Gladiaから文字起こし結果を受信（非同期）"""
        try:
            logger.info("Gladia: Starting transcript reception")
            message_count = 0

            async for message in ws:
                if not self.gladia_running:
                    break

                message_count += 1

                try:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "transcript":
                        # 文字起こし結果を処理
                        transcript_data = data.get("data", {})
                        is_final = transcript_data.get("is_final", False)
                        utterance = transcript_data.get("utterance", {})
                        text = utterance.get("text", "")

                        logger.info(f"Gladia: Transcript received, is_final={is_final}, text='{text}'")

                        if is_final and text:
                            logger.info(f"Gladia final transcript: {text}")
                            self._process_gladia_result(text)
                        elif text:
                            # 部分的な文字起こしもログに記録
                            logger.info(f"Gladia partial transcript: {text}")

                    elif msg_type == "error":
                        error_msg = data.get("message", "Unknown error")
                        logger.error(f"Gladia error: {error_msg}")

                    # その他のメッセージタイプはログに記録しない（audio_chunkなど）

                except json.JSONDecodeError as e:
                    logger.error(f"Gladia: Failed to parse message: {e}, raw message: {message[:200]}")

        except Exception as e:
            logger.error(f"Gladia transcript receive error: {e}", exc_info=True)

    def _process_gladia_result(self, text):
        """Gladiaの文字起こし結果を処理"""
        try:
            mode = self.mode_getter()
            logger.info(f"Gladia recognized: {text}")

            # 翻訳
            api_key = self.api_key_getter()
            if api_key:
                # 自動モードの場合はそのままtranslatorに渡して判定させる
                translated = translate_text_sync(text, mode, api_key)
            else:
                translated = "(No API Key)"

            # コールバック
            if self.callback:
                self.callback(text, translated)

        except Exception as e:
            logger.error(f"Gladia result processing error: {e}", exc_info=True)

    def stop(self):
        """音声認識を停止し、全てのリソースを解放"""
        # Gladia停止
        if self.gladia_running:
            logger.info("Stopping Gladia...")
            self.gladia_running = False
            if self.gladia_thread:
                self.gladia_thread.join(timeout=3)
            logger.info("Stopped Gladia listening.")

        # Google SR停止
        if self.stop_listening:
            logger.info("Stopping Google SR background listening...")
            self.stop_listening(wait_for_stop=False)
            self.stop_listening = None
            logger.info("Stopped Google SR listening.")

        # マイクリソースの解放
        if self.mic is not None:
            try:
                # マイクのストリームを閉じる
                logger.info("Releasing microphone resource...")
                self.mic = None
                logger.info("Microphone resource released.")
            except Exception as e:
                logger.error(f"Failed to release microphone: {e}", exc_info=True)

    def process_audio(self, recognizer, audio):
        mode = self.mode_getter()

        # Determine Recognition Language based on Translation Mode
        # If translating JA -> EN, we recognize JA.
        # If translating EN -> JA, we recognize EN.
        # If Auto, default to JA (Assuming Japanese streamer).
        recog_lang = 'ja-JP'
        if mode == '英→日':
            recog_lang = 'en-US'
        elif mode == '日→英':
            recog_lang = 'ja-JP'

        try:
            # Recognize
            text = recognizer.recognize_google(audio, language=recog_lang)
            logger.info(f"Recognized ({recog_lang}): {text}")

            # Translate
            api_key = self.api_key_getter()
            if api_key:
                # 自動モードの場合はそのままtranslatorに渡して判定させる
                translated = translate_text_sync(text, mode, api_key)
            else:
                translated = "(No API Key)"

            # Callback
            if self.callback:
                self.callback(text, translated)

        except sr.UnknownValueError:
            # Speech was unintelligible
            logger.debug("Speech was unintelligible")
        except sr.RequestError as e:
            logger.error(f"Google API Error: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Voice recognition error: {e}", exc_info=True)
