import asyncio
from twitchio.ext import commands
from src.translator import translate_text, should_filter, apply_translation_dictionary, get_stats
from src.logger import logger
from src.tts import get_tts_instance
from src.participant_tracker import get_tracker
from src.comment_data import create_twitch_comment

class TranslateBot(commands.Bot):
    def __init__(self, token, channel, get_lang_mode, gui_ref, deepl_api_key, tts_enabled_getter=None, tts_include_name_getter=None):
        super().__init__(token=token, prefix='!', initial_channels=[channel])
        self.get_lang_mode = get_lang_mode
        self.gui = gui_ref
        self.deepl_api_key = deepl_api_key
        self.tts_enabled_getter = tts_enabled_getter or (lambda: False)
        self.tts_include_name_getter = tts_include_name_getter or (lambda: False)
        self.tts = get_tts_instance()
        self.tracker = get_tracker()
        # 実行中のイベントループは event_ready でセットする
        self._running_loop = None

    async def event_ready(self):
        # GUI側から run_coroutine_threadsafe で送信できるよう、実際に動いているループを保持
        try:
            self._running_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._running_loop = None
        logger.info(f"Bot logged in as {self.nick}")

    async def event_message(self, message):
        if message.echo:
            return

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
            await message.channel.send(translated)

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
            # 日本語のコメントはそのまま、外国語のコメントは翻訳後を読み上げ
            # 翻訳がある場合は翻訳を、ない場合は元のメッセージを読み上げ
            if translated and translated != message.content:
                # 翻訳結果がある場合（外国語→日本語）
                speak_text = translated
            else:
                # 翻訳がない場合（日本語のコメント）
                speak_text = message.content

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
        # サブスク関連のみ扱う
        sub_related = {
            "sub",
            "resub",
            "subgift",
            "anonsubgift",
            "submysterygift",
            "anonsubmysterygift",
            "primepaidupgrade",
            "giftpaidupgrade",
            "rewardgift",
            "communitypayforward",
            "bitsbadgetier",
        }
        if msg_id not in sub_related:
            return

        display_name = None
        if hasattr(message, "author") and message.author:
            display_name = getattr(message.author, "display_name", None) or getattr(message.author, "name", None)
        display_name = display_name or "匿名"

        system_msg = ""
        if message.tags and message.tags.get("system-msg"):
            system_msg = self._decode_irc_tag(message.tags.get("system-msg"))

        # フォールバックメッセージ
        fallback_msg = f"{display_name} がサブスクしました"
        event_msg = system_msg if system_msg else fallback_msg

        self._notify_special_event(event_msg, event_type="subscription")

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

    def disconnect(self):
        self._ws = None
