import asyncio
import aiohttp
import json
from twitchio.ext import commands
from src.translator import translate_text, should_filter, apply_translation_dictionary, get_stats
from src.logger import logger
from src.tts import get_tts_instance, is_japanese
from src.participant_tracker import get_tracker
from src.comment_data import create_twitch_comment
from src.config import load_config


class EventSubHandler:
    """Twitch EventSub WebSocketハンドラー（フォロー検知用）"""

    EVENTSUB_URL = "wss://eventsub.wss.twitch.tv/ws"

    def __init__(self, token: str, client_id: str, channel_name: str, on_follow_callback):
        # oauth:プレフィックスを除去
        self.token = token[6:] if token.startswith("oauth:") else token
        self.client_id = client_id
        self.channel_name = channel_name.lower()
        self.on_follow = on_follow_callback
        self._running = False
        self._session_id = None
        self._broadcaster_id = None
        self._moderator_id = None
        self._ws = None
        self._task = None

    async def start(self):
        """EventSub接続を開始"""
        if self._running:
            return

        self._running = True

        # ユーザーIDを取得
        try:
            self._broadcaster_id = await self._get_user_id(self.channel_name)
            if not self._broadcaster_id:
                logger.error(f"Failed to get broadcaster ID for {self.channel_name}")
                return

            # モデレーターID（BOTのID）を取得
            self._moderator_id = await self._get_token_user_id()
            if not self._moderator_id:
                logger.error("Failed to get moderator (bot) user ID")
                return

            logger.info(f"EventSub: broadcaster_id={self._broadcaster_id}, moderator_id={self._moderator_id}")
        except Exception as e:
            logger.error(f"EventSub setup failed: {e}", exc_info=True)
            return

        # WebSocket接続を開始
        self._task = asyncio.create_task(self._run_websocket())

    async def stop(self):
        """EventSub接続を停止"""
        self._running = False
        if self._ws:
            await self._ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _get_user_id(self, login: str) -> str | None:
        """ユーザー名からユーザーIDを取得"""
        url = f"https://api.twitch.tv/helix/users?login={login}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Client-Id": self.client_id,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("data"):
                            return data["data"][0]["id"]
        except Exception as e:
            logger.error(f"Failed to get user ID for {login}: {e}")
        return None

    async def _get_token_user_id(self) -> str | None:
        """トークンの所有者のユーザーIDを取得"""
        url = "https://api.twitch.tv/helix/users"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Client-Id": self.client_id,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("data"):
                            return data["data"][0]["id"]
        except Exception as e:
            logger.error(f"Failed to get token user ID: {e}")
        return None

    async def _run_websocket(self):
        """WebSocket接続を維持"""
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(self.EVENTSUB_URL) as ws:
                        self._ws = ws
                        logger.info("EventSub WebSocket connected")

                        async for msg in ws:
                            if not self._running:
                                break

                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await self._handle_message(msg.data)
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error(f"EventSub WebSocket error: {ws.exception()}")
                                break
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                logger.info("EventSub WebSocket closed")
                                break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"EventSub WebSocket error: {e}", exc_info=True)
                if self._running:
                    await asyncio.sleep(5)  # 再接続待機

    async def _handle_message(self, data: str):
        """WebSocketメッセージを処理"""
        try:
            message = json.loads(data)
            msg_type = message.get("metadata", {}).get("message_type")

            if msg_type == "session_welcome":
                self._session_id = message["payload"]["session"]["id"]
                logger.info(f"EventSub session established: {self._session_id}")
                # フォローイベントを購読
                await self._subscribe_to_follows()

            elif msg_type == "session_keepalive":
                pass  # キープアライブ

            elif msg_type == "notification":
                await self._handle_notification(message)

            elif msg_type == "session_reconnect":
                # 再接続が必要
                reconnect_url = message["payload"]["session"]["reconnect_url"]
                logger.info(f"EventSub reconnect requested: {reconnect_url}")

        except Exception as e:
            logger.error(f"Failed to handle EventSub message: {e}", exc_info=True)

    async def _subscribe_to_follows(self):
        """フォローイベントを購読"""
        url = "https://api.twitch.tv/helix/eventsub/subscriptions"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Client-Id": self.client_id,
            "Content-Type": "application/json",
        }
        body = {
            "type": "channel.follow",
            "version": "2",
            "condition": {
                "broadcaster_user_id": self._broadcaster_id,
                "moderator_user_id": self._moderator_id,
            },
            "transport": {
                "method": "websocket",
                "session_id": self._session_id,
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=body) as resp:
                    if resp.status in (200, 202):
                        logger.info("EventSub: Subscribed to channel.follow")
                    else:
                        error = await resp.text()
                        logger.error(f"EventSub subscription failed: {resp.status} - {error}")
        except Exception as e:
            logger.error(f"Failed to subscribe to follows: {e}", exc_info=True)

    async def _handle_notification(self, message: dict):
        """通知イベントを処理"""
        subscription_type = message.get("payload", {}).get("subscription", {}).get("type")

        if subscription_type == "channel.follow":
            event = message["payload"]["event"]
            follower_name = event.get("user_name", "誰か")
            logger.info(f"New follower: {follower_name}")

            if self.on_follow:
                self.on_follow(follower_name)

class TranslateBot(commands.Bot):
    def __init__(self, token, channel, get_lang_mode, gui_ref, deepl_api_key,
                 tts_enabled_getter=None, tts_include_name_getter=None, client_id=None):
        super().__init__(token=token, prefix='!', initial_channels=[channel])
        self.token = token
        self.channel_name = channel
        self.client_id = client_id
        self.get_lang_mode = get_lang_mode
        self.gui = gui_ref
        self.deepl_api_key = deepl_api_key
        self.tts_enabled_getter = tts_enabled_getter or (lambda: False)
        self.tts_include_name_getter = tts_include_name_getter or (lambda: False)
        self.tts = get_tts_instance()
        self.tracker = get_tracker()
        # 実行中のイベントループは event_ready でセットする
        self._running_loop = None
        # 処理済みメッセージIDを記録（重複防止）
        self._processed_message_ids = set()
        self._max_processed_ids = 1000  # メモリ制限
        # 停止フラグ
        self._stopped = False
        # EventSub handler（フォロー検知用）
        self._eventsub_handler = None

    async def event_ready(self):
        # GUI側から run_coroutine_threadsafe で送信できるよう、実際に動いているループを保持
        try:
            self._running_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._running_loop = None
        logger.info(f"Bot logged in as {self.nick}")

        # EventSub接続を開始（フォロー検知）
        if self.client_id:
            try:
                self._eventsub_handler = EventSubHandler(
                    token=self.token,
                    client_id=self.client_id,
                    channel_name=self.channel_name,
                    on_follow_callback=self._on_follow_event
                )
                await self._eventsub_handler.start()
                logger.info("EventSub handler started for follow detection")
            except Exception as e:
                logger.error(f"Failed to start EventSub handler: {e}", exc_info=True)
        else:
            logger.warning("client_id not provided, follow detection disabled")

    def _on_follow_event(self, follower_name: str):
        """フォローイベントのコールバック"""
        follow_msg = f"{follower_name} さんがフォローしました"
        self._notify_special_event(follow_msg, event_type="follow")

    async def event_message(self, message):
        # 停止済みの場合は処理しない
        if self._stopped:
            return

        # message.authorがNoneの場合は処理しない（BOTのエコーメッセージなど）
        if message.author is None:
            logger.debug("Skipped: message.author is None")
            return

        # メッセージIDによる重複チェック（BOT再起動時の二重処理防止）
        msg_id = message.tags.get('id') if message.tags else None
        if msg_id:
            if msg_id in self._processed_message_ids:
                logger.debug(f"Duplicate message skipped: {msg_id}")
                return
            self._processed_message_ids.add(msg_id)
            # メモリ制限: 古いIDを削除
            if len(self._processed_message_ids) > self._max_processed_ids:
                # セットの最初の半分を削除
                to_remove = list(self._processed_message_ids)[:self._max_processed_ids // 2]
                for old_id in to_remove:
                    self._processed_message_ids.discard(old_id)

        # BOTが送信した翻訳結果をスキップ（ゼロ幅スペースで判定）
        if '\u200B' in message.content:
            logger.debug(f"Skipped (zero-width space): {message.author.name}")
            return

        # BOTが送信したエコーメッセージのみスキップ
        # ※配信者アカウント＝BOTアカウントの場合、配信者の手入力は翻訳対象
        # echoフラグ: BOTが送信→Twitchからエコーバック→True
        # 配信者の手入力: echo=False（通常メッセージとして扱われる）
        is_bot_echo = message.echo and self.nick and message.author.name.lower() == self.nick.lower()
        if is_bot_echo:
            logger.debug(f"Skipped (bot echo): {message.author.name}")
            return

        # 配信者の手入力（echo=False, 名前一致）は翻訳対象として処理を継続
        if self.nick and message.author.name.lower() == self.nick.lower():
            logger.debug(f"Processing broadcaster's own message: {message.author.name}")

        original_content = message.content
        content = message.content
        if message.tags:
            # Emote ranges are stored in 'emotes' tag as 'id:start-end,start-end/id:start-end'
            # We want to wrap these ranges in <k>...</k> tags for DeepL xml handling
            
            # Create a list of (start, end, type) tuples to handle replacements
            replacements = []
            
            # Handle standard Twitch emotes
            if message.tags.get('emotes'):
                emote_str = message.tags['emotes']
                # format: id:start-end,start-end/id:start-end
                for emote_group in emote_str.split('/'):
                    if ':' in emote_group:
                        _, positions = emote_group.split(':')
                        for pos in positions.split(','):
                            start, end = map(int, pos.split('-'))
                            replacements.append((start, end + 1, 'emote'))

            # Sort replacements by start index in reverse order to avoid offsetting indices
            replacements.sort(key=lambda x: x[0], reverse=True)
            
            # Apply replacements
            temp_content = list(content)
            for start, end, _ in replacements:
                # Wrap emote in <k> tag
                # Need to handle potential overlap or adjacent emotes if any (though twitch usually handles this)
                original = "".join(temp_content[start:end])
                temp_content[start:end] = list(f"<k>{original}</k>")
            
            content = "".join(temp_content)

        # チャット発言者を参加者として記録（キーワード検知のみ）
        participant_name = getattr(message.author, "display_name", None) or message.author.name
        added_by_keyword = self.tracker.check_message(participant_name, message.content)

        # 参加キーワードを検知した場合は専用メッセージを表示・読み上げ
        if added_by_keyword:
            join_msg = f"{participant_name}さんが参加希望登録しました。"
            # コメントログに追加するため、専用CommentDataを生成
            join_comment = create_twitch_comment(
                username=message.author.name,
                message=join_msg,
                tags=message.tags,
                display_name=participant_name,
                translated=None
            )
            self.gui.on_comment_received(join_comment)
            self.gui.log_message(join_msg, log_type="system")

            # 参加者リストを即時送信
            try:
                self.gui.send_participant_list_to_chat()
            except Exception as e:
                logger.error(f"Failed to auto-send participant list: {e}", exc_info=True)

            # TTSで読み上げ（設定ONの場合）
            if self.tts_enabled_getter():
                speak_text = join_msg
                try:
                    self.tts.speak(speak_text)
                    logger.debug(f"TTS speak (join): {speak_text[:30]}...")
                except Exception as e:
                    logger.error(f"TTS speak error: {e}", exc_info=True)
            return

        # ここから通常の翻訳処理
        # チャット翻訳が無効の場合は翻訳をスキップ
        config = load_config()
        if not config.get("chat_translation_enabled", False):
            # 翻訳せずに原文のみ表示
            comment = create_twitch_comment(
                username=message.author.name,
                message=message.content,
                tags=message.tags,
                display_name=message.author.display_name if hasattr(message.author, 'display_name') else message.author.name,
                translated=None
            )
            self.gui.on_comment_received(comment)

            # TTS: チャット読み上げ（翻訳無効時も原文を読み上げる）
            if self.tts_enabled_getter():
                speak_text = message.content
                if self.tts_include_name_getter():
                    display_name = message.author.display_name if hasattr(message.author, 'display_name') else message.author.name
                    speak_text = f"{display_name}さん、{speak_text}"
                if speak_text and speak_text.strip():
                    try:
                        self.tts.speak(speak_text)
                        logger.debug(f"TTS speak called (no translation): {speak_text[:30]}...")
                    except Exception as e:
                        logger.error(f"TTS speak error: {e}", exc_info=True)
            return

        lang_mode = self.get_lang_mode()
        translated = await translate_text(content, lang_mode, self.deepl_api_key)

        # フィルタでスキップされた場合
        if translated == "":
            self.gui.log_message("🚫 翻訳フィルタによりスキップしました", log_type="system")
            # コメントは表示する
            comment = create_twitch_comment(
                username=message.author.name,
                message=message.content,
                tags=message.tags,
                display_name=message.author.display_name if hasattr(message.author, 'display_name') else message.author.name,
                translated=None
            )
            self.gui.on_comment_received(comment)
            return

        # Remove <k> tags from translated text for display
        if translated:
            translated = translated.replace("<k>", "").replace("</k>", "")

        # チャットに翻訳結果を送信（翻訳がある場合のみ）
        if translated and translated != message.content:
            await message.channel.send(f"[Chat] {translated}" + '\u200B')

        # CommentDataオブジェクトを作成（全てのコメントを表示）
        comment = create_twitch_comment(
            username=message.author.name,
            message=message.content,
            tags=message.tags,
            display_name=message.author.display_name if hasattr(message.author, 'display_name') else message.author.name,
            translated=translated if translated and translated != message.content else None
        )

        # GUIにコメントデータを渡す（全てのコメントをタイル表示）
        self.gui.on_comment_received(comment)

        # TTS: チャット読み上げ
        if self.tts_enabled_getter():
            # デフォルトは原文
            speak_text = message.content

            # 翻訳があり、かつ翻訳結果が日本語を含むなら、翻訳結果を読み上げる
            # (英語コメント -> 日本語翻訳 のケース)
            if translated and translated != message.content:
                if is_japanese(translated):
                    speak_text = translated

            # 名前を読み上げる設定があれば、名前も追加
            if self.tts_include_name_getter():
                display_name = message.author.display_name if hasattr(message.author, 'display_name') else message.author.name
                speak_text = f"{display_name}さん、{speak_text}"

            # TTSに渡す（空でないことを確認）
            if speak_text and speak_text.strip():
                try:
                    self.tts.speak(speak_text)
                    logger.debug(f"TTS speak called: {speak_text[:30]}...")
                except Exception as e:
                    logger.error(f"TTS speak error: {e}", exc_info=True)

        # ビッツ（チア）イベント検知と通知
        bits = 0
        if message.tags and message.tags.get("bits"):
            try:
                bits = int(message.tags.get("bits", "0"))
            except ValueError:
                bits = 0

        if bits > 0:
            display_name = None
            if hasattr(message, "author") and message.author:
                display_name = getattr(message.author, "display_name", None) or getattr(message.author, "name", None)
            display_name = display_name or "匿名"

            bits_msg = f"{display_name} が {bits} ビッツを投げました"
            if original_content:
                bits_msg += f"「{original_content}」"

            self._notify_special_event(bits_msg, event_type="bits")

    async def event_usernotice(self, message):
        """サブスクやギフトなどのUSERNOTICEイベントを処理"""
        msg_id = message.tags.get("msg-id") if message.tags else None

        # 自分でサブスク登録（sub, resub, primepaidupgrade）
        self_sub_types = {"sub", "resub", "primepaidupgrade"}
        # ギフトサブ関連
        gift_sub_types = {
            "subgift",
            "anonsubgift",
            "submysterygift",
            "anonsubmysterygift",
            "giftpaidupgrade",
            "rewardgift",
            "communitypayforward",
        }
        # その他（bitsbadgetierなど）
        other_sub_types = {"bitsbadgetier"}

        all_sub_related = self_sub_types | gift_sub_types | other_sub_types
        if msg_id not in all_sub_related:
            return

        display_name = None
        if hasattr(message, "author") and message.author:
            display_name = getattr(message.author, "display_name", None) or getattr(message.author, "name", None)
        display_name = display_name or "匿名"

        system_msg = ""
        if message.tags and message.tags.get("system-msg"):
            system_msg = self._decode_irc_tag(message.tags.get("system-msg"))

        # イベントタイプを判別
        if msg_id in self_sub_types:
            fallback_msg = f"{display_name} がサブスク登録しました"
            event_type = "subscription"
        elif msg_id in gift_sub_types:
            fallback_msg = f"{display_name} がギフトサブを贈りました"
            event_type = "gift_sub"
        else:
            fallback_msg = f"{display_name} がサブスクしました"
            event_type = "subscription"

        event_msg = system_msg if system_msg else fallback_msg
        self._notify_special_event(event_msg, event_type=event_type)

    def _notify_special_event(self, message: str, event_type: str = "other"):
        """GUIの特別イベントログに通知"""
        if hasattr(self, "gui") and self.gui and hasattr(self.gui, "log_special_event"):
            try:
                self.gui.log_special_event(message, event_type)
            except Exception as e:
                logger.error(f"Failed to notify special event: {e}", exc_info=True)

    @staticmethod
    def _decode_irc_tag(value: str) -> str:
        """Twitch IRCタグのエスケープを解除"""
        if not value:
            return ""
        replacements = {
            r"\s": " ",
            r"\:": ";",
            r"\\": "\\",
            r"\r": "\r",
            r"\n": "\n",
        }
        result = value
        for k, v in replacements.items():
            result = result.replace(k, v)
        return result

    async def send_participant_list(self):
        """参加者リストをチャットに送信"""
        if not self.tracker or not hasattr(self, '_connection') or not self._connection:
            logger.warning("BOTが接続されていないため、参加者リストを送信できません")
            return False

        participants = self.tracker.get_participant_names()

        if not participants:
            message = "【待機参加者リスト】参加者はいません"
        else:
            participant_str = "→".join(participants)
            message = f"【待機参加者リスト】{participant_str}"

        try:
            # 最初のチャンネルに送信
            if self._connection and self._connection.connected_channels:
                channel = self._connection.connected_channels[0]
                await channel.send(message)
                logger.info(f"参加者リストを送信: {message}")
                return True
        except Exception as e:
            logger.error(f"参加者リスト送信エラー: {e}", exc_info=True)
            return False

    def stop(self):
        """
        BOTを安全に停止する
        """
        logger.info("Bot.stop() called")

        # 停止フラグを設定（二重処理防止）
        self._stopped = True

        loop = self._running_loop

        # EventSubハンドラーを停止
        if self._eventsub_handler and loop and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    self._eventsub_handler.stop(),
                    loop
                )
                logger.info("EventSub handler stop requested")
            except Exception as e:
                logger.warning(f"Exception stopping EventSub handler: {e}")
            self._eventsub_handler = None

        # ループが存在しない場合は何もしない
        if loop is None:
            logger.info("No running loop, nothing to stop.")
            self._processed_message_ids.clear()
            return

        # ループを停止
        try:
            if loop.is_running():
                # 別スレッドからループを停止
                loop.call_soon_threadsafe(loop.stop)
                logger.info("Bot loop stop requested.")
        except Exception as e:
            logger.warning(f"Exception during loop stop: {e}")

        # クリーンアップ
        self._running_loop = None
        self._processed_message_ids.clear()
        logger.info("Bot.stop() completed")

