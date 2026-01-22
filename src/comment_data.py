"""
コメントデータ構造
複数プラットフォーム対応のためのデータモデル
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class Platform(Enum):
    """配信プラットフォーム"""
    TWITCH = "Twitch"
    YOUTUBE = "YouTube"
    NICONICO = "ニコ生"
    TWITCASTING = "ツイキャス"
    KICK = "Kick"
    SHOWROOM = "SHOWROOM"
    MIXCHANNEL = "ミクチャ"
    MIRRATIV = "ミラティブ"
    UNKNOWN = "不明"


@dataclass
class CommentData:
    """
    コメントデータクラス
    全プラットフォーム共通のコメント情報を保持
    """
    # 基本情報
    username: str                           # ユーザー名
    message: str                            # コメント本文
    platform: Platform                      # プラットフォーム
    timestamp: datetime = field(default_factory=datetime.now)  # 投稿時刻

    # ユーザー情報
    display_name: Optional[str] = None      # 表示名（ユーザー名と異なる場合）
    user_id: Optional[str] = None           # ユーザーID
    avatar_url: Optional[str] = None        # アイコンURL

    # 翻訳情報
    translated: Optional[str] = None        # 翻訳後のテキスト
    original_language: Optional[str] = None # 元の言語
    target_language: Optional[str] = None   # 翻訳先の言語

    # プラットフォーム固有情報
    badges: list = field(default_factory=list)  # バッジ情報（モデレーター、サブスクライバーなど）
    emotes: list = field(default_factory=list)  # エモート情報
    color: Optional[str] = None             # ユーザー名の色
    is_moderator: bool = False              # モデレーターかどうか
    is_subscriber: bool = False             # サブスクライバーかどうか
    is_vip: bool = False                    # VIPかどうか

    # その他
    raw_data: Dict[str, Any] = field(default_factory=dict)  # プラットフォーム固有の生データ

    @property
    def display_username(self) -> str:
        """表示用のユーザー名を取得"""
        return self.display_name if self.display_name else self.username

    @property
    def platform_name(self) -> str:
        """プラットフォーム名を取得"""
        return self.platform.value

    @property
    def formatted_timestamp(self) -> str:
        """フォーマット済みのタイムスタンプを取得"""
        return self.timestamp.strftime("%H:%M:%S")

    @property
    def badge_text(self) -> str:
        """バッジをテキスト形式で取得"""
        badge_symbols = []
        if self.is_moderator:
            badge_symbols.append("🛡️")
        if self.is_subscriber:
            badge_symbols.append("⭐")
        if self.is_vip:
            badge_symbols.append("💎")
        return "".join(badge_symbols)

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換（ログ出力用）"""
        return {
            "username": self.username,
            "display_name": self.display_name,
            "message": self.message,
            "translated": self.translated,
            "platform": self.platform_name,
            "timestamp": self.timestamp.isoformat(),
            "avatar_url": self.avatar_url,
            "badges": self.badges,
            "is_moderator": self.is_moderator,
            "is_subscriber": self.is_subscriber,
            "is_vip": self.is_vip,
            "color": self.color
        }

    def to_log_string(self) -> str:
        """ログ文字列に変換"""
        badge_str = f"{self.badge_text} " if self.badge_text else ""
        translated_str = f"\n→ {self.translated}" if self.translated else ""
        return f"[{self.formatted_timestamp}] [{self.platform_name}] {badge_str}{self.display_username}: {self.message}{translated_str}"


def create_twitch_comment(username: str, message: str, tags: Dict[str, Any],
                         display_name: Optional[str] = None,
                         translated: Optional[str] = None) -> CommentData:
    """
    Twitchのコメントデータを作成

    Args:
        username: ユーザー名
        message: コメント本文
        tags: Twitchのタグ情報
        display_name: 表示名
        translated: 翻訳テキスト

    Returns:
        CommentDataインスタンス
    """
    # バッジ情報の解析
    badges = []
    is_moderator = False
    is_subscriber = False
    is_vip = False

    if tags and tags.get("badges"):
        badge_info = tags.get("badges", {})
        if isinstance(badge_info, dict):
            if "moderator" in badge_info:
                is_moderator = True
                badges.append("moderator")
            if "subscriber" in badge_info:
                is_subscriber = True
                badges.append("subscriber")
            if "vip" in badge_info:
                is_vip = True
                badges.append("vip")

    # アイコンURLの取得（Twitch APIから取得する必要がある）
    # 今回は後で実装するため、プレースホルダー
    avatar_url = None
    user_id = tags.get("user-id") if tags else None
    if user_id:
        # Twitch CDNのデフォルトアイコンパターン
        avatar_url = f"https://static-cdn.jtvnw.net/user-default-pictures-uv/{{size}}.png"

    # ユーザー名の色
    color = tags.get("color") if tags else None

    return CommentData(
        username=username,
        message=message,
        platform=Platform.TWITCH,
        display_name=display_name or username,
        user_id=user_id,
        avatar_url=avatar_url,
        translated=translated,
        badges=badges,
        is_moderator=is_moderator,
        is_subscriber=is_subscriber,
        is_vip=is_vip,
        color=color,
        raw_data=tags or {}
    )
