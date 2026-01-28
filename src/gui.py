# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import threading
import webbrowser
import subprocess
import shutil
import json
import platform
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
from datetime import datetime
from typing import Dict

# pygameは効果音再生で使用
try:
    import pygame
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    PYGAME_AVAILABLE = True
except Exception as e:
    pygame = None
    PYGAME_AVAILABLE = False

from src.auth import run_auth_server_and_get_token, build_auth_url, validate_token
from src.bot import TranslateBot
from src.config import load_config, save_config
from src.voice_listener import VoiceTranslator
from src.overlay_server import update_translation, run_server_thread
from src.logger import logger
from src.tts import get_tts_instance
from src.tts_dictionary import get_dictionary
from src.participant_tracker import get_tracker
from src.voicevox_manager import get_voicevox_manager
from src.comment_data import CommentData
from src import translator
from src.resource_monitor import get_monitor

# 外観設定 / テーマ
# 初期設定（後でconfigから読み込んだテーマで上書き）
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# テーマ定義
THEMES = {
    "gradient": {  # 案1: グラデーション × グラスモーフィズム
        "name": "グラデーション（モダン）",
        "APP_BG": "#0A0E27",
        "APP_BG_GRADIENT": "#1A1535",  # グラデーション用
        "CARD_BG": "#1C1F3A",
        "CARD_BG_GLASS": "#1C1F3A",  # 半透明風
        "PANEL_BG": "#151830",
        "BORDER": "#2D3250",
        "ACCENT": "#00D9FF",  # シアン
        "ACCENT_SECONDARY": "#FF00E5",  # マゼンタ
        "ACCENT_WARN": "#FFB800",
        "TEXT_PRIMARY": "#FFFFFF",
        "TEXT_SUBTLE": "#A0A8C8",
        "SHADOW": "#000000",
        "GLOW": True,  # グロー効果を有効化
    },
    "minimal": {  # 案2: ミニマリスト × マテリアルデザイン
        "name": "ミニマル（シンプル）",
        "APP_BG": "#FAFAFA",
        "APP_BG_GRADIENT": "#F5F5F5",
        "CARD_BG": "#FFFFFF",
        "CARD_BG_GLASS": "#FFFFFF",
        "PANEL_BG": "#F8F9FA",
        "BORDER": "#E0E0E0",
        "ACCENT": "#1976D2",  # Material Blue
        "ACCENT_SECONDARY": "#0288D1",
        "ACCENT_WARN": "#F57C00",
        "TEXT_PRIMARY": "#212121",
        "TEXT_SUBTLE": "#757575",
        "SHADOW": "#00000015",
        "GLOW": False,
    },
    "cyberpunk": {  # 案3: サイバーパンク × ゲーミング
        "name": "サイバーパンク（ゲーミング）",
        "APP_BG": "#000000",
        "APP_BG_GRADIENT": "#0D0208",
        "CARD_BG": "#0A0A0A",
        "CARD_BG_GLASS": "#1A1A1A",
        "PANEL_BG": "#050505",
        "BORDER": "#FF00FF",  # ネオンピンク
        "ACCENT": "#00FFFF",  # ネオンシアン
        "ACCENT_SECONDARY": "#FF00FF",  # ネオンマゼンタ
        "ACCENT_WARN": "#FFFF00",  # ネオンイエロー
        "TEXT_PRIMARY": "#00FFFF",
        "TEXT_SUBTLE": "#008080",  # ダークシアン（半透明の代替）
        "SHADOW": "#004040",  # ダークシアン（半透明の代替）
        "GLOW": True,  # グロー効果強め
    },
    "default": {  # 現在のデフォルトテーマ（既存）
        "name": "デフォルト（クラシック）",
        "APP_BG": "#0C1424",
        "APP_BG_GRADIENT": "#0C1424",
        "CARD_BG": "#111B2E",
        "CARD_BG_GLASS": "#111B2E",
        "PANEL_BG": "#0E1728",
        "BORDER": "#1F2C43",
        "ACCENT": "#22C55E",
        "ACCENT_SECONDARY": "#38BDF8",
        "ACCENT_WARN": "#F97316",
        "TEXT_PRIMARY": "#FFFFFF",
        "TEXT_SUBTLE": "#9BAEC6",
        "SHADOW": "#00000020",
        "GLOW": False,
    }
}

# デフォルトテーマを設定（後で設定から変更可能）
CURRENT_THEME = "default"

# UI theme constants（動的に更新される）
APP_BG = THEMES[CURRENT_THEME]["APP_BG"]
CARD_BG = THEMES[CURRENT_THEME]["CARD_BG"]
PANEL_BG = THEMES[CURRENT_THEME]["PANEL_BG"]
BORDER = THEMES[CURRENT_THEME]["BORDER"]
ACCENT = THEMES[CURRENT_THEME]["ACCENT"]
ACCENT_SECONDARY = THEMES[CURRENT_THEME]["ACCENT_SECONDARY"]
ACCENT_WARN = THEMES[CURRENT_THEME]["ACCENT_WARN"]
TEXT_SUBTLE = THEMES[CURRENT_THEME]["TEXT_SUBTLE"]
BUTTON_CORNER_RADIUS = THEMES[CURRENT_THEME].get("BUTTON_CORNER_RADIUS", 10)
FONT_TITLE = ("Segoe UI Semibold", 18)
FONT_SUBTITLE = ("Segoe UI", 13)
FONT_LABEL = ("Segoe UI Semibold", 12)
FONT_BODY = ("Segoe UI", 12)

class TwitchBotApp:
    def __init__(self, master):
        self.master = master
        self.master.title("ことつな！")

        # ウィンドウアイコンを設定（build_widgetsの後に移動）
        self._window_icon_path = None

        # 画面サイズに応じて最適なサイズを設定
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        # 画面の80%のサイズを使用（最大1400x950）
        window_width = min(int(screen_width * 0.8), 1400)
        window_height = min(int(screen_height * 0.85), 950)
        self.master.geometry(f"{window_width}x{window_height}")
        self.master.minsize(1000, 700)  # 最小ウィンドウサイズを縮小
        self.master.configure(bg=APP_BG)
        self.main_split_ratio = 0.75  # 左右分割の目標比率（左75%）
        self._sash_lock = False  # 再配置ループ防止

        # 設定読み込み
        self.config = load_config()
        translator.set_translation_filters(self.config.get("translation_filters", []))
        translator.set_translation_dictionary(self.config.get("translation_dictionary", []))

        # テーマ適用（widgetビルド前に実行）
        saved_theme = self.config.get("ui_theme", "default")
        self._apply_theme_colors(saved_theme)

        self.token = None
        self.bot_instance = None
        self.tts_started = False
        self.tracker = get_tracker()
        self.tracker.enable()

        # ログ履歴（時系列で記録）
        self.chat_log_history = []
        self.chat_history = []

        # Variables
        self.channel = tk.StringVar(value=self.config.get("channel_name", ""))
        self.lang_mode = tk.StringVar(value=self.config.get("translate_mode", "自動"))
        self.chat_translation_enabled = tk.BooleanVar(value=self.config.get("chat_translation_enabled", True))
        self.client_id = tk.StringVar(value=self.config.get("twitch_client_id", ""))
        self.deepl_key = tk.StringVar(value=self.config.get("deepl_api_key", ""))
        self.gladia_key = tk.StringVar(value=self.config.get("gladia_api_key", ""))
        self.voicevox_path = tk.StringVar(value=self.config.get("voicevox_engine_path", ""))
        self.voicevox_auto_start = tk.BooleanVar(value=self.config.get("voicevox_auto_start", True))
        self.bits_sound_path = tk.StringVar(value=self.config.get("bits_sound_path", ""))
        self.sub_sound_path = tk.StringVar(value=self.config.get("subscription_sound_path", ""))
        # コメントログカスタム
        self.comment_bg = tk.StringVar(value=self.config.get("comment_log_bg", "#0E1728"))
        self.comment_fg = tk.StringVar(value=self.config.get("comment_log_fg", "#E8F0FF"))
        self.comment_font = tk.StringVar(value=self.config.get("comment_log_font", "Consolas 11"))
        self.comment_bubble_style = tk.StringVar(value=self.config.get("comment_bubble_style", "classic"))
        # チャットHTML出力
        self.chat_html_output = tk.BooleanVar(value=self.config.get("chat_html_output", False))
        self.chat_html_path = tk.StringVar(value=self._default_chat_html_path(self.config.get("chat_html_path", "")))
        self.chat_html_newest_first = tk.BooleanVar(value=self.config.get("chat_html_newest_first", False))
        # HTML表示ウィンドウの管理
        self.chat_html_window = None  # Tkinterウィンドウ（フォールバック用）
        self.qt_html_window = None  # PyQt6ウィンドウ（Chromiumベース）
        self.qt_app = None  # PyQt6アプリケーションインスタンス
        # 設定変更は即時保存
        self._setup_auto_save()
        # 参加者タブ自動更新用
        self.participant_tab_refresh_timer = None

        # 音声翻訳クラスの初期化
        self.voice_translator = VoiceTranslator(
            mode_getter=lambda: self.lang_mode.get(),
            api_key_getter=lambda: self.deepl_key.get(),
            callback=self.voice_callback,
            config_data=self.config
        )

        # TTS (Text-to-Speech) の初期化
        self.tts = get_tts_instance()

        # VOICEVOX Engine Manager の初期化
        voicevox_engine_path = self.config.get("voicevox_engine_path", "")
        voicevox_url = self.config.get("voicevox_url", "http://localhost:50021")
        self.voicevox_manager = get_voicevox_manager(voicevox_engine_path, voicevox_url)

        # オーバーレイサーバー起動
        run_server_thread()

        # リソース監視の初期化
        self.resource_monitor = get_monitor()
        # 警告コールバックを設定
        self.resource_monitor.warning_callback = self._on_resource_warning

        self.build_widgets()

        # ウィンドウアイコンを設定（ウィジェット構築後）
        self._setup_window_icon()

        # 起動時にHTML出力がONの場合、ウィンドウを開く
        if self.chat_html_output.get():
            self.master.after(500, self._open_chat_html_window)

        # 起動時に保存されたトークンをチェックして自動ログイン
        self.master.after(1000, self._check_saved_token)

    def _apply_theme_colors(self, theme_name):
        """
        テーマを適用してモジュールレベルの色変数を更新

        Args:
            theme_name: テーマ名 (default / gradient / minimal / cyberpunk)
        """
        global CURRENT_THEME, APP_BG, CARD_BG, PANEL_BG, BORDER
        global ACCENT, ACCENT_SECONDARY, ACCENT_WARN, TEXT_SUBTLE
        global BUTTON_CORNER_RADIUS

        if theme_name not in THEMES:
            logger.warning(f"Unknown theme: {theme_name}, falling back to default")
            theme_name = "default"

        theme = THEMES[theme_name]
        CURRENT_THEME = theme_name

        # 色変数を更新
        APP_BG = theme["APP_BG"]
        CARD_BG = theme["CARD_BG"]
        PANEL_BG = theme["PANEL_BG"]
        BORDER = theme["BORDER"]
        ACCENT = theme["ACCENT"]
        ACCENT_SECONDARY = theme["ACCENT_SECONDARY"]
        ACCENT_WARN = theme["ACCENT_WARN"]
        TEXT_SUBTLE = theme["TEXT_SUBTLE"]
        BUTTON_CORNER_RADIUS = theme.get("BUTTON_CORNER_RADIUS", 10)

        # ライトモード/ダークモードの切り替え
        if theme_name == "minimal":
            ctk.set_appearance_mode("Light")
        else:
            ctk.set_appearance_mode("Dark")

        logger.info(f"Theme applied: {theme['name']} ({theme_name})")

    def _on_theme_changed(self, display_name):
        """
        テーマ選択が変更されたときのコールバック

        Args:
            display_name: 表示名 (例: "グラデーション（モダン）")
        """
        # 表示名からテーマキーへの変換マップ
        display_to_key = {
            "デフォルト（クラシック）": "default",
            "グラデーション（モダン）": "gradient",
            "ミニマル（シンプル・ライトモード）": "minimal",
            "サイバーパンク（ゲーミング）": "cyberpunk"
        }

        theme_key = display_to_key.get(display_name, "default")

        # テーマを適用
        self._apply_theme_colors(theme_key)

        # 設定を保存
        self.config["ui_theme"] = theme_key
        save_config(self.config)

        # ユーザーに通知
        self.log_message(f"✨ テーマを '{THEMES[theme_key]['name']}' に変更しました")
        self.log_message("⚠️ 一部の色変更を反映するには、アプリを再起動してください")

    def build_widgets(self):
        # メインコンテナ
        self.main_frame = ctk.CTkFrame(self.master, fg_color=APP_BG)
        self.main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        # タブビュー作成
        self.tabview = ctk.CTkTabview(self.main_frame, fg_color=PANEL_BG, segmented_button_fg_color=CARD_BG)
        self.tabview.pack(fill="both", expand=True)

        self.tab_main = self.tabview.add("メイン操作")
        self.tab_settings = self.tabview.add("設定")
        self.tab_dictionary = self.tabview.add("読み上げ辞書")
        self.tab_participants = self.tabview.add("参加者管理")
        self.tab_resources = self.tabview.add("リソース監視")

        # === メイン操作タブ ===
        self.build_main_tab()

        # === 設定タブ ===
        self.build_settings_tab()

        # === 辞書タブ ===
        self.build_dictionary_tab()

        # === 参加者タブ ===
        self.build_participants_tab()

        # === リソース監視タブ ===
        self.build_resource_monitor_tab()

    def build_main_tab(self):
        surface = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        surface.pack(fill="both", expand=True, padx=6, pady=6)

        # ===== ヒーローバー =====
        hero = ctk.CTkFrame(surface, fg_color=CARD_BG, corner_radius=16, border_width=1, border_color=BORDER)
        hero.pack(fill="x", padx=4, pady=(0, 12))
        hero.grid_columnconfigure(1, weight=1)
        hero.grid_columnconfigure(2, weight=0)

        ctk.CTkLabel(hero, text="ことつな！", font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 0))
        ctk.CTkLabel(hero, text="翻訳・読み上げ・参加者管理をまとめたコントロールセンター", font=FONT_SUBTITLE, text_color=TEXT_SUBTLE).grid(row=1, column=0, sticky="w", padx=18, pady=(2, 14))

        badge_row = ctk.CTkFrame(hero, fg_color="transparent")
        badge_row.grid(row=0, column=1, rowspan=2, sticky="w", pady=10)
        ctk.CTkLabel(badge_row, text="現在の翻訳モード", font=FONT_LABEL, text_color=TEXT_SUBTLE).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(badge_row, textvariable=self.lang_mode, fg_color=ACCENT_SECONDARY, text_color="#0B1220", corner_radius=12, font=("Segoe UI Semibold", 13), padx=14, pady=6).pack(side="left", padx=(0, 10))

        # 右端: 主ボタン
        action_bar = ctk.CTkFrame(hero, fg_color="transparent")
        action_bar.grid(row=0, column=2, rowspan=2, sticky="e", padx=16, pady=10)
        action_bar.grid_columnconfigure(0, weight=1)
        button_opts = {"font": ("Segoe UI Semibold", 13), "height": 40, "width": 160, "corner_radius": BUTTON_CORNER_RADIUS}
        ctk.CTkButton(action_bar, text="① トークン認証", command=self.start_auth, fg_color=ACCENT_SECONDARY, hover_color="#1EA4D8", text_color="#0B1220", **button_opts).grid(row=0, column=0, sticky="ew", pady=3)
        ctk.CTkButton(action_bar, text="② BOT起動", command=self.start_bot, fg_color=ACCENT, hover_color="#16A34A", text_color="#0B1220", **button_opts).grid(row=1, column=0, sticky="ew", pady=3)
        ctk.CTkButton(action_bar, text="③ BOT停止", command=self.stop_bot, fg_color="#EF4444", hover_color="#DC2626", text_color="#FFFFFF", **button_opts).grid(row=2, column=0, sticky="ew", pady=3)
        ctk.CTkButton(action_bar, text="🚪 ログアウト", command=self.logout, fg_color="#6B7280", hover_color="#4B5563", text_color="#FFFFFF", **button_opts).grid(row=3, column=0, sticky="ew", pady=3)

        # ===== コントロール群 =====
        controls = ctk.CTkFrame(surface, fg_color="transparent")
        controls.pack(fill="x", padx=4, pady=(0, 10))
        controls.grid_columnconfigure(0, weight=2)
        controls.grid_columnconfigure(1, weight=2)
        controls.grid_columnconfigure(2, weight=1)

        # 接続/翻訳設定カード
        card_connect = ctk.CTkFrame(controls, fg_color=CARD_BG, corner_radius=14, border_width=1, border_color=BORDER)
        card_connect.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        card_connect.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card_connect, text="配信と翻訳", font=FONT_LABEL).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 8))
        ctk.CTkLabel(card_connect, text="チャンネル名", font=FONT_SUBTITLE, text_color=TEXT_SUBTLE).grid(row=1, column=0, sticky="e", padx=12, pady=6)
        ctk.CTkEntry(card_connect, textvariable=self.channel, placeholder_text="配信チャンネル名", height=34).grid(row=1, column=1, sticky="ew", padx=(0, 14), pady=6)
        ctk.CTkLabel(card_connect, text="翻訳モード", font=FONT_SUBTITLE, text_color=TEXT_SUBTLE).grid(row=2, column=0, sticky="e", padx=12, pady=6)
        ctk.CTkOptionMenu(card_connect, variable=self.lang_mode, values=['自動', '英→日', '日→英'], height=34, fg_color=PANEL_BG, button_color=ACCENT_SECONDARY, button_hover_color="#1EA4D8").grid(row=2, column=1, sticky="w", padx=(0, 14), pady=6)
        # チャット翻訳有効/無効トグル
        ctk.CTkLabel(card_connect, text="チャット翻訳", font=FONT_SUBTITLE, text_color=TEXT_SUBTLE).grid(row=3, column=0, sticky="e", padx=12, pady=6)
        self.translation_toggle = ctk.CTkSwitch(
            card_connect,
            text="有効",
            variable=self.chat_translation_enabled,
            command=self._on_translation_toggle_changed,
            onvalue=True,
            offvalue=False,
            font=FONT_BODY
        )
        self.translation_toggle.pack_forget()  # gridで配置するため
        self.translation_toggle.grid(row=3, column=1, sticky="w", padx=(0, 14), pady=6)

        # 音声/読み上げカード
        card_voice = ctk.CTkFrame(controls, fg_color=CARD_BG, corner_radius=14, border_width=1, border_color=BORDER)
        card_voice.grid(row=0, column=1, sticky="nsew", padx=8)
        card_voice.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(card_voice, text="音声 & 読み上げ", font=FONT_LABEL).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 8))

        self.voice_var = ctk.BooleanVar(value=False)
        # self.voice_tts_var: 廃止（読み上げない）
        # self.event_tts_var: 廃止（常に読み上げる）
        # self.voice_send_to_chat_var: 廃止（voice_varと統合）
        self.tts_include_name_var = ctk.BooleanVar(value=False)

        toggle_items = [
            ("🎤 音声翻訳してチャット送信", self.voice_var, self.toggle_voice),
            ("👤 名前も読み上げる", self.tts_include_name_var, None),
        ]

        for idx, (label, var, cmd) in enumerate(toggle_items):
            row = 1 + idx // 2
            col = idx % 2
            ctk.CTkSwitch(card_voice, text=label, variable=var, command=cmd, font=FONT_BODY).grid(row=row, column=col, sticky="w", padx=12, pady=5)

        # サマリーカード（ステータス表示用）
        card_status = ctk.CTkFrame(controls, fg_color=CARD_BG, corner_radius=14, border_width=1, border_color=BORDER)
        card_status.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        card_status.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card_status, text="セッションの状態", font=FONT_LABEL).pack(anchor="w", padx=14, pady=(12, 6))
        self.status_label = ctk.CTkLabel(card_status, text="待機中 - トークン認証を行ってください", font=FONT_BODY, text_color=TEXT_SUBTLE, wraplength=240, justify="left")
        self.status_label.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkLabel(card_status, text="読み上げと翻訳の切替は上のカードからいつでも変更できます。", font=("Segoe UI", 11), text_color=TEXT_SUBTLE, wraplength=240, justify="left").pack(fill="x", padx=14, pady=(0, 12))
        self.stats_label = ctk.CTkLabel(card_status, text="翻訳統計: 0 req / 0 hit / 0 filtered", font=("Segoe UI", 11), text_color=TEXT_SUBTLE, wraplength=240, justify="left")
        self.stats_label.pack(fill="x", padx=14, pady=(0, 12))

        # === リサイズ可能な3カラムレイアウト（PanedWindow使用） ===
        content_shell = ctk.CTkFrame(surface, fg_color=CARD_BG, corner_radius=14, border_width=1, border_color=BORDER)
        content_shell.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        main_paned = tk.PanedWindow(content_shell, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED, bg=BORDER, bd=0, relief="flat", handlepad=2)
        main_paned.pack(fill="both", expand=True, padx=6, pady=6)
        # 幅変更時も比率を維持
        main_paned.bind("<Configure>", lambda e: self._force_main_split())

        # === 左側: コメントログエリア ===
        left_frame = ctk.CTkFrame(main_paned, fg_color=PANEL_BG, corner_radius=12)
        self.left_frame = left_frame  # 参照を保存

        # グリッドレイアウトの設定（ボタンを常に表示するため）
        left_frame.grid_rowconfigure(0, weight=0)  # ヘッダー
        left_frame.grid_rowconfigure(1, weight=1)  # コメントペイン（伸縮可能）
        left_frame.grid_rowconfigure(2, weight=0)  # ボタンフレーム
        left_frame.grid_columnconfigure(0, weight=1)

        # コメントログタイトル
        comment_header = ctk.CTkFrame(left_frame, fg_color="transparent")
        comment_header.grid(row=0, column=0, sticky="ew", pady=(10, 8), padx=6)

        self.comment_title = ctk.CTkLabel(
            comment_header,
            text="💬 コメントログ",
            font=FONT_LABEL
        )
        self.comment_title.pack(side="left", padx=10)

        # コメント表示エリア（タイル + システムログ）の分割
        comment_paned = tk.PanedWindow(
            left_frame,
            orient=tk.VERTICAL,
            sashwidth=4,
            sashrelief=tk.RAISED,
            bg=BORDER,
            bd=0,
            relief="flat",
            handlepad=2
        )
        comment_paned.grid(row=1, column=0, sticky="nsew", padx=8)

        # 上部：タイル表示（カード形式）
        tile_container = ctk.CTkFrame(comment_paned)
        self.comment_tile_frame = ctk.CTkScrollableFrame(
            tile_container,
            fg_color="transparent",
            height=260,
            corner_radius=10
        )
        self.comment_tile_frame.pack(fill="both", expand=True, padx=4, pady=(4, 4))
        self.comment_tiles = []
        self.comment_tile_limit = 120

        # 下部：システムログ（時系列順のテキストログ）
        log_container = ctk.CTkFrame(comment_paned)
        log_header = ctk.CTkLabel(
            log_container,
            text="📋 システムログ",
            font=("Segoe UI Semibold", 11),
            anchor="w"
        )
        log_header.pack(fill="x", padx=5, pady=(4, 2))

        self.log = ctk.CTkTextbox(log_container, width=500, height=120, font=("Consolas", 11))
        # カスタムテーマ適用
        self._apply_log_style(self.log)
        self.log.pack(fill="both", expand=True, padx=5, pady=(0, 4))
        self.log.insert("0.0", "--- システムログ開始 ---\n")

        # PanedWindowに追加（上部60%, 下部40%）
        comment_paned.add(tile_container, minsize=200)
        comment_paned.add(log_container, minsize=100)

        # ログ履歴
        self.log_history = []

        # ログ操作ボタン
        log_btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        log_btn_frame.grid(row=2, column=0, sticky="ew", pady=(6, 10), padx=8)

        ctk.CTkButton(
            log_btn_frame,
            text="📄 テキスト出力",
            command=self.export_log_text,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            width=120
        ).pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            log_btn_frame,
            text="📊 JSON出力",
            command=self.export_log_json,
            fg_color="#8B5CF6",
            hover_color="#7C3AED",
            width=120
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            log_btn_frame,
            text="🗑 ログクリア",
            command=self.clear_log,
            fg_color="#6B7280",
            hover_color="#4B5563",
            width=120
        ).pack(side="left", padx=5)

        # HTML出力トグル
        ctk.CTkSwitch(
            log_btn_frame,
            text="💾 チャットをHTML出力",
            variable=self.chat_html_output,
            command=self.toggle_chat_html_output,
            font=FONT_BODY
        ).pack(side="left", padx=8)

        # ブラウザで開くボタン
        ctk.CTkButton(
            log_btn_frame,
            text="🌐 ブラウザで確認",
            command=self.open_chat_html_in_browser,
            width=120,
            fg_color="#0D9488",
            hover_color="#0F766E"
        ).pack(side="left", padx=5)

        # === 右側: 上下2分割のPanedWindow（垂直方向） ===
        right_paned = tk.PanedWindow(
            main_paned,
            orient=tk.VERTICAL,
            sashwidth=5,
            sashrelief=tk.RAISED,
            bg=BORDER,
            bd=0,
            relief="flat",
            handlepad=2
        )

        # === 右上: 特別イベントログ ===
        event_frame = ctk.CTkFrame(right_paned, fg_color=PANEL_BG, corner_radius=12)
        self.event_frame = event_frame  # 参照を保存

        # タイトル
        event_header = ctk.CTkFrame(event_frame, fg_color="transparent")
        event_header.pack(fill="x", pady=(10, 6), padx=6)

        self.event_title = ctk.CTkLabel(
            event_header,
            text="⭐ 特別イベント",
            font=FONT_LABEL
        )
        self.event_title.pack(side="left", padx=10)

        # 特別イベントログ
        self.event_log = ctk.CTkTextbox(event_frame, width=200, height=150, font=("Consolas", 11))
        self._apply_log_style(self.event_log)
        self.event_log.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.event_log.insert("0.0", "--- 特別イベントログ ---\n")

        # === 右下: 参加者一覧 ===
        participant_frame = ctk.CTkFrame(right_paned, fg_color=PANEL_BG, corner_radius=12)
        self.participant_frame = participant_frame  # 参照を保存

        # タイトルと参加者数
        header_frame = ctk.CTkFrame(participant_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(10, 6), padx=8)

        self.participant_title = ctk.CTkLabel(
            header_frame,
            text="👥 参加者",
            font=FONT_LABEL
        )
        self.participant_title.pack(side="left")

        self.main_participant_count_label = ctk.CTkLabel(
            header_frame,
            text="(0人)",
            font=("Segoe UI Semibold", 13),
            text_color=TEXT_SUBTLE
        )
        self.main_participant_count_label.pack(side="left", padx=5)

        # 参加者リスト（スクロール可能）
        self.main_participant_list = ctk.CTkScrollableFrame(participant_frame, height=150, fg_color="transparent")
        self.main_participant_list.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # 右側のPanedWindowに上下のフレームを追加
        right_paned.add(event_frame, minsize=100)
        right_paned.add(participant_frame, minsize=100)

        # メインのPanedWindowに左右のフレームを追加（初期比率: 70% vs 30%）
        main_paned.add(left_frame, minsize=400)
        main_paned.add(right_paned, minsize=200)

        # PanedWindowの参照を保存（カスタマイズモード用）
        self.main_paned = main_paned
        self.right_paned = right_paned
        self.comment_paned = comment_paned  # コメントペインの参照も保存

        # 保存されたレイアウトを復元（初期位置設定を含む）
        # ウィンドウが完全に表示された後に実行するため、遅延を長めに設定
        self.master.after(300, lambda: self._restore_layout())

        # 参加者リスト自動更新用のタイマー
        self.participant_refresh_timer = None
        self.start_participant_auto_refresh()

        # TTSを自動起動
        self.master.after(300, self._ensure_tts_started)
        # 統計表示更新
        self.master.after(1000, self._update_stats_display)

    def build_settings_tab(self):
        # スクロール可能なフレームを作成
        scrollable_frame = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

        frm_set = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        frm_set.pack(fill="both", expand=True, padx=10, pady=10)
        frm_set.grid_columnconfigure(1, weight=1)

        # === UI テーマ設定 ===
        ctk.CTkLabel(frm_set, text="UIテーマ", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(10, 10))
        ctk.CTkLabel(frm_set, text="テーマを選択:", font=("Arial", 14, "bold")).grid(row=1, column=0, sticky="w", pady=(10, 0))

        # テーマ名とその説明を含むマップ
        theme_display_names = {
            "default": "デフォルト（クラシック）",
            "gradient": "グラデーション（モダン）",
            "minimal": "ミニマル（シンプル・ライトモード）",
            "cyberpunk": "サイバーパンク（ゲーミング）"
        }

        # 現在のテーマを表示名に変換
        current_theme_key = self.config.get("ui_theme", "default")
        current_theme_display = theme_display_names.get(current_theme_key, theme_display_names["default"])

        # テーマ選択用のStringVar（表示名を格納）
        self.ui_theme_var = tk.StringVar(value=current_theme_display)

        # OptionMenu作成
        theme_menu = ctk.CTkOptionMenu(
            frm_set,
            values=[theme_display_names[k] for k in ["default", "gradient", "minimal", "cyberpunk"]],
            variable=self.ui_theme_var,
            command=self._on_theme_changed,
            width=280
        )
        theme_menu.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        ctk.CTkLabel(
            frm_set,
            text="💡 テーマを変更するとアプリの外観が即座に切り替わります",
            font=("Arial", 10),
            text_color="gray"
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 15))

        # プラットフォーム設定
        ctk.CTkLabel(frm_set, text="配信プラットフォーム設定", font=("Arial", 16, "bold")).grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 10))
        ctk.CTkLabel(frm_set, text="Client ID (Twitch):", font=("Arial", 14, "bold")).grid(row=5, column=0, sticky="w", pady=(10, 0))
        ctk.CTkEntry(frm_set, textvariable=self.client_id, width=300).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        btn_twitch_help = ctk.CTkButton(frm_set, text="Twitch開発者コンソールへ (ID取得)",
                                      command=lambda: webbrowser.open("https://dev.twitch.tv/console/apps"),
                                      fg_color="gray",
                                      width=200)
        btn_twitch_help.grid(row=6, column=2, padx=10, pady=(0, 5), sticky="w")

        # 翻訳API設定
        ctk.CTkLabel(frm_set, text="翻訳API設定", font=("Arial", 16, "bold")).grid(row=7, column=0, columnspan=3, sticky="w", pady=(20, 10))
        ctk.CTkLabel(frm_set, text="DeepL API Key:", font=("Arial", 14, "bold")).grid(row=8, column=0, sticky="w", pady=(10, 0))
        ctk.CTkEntry(frm_set, textvariable=self.deepl_key, width=300, show="*").grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        btn_deepl_help = ctk.CTkButton(frm_set, text="DeepL API登録ページへ",
                                      command=lambda: webbrowser.open("https://www.deepl.com/pro-api"),
                                      fg_color="gray",
                                      width=200)
        btn_deepl_help.grid(row=9, column=2, padx=10, pady=(0, 5), sticky="w")

        # 音声認識API設定
        ctk.CTkLabel(frm_set, text="音声認識API設定", font=("Arial", 16, "bold")).grid(row=10, column=0, columnspan=3, sticky="w", pady=(20, 10))
        ctk.CTkLabel(frm_set, text="Gladia API Key (音声認識):", font=("Arial", 14, "bold")).grid(row=11, column=0, sticky="w", pady=(10, 0))
        ctk.CTkEntry(frm_set, textvariable=self.gladia_key, width=300, show="*").grid(row=12, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        btn_gladia_help = ctk.CTkButton(frm_set, text="Gladia登録ページへ (月10h無料)",
                                       command=lambda: webbrowser.open("https://www.gladia.io"),
                                       fg_color="gray",
                                       width=200)
        btn_gladia_help.grid(row=12, column=2, padx=10, pady=(0, 5), sticky="w")

        # Gladia使用状況表示
        usage_sec = self.config.get("gladia_usage_seconds", 0)
        usage_hours = usage_sec / 3600
        remaining_hours = 10 - usage_hours
        usage_text = f"今月の使用: {usage_hours:.2f}h / 10h (残り: {remaining_hours:.2f}h)"
        provider = self.config.get("stt_provider", "gladia")
        provider_text = "Gladia" if provider == "gladia" else "Google SR"

        self.gladia_usage_label = ctk.CTkLabel(frm_set,
                                               text=f"{usage_text}\n現在のプロバイダー: {provider_text}",
                                               text_color="gray",
                                               font=("Arial", 11))
        self.gladia_usage_label.grid(row=13, column=0, columnspan=3, sticky="w")

        # 読み上げ設定
        ctk.CTkLabel(frm_set, text="読み上げ設定", font=("Arial", 16, "bold")).grid(row=14, column=0, columnspan=3, sticky="w", pady=(20, 10))
        ctk.CTkLabel(frm_set, text="VOICEVOX Engine パス:", font=("Arial", 14, "bold")).grid(row=15, column=0, sticky="w", pady=(10, 0))

        voicevox_frame = ctk.CTkFrame(frm_set, fg_color="transparent")
        voicevox_frame.grid(row=16, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        voicevox_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(voicevox_frame, textvariable=self.voicevox_path, width=250).grid(row=0, column=0, sticky="ew", padx=(0, 5))

        ctk.CTkButton(
            voicevox_frame,
            text="参照...",
            command=self.browse_voicevox_path,
            width=70,
            fg_color="gray"
        ).grid(row=0, column=1)

        btn_voicevox_help = ctk.CTkButton(frm_set, text="VOICEVOX公式サイト",
                                          command=lambda: webbrowser.open("https://voicevox.hiroshiba.jp/"),
                                          fg_color="gray",
                                          width=200)
        btn_voicevox_help.grid(row=16, column=2, padx=10, pady=(0, 5), sticky="w")

        # ヒントラベル
        ctk.CTkLabel(
            frm_set,
            text="💡 ヒント: 「参照...」ボタンでVOICEVOXフォルダ内の run.exe を選択してください",
            font=("Arial", 10),
            text_color="gray"
        ).grid(row=16, column=0, columnspan=2, sticky="w", pady=(30, 0))

        # テストボタン
        ctk.CTkButton(
            frm_set,
            text="🔍 VOICEVOX接続テスト",
            command=self.test_voicevox_connection,
            fg_color="#6B7280",
            hover_color="#4B5563",
            width=200
        ).grid(row=16, column=2, padx=10, pady=(30, 0), sticky="w")

        # VOICEVOX自動起動チェックボックス
        ctk.CTkCheckBox(
            frm_set,
            text="読み上げ開始時にVOICEVOX Engineを自動起動",
            variable=self.voicevox_auto_start,
            font=("Arial", 12)
        ).grid(row=17, column=0, columnspan=2, sticky="w", pady=(5, 0))

        # TTS診断ボタン
        ctk.CTkButton(
            frm_set,
            text="🩺 読み上げ診断",
            command=self.diagnose_tts,
            fg_color="#8B5CF6",
            hover_color="#7C3AED",
            width=200
        ).grid(row=17, column=2, padx=10, pady=(5, 0), sticky="w")

        # === コメントログ外観 ===
        row_base = 18
        ctk.CTkLabel(frm_set, text="コメントログ外観", font=("Arial", 14, "bold")).grid(row=row_base, column=0, sticky="w", pady=(16, 4))
        ctk.CTkLabel(frm_set, text="背景色", font=("Arial", 12)).grid(row=row_base+1, column=0, sticky="w")
        ctk.CTkEntry(frm_set, textvariable=self.comment_bg, width=140).grid(row=row_base+1, column=1, sticky="w", pady=2)
        ctk.CTkLabel(frm_set, text="文字色", font=("Arial", 12)).grid(row=row_base+2, column=0, sticky="w")
        ctk.CTkEntry(frm_set, textvariable=self.comment_fg, width=140).grid(row=row_base+2, column=1, sticky="w", pady=2)
        ctk.CTkLabel(frm_set, text="フォント (例: Consolas 11)", font=("Arial", 12)).grid(row=row_base+3, column=0, sticky="w")
        ctk.CTkEntry(frm_set, textvariable=self.comment_font, width=220).grid(row=row_base+3, column=1, sticky="w", pady=2)
        ctk.CTkLabel(frm_set, text="吹き出しデザイン", font=("Arial", 12)).grid(row=row_base+4, column=0, sticky="w")
        ctk.CTkOptionMenu(frm_set, values=["classic", "modern", "box", "bubble", "neon", "cute", "minimal"], variable=self.comment_bubble_style, width=200).grid(row=row_base+4, column=1, sticky="w")

        # === HTML出力設定 ===
        ctk.CTkLabel(frm_set, text="チャットHTML出力先", font=("Arial", 14, "bold")).grid(row=row_base+5, column=0, sticky="w", pady=(12, 4))
        path_row = ctk.CTkFrame(frm_set, fg_color="transparent")
        path_row.grid(row=row_base+6, column=0, columnspan=2, sticky="ew", pady=2)
        path_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(path_row, textvariable=self.chat_html_path).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(path_row, text="デフォルトに戻す", width=140,
                      command=lambda: self.chat_html_path.set(self._default_chat_html_path(""))).grid(row=0, column=1)

        # HTML出力のコメント表示順序
        ctk.CTkLabel(frm_set, text="コメント表示順序", font=("Arial", 12)).grid(row=row_base+7, column=0, sticky="w", pady=(8, 2))
        ctk.CTkSwitch(frm_set, text="上が新しいコメント（オフ＝下が新しい）", variable=self.chat_html_newest_first, font=("Arial", 11)).grid(row=row_base+7, column=1, sticky="w", pady=(8, 2))

        # イベント効果音
        event_row = 27
        ctk.CTkLabel(frm_set, text="イベント効果音 (TTS前に再生):", font=("Arial", 14, "bold")).grid(row=event_row, column=0, sticky="w", pady=(16, 0))

        # ビッツ効果音
        bits_frame = ctk.CTkFrame(frm_set, fg_color="transparent")
        bits_frame.grid(row=event_row+1, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        bits_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(bits_frame, text="ビッツ:", width=60, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 5))
        ctk.CTkEntry(bits_frame, textvariable=self.bits_sound_path).grid(row=0, column=1, sticky="ew", padx=(0, 5))
        ctk.CTkButton(bits_frame, text="参照", width=60, fg_color="gray",
                      command=lambda: self.select_event_sound("bits")).grid(row=0, column=2, padx=(0, 5))
        ctk.CTkButton(bits_frame, text="再生", width=60, fg_color="#2e8b57",
                      command=lambda: self.play_event_sound("bits")).grid(row=0, column=3)

        # サブスク効果音
        sub_frame = ctk.CTkFrame(frm_set, fg_color="transparent")
        sub_frame.grid(row=event_row+2, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        sub_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(sub_frame, text="サブスク:", width=60, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 5))
        ctk.CTkEntry(sub_frame, textvariable=self.sub_sound_path).grid(row=0, column=1, sticky="ew", padx=(0, 5))
        ctk.CTkButton(sub_frame, text="参照", width=60, fg_color="gray",
                      command=lambda: self.select_event_sound("subscription")).grid(row=0, column=2, padx=(0, 5))
        ctk.CTkButton(sub_frame, text="再生", width=60, fg_color="#2e8b57",
                      command=lambda: self.play_event_sound("subscription")).grid(row=0, column=3)

        # 保存ボタン
        ctk.CTkButton(frm_set, text="設定を保存", command=self.save_settings, height=40, width=220).grid(row=event_row+4, column=0, columnspan=3, pady=30, sticky="w")

        ctk.CTkLabel(frm_set, text="※ 設定変更後は必ず「保存」を押してください。\n※ チャンネル名なども保存されます。", text_color="gray").grid(row=event_row+5, column=0, columnspan=3)

    def diagnose_tts(self):
        """TTS（読み上げ）システムの診断を実行"""
        self.log_message("🩺 === TTS診断開始 ===")

        # 1. TTSエンジンの状態確認
        if self.tts_started:
            self.log_message(f"✅ TTSエンジン: 起動中 (モード: {self.tts.engine_mode})")
        else:
            self.log_message("⚠️ TTSエンジン: 停止中")

        # 2. VOICEVOX Engineの状態確認
        voicevox_running = self.voicevox_manager.is_running()
        if voicevox_running:
            self.log_message(f"✅ VOICEVOX Engine: 起動中 ({self.voicevox_manager.api_url})")
        else:
            self.log_message(f"❌ VOICEVOX Engine: 停止中 ({self.voicevox_manager.api_url})")

        # 3. pygameオーディオの状態確認
        try:
            from src.tts import PYGAME_IMPORTED, AUDIO_AVAILABLE
            if PYGAME_IMPORTED:
                if AUDIO_AVAILABLE:
                    self.log_message("✅ pygameオーディオ: 利用可能")
                else:
                    self.log_message("⚠️ pygameオーディオ: インポート済みだが初期化されていない")
            else:
                self.log_message("❌ pygame: インストールされていない")
        except Exception as e:
            self.log_message(f"⚠️ pygameチェックエラー: {e}")

        # 4. pyttsx3の状態確認
        try:
            from src.tts import PYTTSX3_AVAILABLE
            if PYTTSX3_AVAILABLE:
                self.log_message("✅ pyttsx3: 利用可能（フォールバックエンジン）")
            else:
                self.log_message("❌ pyttsx3: インストールされていない")
        except Exception as e:
            self.log_message(f"⚠️ pyttsx3チェックエラー: {e}")

        # 5. テスト読み上げ
        self.log_message("🔊 テスト読み上げを実行中...")

        def test_speak():
            test_text = "こんにちは、これはテストです"
            try:
                # TTSが起動していない場合は起動を試みる
                if not self.tts_started:
                    self.log_message("TTSエンジンを起動しています...")
                    success = self.tts.start()
                    if success:
                        self.tts_started = True
                        self.log_message(f"✅ TTSエンジンが起動しました (モード: {self.tts.engine_mode})")
                    else:
                        self.master.after(0, lambda: self.log_message("❌ TTSエンジンの起動に失敗しました"))
                        return

                # テスト読み上げを強制実行
                self.tts.speak(test_text, force=True)
                self.master.after(0, lambda: self.log_message(f"✅ テスト読み上げを送信しました: {test_text}"))
                self.master.after(0, lambda: self.log_message("💡 数秒待っても音声が聞こえない場合:"))
                self.master.after(0, lambda: self.log_message("  • 音量設定を確認"))
                self.master.after(0, lambda: self.log_message("  • 別のオーディオアプリを閉じる"))
                self.master.after(0, lambda: self.log_message("  • VOICEVOX Engineを再起動"))

            except Exception as e:
                self.master.after(0, lambda: self.log_message(f"❌ テスト読み上げエラー: {e}"))
                logger.error(f"Test speak error: {e}", exc_info=True)

        # 別スレッドでテスト実行
        threading.Thread(target=test_speak, daemon=True).start()

        self.log_message("🩺 === TTS診断完了 ===")

    def test_voicevox_connection(self):
        """VOICEVOX Engineへの接続をテスト"""
        voicevox_path = self.voicevox_path.get().strip()

        # パスのチェック
        if not voicevox_path:
            messagebox.showwarning(
                "接続テスト",
                "VOICEVOX Engineのパスが設定されていません。\n\n"
                "「参照...」ボタンから run.exe を選択してください。"
            )
            return

        abs_path = os.path.abspath(voicevox_path)
        if not os.path.exists(abs_path):
            messagebox.showerror(
                "接続テスト - ファイルが見つかりません",
                f"指定されたファイルが見つかりません:\n{abs_path}\n\n"
                f"設定値: {voicevox_path}\n\n"
                "「参照...」ボタンから正しいファイルを選択してください。"
            )
            self.log_message(f"❌ ファイルが見つかりません: {abs_path}")
            return

        # 実行可能かチェック
        if not os.access(abs_path, os.X_OK):
            messagebox.showwarning(
                "接続テスト - 実行権限なし",
                f"ファイルに実行権限がありません:\n{abs_path}\n\n"
                "ファイルのプロパティを確認してください。"
            )
            self.log_message(f"⚠️ 実行権限がありません: {abs_path}")
            return

        # VOICEVOX Engineが起動しているかチェック
        if self.voicevox_manager.is_running():
            messagebox.showinfo(
                "接続テスト - 成功",
                "✅ VOICEVOX Engineは既に起動しています！\n\n"
                f"API URL: {self.voicevox_manager.api_url}\n"
                "読み上げ機能が使用できます。"
            )
            self.log_message("✅ VOICEVOX Engine接続テスト: 成功（既に起動中）")
            return

        # 起動を試みる
        self.log_message("🔍 VOICEVOX Engineへの接続をテストしています...")
        messagebox.showinfo(
            "接続テスト",
            "VOICEVOX Engineの起動を試みます。\n\n"
            "数秒かかることがあります..."
        )

        def test_thread():
            success = self.voicevox_manager.start()
            if success:
                self.master.after(0, lambda: messagebox.showinfo(
                    "接続テスト - 成功",
                    f"✅ VOICEVOX Engineの起動に成功しました！\n\n"
                    f"実行ファイル: {abs_path}\n"
                    f"API URL: {self.voicevox_manager.api_url}\n\n"
                    "読み上げ機能が使用できます。"
                ))
                self.master.after(0, lambda: self.log_message("✅ VOICEVOX Engine接続テスト: 成功"))
            else:
                self.master.after(0, lambda: messagebox.showerror(
                    "接続テスト - 失敗",
                    f"❌ VOICEVOX Engineの起動に失敗しました。\n\n"
                    f"実行ファイル: {abs_path}\n\n"
                    "考えられる原因:\n"
                    "• ファイルパスが間違っている\n"
                    "• ポート50021が既に使用されている\n"
                    "• 依存ライブラリが不足している\n\n"
                    "ログを確認してください。"
                ))
                self.master.after(0, lambda: self.log_message("❌ VOICEVOX Engine接続テスト: 失敗"))

        threading.Thread(target=test_thread, daemon=True).start()

    def browse_voicevox_path(self):
        """VOICEVOX Engineの実行ファイルを選択"""
        file_path = filedialog.askopenfilename(
            title="VOICEVOX Engineの実行ファイルを選択（run.exe）",
            filetypes=[
                ("実行ファイル", "*.exe" if platform.system() == "Windows" else "*"),
                ("すべてのファイル", "*.*")
            ]
        )
        if file_path:
            # パスの正規化と絶対パス化
            normalized_path = os.path.normpath(file_path)
            abs_path = os.path.abspath(normalized_path)

            logger.debug(f"選択されたパス: {file_path}")
            logger.debug(f"正規化後: {normalized_path}")
            logger.debug(f"絶対パス: {abs_path}")

            self.voicevox_path.set(abs_path)

            # VOICEVOXマネージャーのパスも更新
            if hasattr(self, 'voicevox_manager'):
                self.voicevox_manager.engine_path = abs_path

            # 選択されたファイルを検証
            if os.path.exists(abs_path):
                # ファイル名のチェック
                file_name = os.path.basename(abs_path)
                if file_name.lower() == "run.exe":
                    self.log_message(f"✅ VOICEVOX Engineパスを設定しました: {abs_path}")
                else:
                    self.log_message(f"⚠️ 警告: ファイル名が run.exe ではありません: {file_name}")
                    self.log_message(f"設定されたパス: {abs_path}")
                    self.log_message("正しいファイルを選択しているか確認してください")

                # ドライブレターの確認（デバッグ用）
                if platform.system() == "Windows":
                    drive = os.path.splitdrive(abs_path)[0]
                    self.log_message(f"ドライブ: {drive if drive else 'なし'}")

            else:
                self.log_message(f"❌ 選択されたファイルが見つかりません: {abs_path}")
                self.log_message(f"元のパス: {file_path}")

    def _setup_auto_save(self):
        """設定変更を自動保存するためのトレースを設定"""
        watch_vars = [
            self.client_id,
            self.deepl_key,
            self.gladia_key,
            self.voicevox_path,
            self.voicevox_auto_start,
            self.channel,
            self.lang_mode,
            self.bits_sound_path,
            self.sub_sound_path,
            self.comment_bg,
            self.comment_fg,
            self.comment_font,
            self.comment_bubble_style,
            self.chat_html_output,
            self.chat_html_path,
        ]
        for var in watch_vars:
            try:
                var.trace_add("write", lambda *args: self._auto_save_settings())
            except Exception as e:
                logger.debug(f"Failed to trace var for auto-save: {e}")

    def _auto_save_settings(self):
        """config.jsonへサイレント保存"""
        try:
            self.config["twitch_client_id"] = self.client_id.get().strip()
            self.config["deepl_api_key"] = self.deepl_key.get().strip()
            self.config["gladia_api_key"] = self.gladia_key.get().strip()
            self.config["voicevox_engine_path"] = self.voicevox_path.get().strip()
            self.config["voicevox_auto_start"] = self.voicevox_auto_start.get()
            self.config["channel_name"] = self.channel.get().strip()
            self.config["translate_mode"] = self.lang_mode.get()
            self.config["bits_sound_path"] = self.bits_sound_path.get().strip()
            self.config["subscription_sound_path"] = self.sub_sound_path.get().strip()
            self.config["comment_log_bg"] = self.comment_bg.get().strip()
            self.config["comment_log_fg"] = self.comment_fg.get().strip()
            self.config["comment_log_font"] = self.comment_font.get().strip()
            self.config["comment_bubble_style"] = self.comment_bubble_style.get()
            self.config["chat_html_output"] = self.chat_html_output.get()
            self.config["chat_html_path"] = self.chat_html_path.get().strip()
            self.config["chat_html_newest_first"] = self.chat_html_newest_first.get()

            # VOICEVOX Managerのパスを更新
            if self.voicevox_path.get().strip() and hasattr(self, "voicevox_manager"):
                self.voicevox_manager.engine_path = self.voicevox_path.get().strip()

            save_config(self.config)
            logger.debug("Config auto-saved")
        except Exception as e:
            logger.error(f"Auto-save failed: {e}", exc_info=True)

    def save_settings(self):
        self._auto_save_settings()
        messagebox.showinfo("保存完了", "設定を config.json に保存しました。")
        # 使用状況表示を更新
        self._update_gladia_usage_display()

    def _update_gladia_usage_display(self):
        """Gladia使用状況の表示を更新"""
        usage_sec = self.config.get("gladia_usage_seconds", 0)
        usage_hours = usage_sec / 3600
        remaining_hours = 10 - usage_hours
        usage_text = f"今月の使用: {usage_hours:.2f}h / 10h (残り: {remaining_hours:.2f}h)"
        provider = self.config.get("stt_provider", "gladia")
        provider_text = "Gladia" if provider == "gladia" else "Google SR"

        if hasattr(self, 'gladia_usage_label'):
            self.gladia_usage_label.configure(text=f"{usage_text}\n現在のプロバイダー: {provider_text}")

    def _set_status(self, text: str, tone: str = "info"):
        """ヘッダーのステータス表示を更新"""
        color_map = {
            "info": TEXT_SUBTLE,
            "success": ACCENT,
            "warn": ACCENT_WARN,
            "error": "#EF4444"
        }

        def _apply():
            if hasattr(self, "status_label"):
                self.status_label.configure(text=text, text_color=color_map.get(tone, TEXT_SUBTLE))

        self.master.after(0, _apply)

    def _update_stats_display(self):
        """翻訳統計ラベルを更新"""
        try:
            stats = translator.get_stats()
            msg = f"翻訳統計: {stats.get('requests',0)} req / {stats.get('cache_hits',0)} hit / {stats.get('filtered',0)} filtered"
            if hasattr(self, "stats_label"):
                self.stats_label.configure(text=msg)
        except Exception as e:
            logger.debug(f"Failed to update stats: {e}")
        finally:
            self.master.after(2000, self._update_stats_display)

    def log_message(self, msg, log_type="info", comment_data=None):
        """
        ログメッセージを表示し、履歴に記録

        Args:
            msg: ログメッセージ
            log_type: ログタイプ ("info", "chat", "voice", "system", "error")
            comment_data: CommentDataオブジェクト（コメントの場合）
        """
        # システムログに表示（時刻付き）
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {msg}\n"

        if hasattr(self, 'log'):
            self.log.insert("end", log_line)
            self.log.see("end")

        # 履歴に記録
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": log_type,
            "message": msg
        }

        # CommentDataがある場合は追加情報を記録
        if comment_data:
            log_entry["comment_data"] = comment_data.to_dict()

        self.log_history.append(log_entry)

        # チャット履歴への反映（チャット/ボイス、またはCommentDataがあるとき）
        if log_type in ("chat", "voice") or comment_data:
            entry = {
                "name": comment_data.display_username if comment_data else "System",
                "message": comment_data.message if comment_data else msg,
                "translated": getattr(comment_data, "translated", None),
                "time": timestamp
            }
            self.chat_history.append(entry)
            if len(self.chat_history) > 200:
                self.chat_history.pop(0)
            if self.chat_html_output.get():
                self._export_chat_html()

    def _apply_log_style(self, textbox):
        try:
            textbox.configure(
                fg_color=self.comment_bg.get(),
                text_color=self.comment_fg.get(),
                font=self.comment_font.get()
            )
        except Exception as e:
            logger.debug(f"Failed to apply log style: {e}")

    def _append_chat_history(self, comment: CommentData):
        entry = {
            "name": comment.display_username,
            "message": comment.message,
            "translated": comment.translated,
            "time": comment.formatted_timestamp
        }
        self.chat_history.append(entry)
        if len(self.chat_history) > 100:
            self.chat_history.pop(0)

    def _get_icon_path(self) -> str:
        """アイコンファイルのパスを取得（PyInstallerビルド対応）"""
        import sys
        if getattr(sys, 'frozen', False):
            # PyInstallerでビルドされた場合
            base_path = sys._MEIPASS
        else:
            # 開発環境の場合
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        icon_path = os.path.join(base_path, "assets", "icon.png")
        return icon_path

    def _setup_window_icon(self):
        """ウィンドウアイコンを設定"""
        try:
            import sys
            import platform

            icon_path = self._get_icon_path()
            logger.info(f"アイコンパス: {icon_path}")
            logger.info(f"アイコンファイル存在: {os.path.exists(icon_path)}")

            if icon_path and os.path.exists(icon_path):
                # Windowsの場合はiconbitmap()を使用（より確実）
                if platform.system() == 'Windows':
                    # .icoファイルのパスを生成
                    icon_dir = os.path.dirname(icon_path)
                    ico_path = os.path.join(icon_dir, "icon.ico")

                    # .icoファイルが存在しない、または古い場合は再生成
                    if not os.path.exists(ico_path) or os.path.getmtime(icon_path) > os.path.getmtime(ico_path):
                        from PIL import Image
                        logger.info("マルチサイズ.icoファイルを生成中...")

                        # PNGからマルチサイズの.icoを生成
                        img = Image.open(icon_path)
                        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                        img.save(ico_path, format='ICO', sizes=icon_sizes)
                        logger.info(f".icoファイルを生成しました: {ico_path}")

                    # iconbitmap()で設定
                    self.master.iconbitmap(ico_path)
                    logger.info(f"ウィンドウアイコンを設定しました (iconbitmap): {ico_path}")
                else:
                    # Linux/Mac の場合は iconphoto() を使用
                    from PIL import Image, ImageTk

                    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                    photo_images = []

                    for size in icon_sizes:
                        pil_image = Image.open(icon_path)
                        pil_image = pil_image.resize(size, Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(pil_image)
                        photo_images.append(photo)

                    self.master.iconphoto(True, *photo_images)
                    self.master._icon_photos = photo_images
                    logger.info("ウィンドウアイコンを設定しました (iconphoto)")
            else:
                logger.warning(f"アイコンファイルが見つかりません: {icon_path}")
        except Exception as e:
            logger.error(f"アイコンの設定に失敗しました: {e}", exc_info=True)

    def _default_chat_html_path(self, current: str) -> str:
        if current:
            return current
        appdata = os.environ.get("APPDATA")
        if appdata:
            return os.path.join(appdata, "Kototsuna", "templates", "chat", "index.html")
        return os.path.join(os.getcwd(), "chat_output.html")

    def _export_chat_html(self, force=False):
        """
        チャットHTMLをファイルに書き出す

        Args:
            force: Trueの場合、トグルの状態に関わらず強制的にエクスポート
        """
        if not force and not self.chat_html_output.get():
            return

        path = self.chat_html_path.get().strip() or self._default_chat_html_path("")
        try:
            # ディレクトリを作成（存在しない場合）
            dir_path = os.path.dirname(path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logger.debug(f"Created directory: {dir_path}")

            # HTMLファイルを書き出し
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._build_chat_html())
            logger.debug(f"Chat HTML exported to {path}")
        except Exception as e:
            logger.error(f"Failed to export chat HTML: {e}", exc_info=True)
            self.log_message(f"⚠️ チャットHTMLの書き出しに失敗しました: {e}", log_type="error")

    def _get_css_style(self, style_name):
        bg = self.comment_bg.get()
        fg = self.comment_fg.get()
        font = self.comment_font.get() or "Consolas, monospace"
        
        # 基本スタイル
        base = f"""
            body {{ margin:0; padding:12px; background-color:{bg}; color:{fg}; font-family:{font}; font-size:14px; overflow-x: hidden; word-wrap: break-word; }}
            .msg {{ margin-bottom:12px; animation: fadein 0.3s; display: flex; flex-direction: column; }}
            .meta {{ display: flex; align-items: baseline; margin-bottom: 4px; font-size: 0.85em; opacity: 0.8; }}
            .time {{ margin-right: 8px; font-size: 0.9em; }}
            .name {{ font-weight: bold; }}
            .content {{ display: flex; flex-direction: column; }}
            .body {{ line-height: 1.4; }}
            .sub {{ font-size: 0.9em; opacity: 0.8; margin-top: 2px; }}
            @keyframes fadein {{ from {{ opacity:0; transform:translateY(5px); }} to {{ opacity:1; transform:translateY(0); }} }}
        """

        if style_name == "modern":
            return base + """
                /* Modern (Overlay Friendly) */
                .msg { 
                    background: rgba(20, 20, 30, 0.9); 
                    border-radius: 8px; 
                    border-left: 4px solid #22c55e;
                    padding: 10px 14px; 
                    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                    animation: slideIn 0.3s;
                }
                .meta { border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 4px; margin-bottom: 6px; }
                .name { color: #4ade80; font-weight: bold; }
                .time { color: #94a3b8; font-size: 0.8em; }
                .body { color: #f1f5f9; font-size: 1.05em; }
                .sub { 
                    margin-top: 6px; padding-top: 4px; 
                    border-top: 1px dashed rgba(255,255,255,0.15); 
                    color: #94a3b8; font-size: 0.9em; 
                }
            """
        elif style_name == "box":
            return base + """
                .msg { background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); padding: 10px; border-radius: 4px; animation: fadein 0.3s; }
                .meta { margin-bottom: 4px; font-size: 0.9em; color: #aaa; }
                .name { color: #88c0d0; font-weight: bold; margin-right: 8px; }
                .sub { color: #81a1c1; font-size: 0.9em; border-top: 1px solid rgba(255,255,255,0.1); margin-top: 6px; padding-top: 4px; }
            """
        elif style_name == "bubble":
            return base + """
                .msg { display: flex; flex-direction: column; align-items: flex-start; margin-bottom: 16px; animation: slideIn 0.3s; }
                .meta { font-size: 0.8em; color: #888; margin-left: 8px; margin-bottom: 2px; }
                .name { font-weight: bold; color: #444; }
                .content { display: flex; flex-direction: column; align-items: flex-start; max-width: 90%; }
                .body { 
                    background: #ffffff; color: #333; padding: 10px 14px; 
                    border-radius: 18px; border-top-left-radius: 4px; 
                    box-shadow: 0 1px 3px rgba(0,0,0,0.15);
                    position: relative;
                }
                .sub { 
                    background: #f0f4f8; color: #555; padding: 6px 12px; 
                    border-radius: 12px; margin-top: 4px; margin-left: 4px;
                    font-size: 0.85em; border: 1px solid #e1e8ed;
                }
            """
        elif style_name == "cute":
            return base + """
                body { background-color: transparent; color: #5d4037; }
                .msg { 
                    background: #fff; border: 2px solid #ffb7b2; 
                    border-radius: 15px; padding: 12px; 
                    box-shadow: 3px 3px 0px rgba(255, 183, 178, 0.5); 
                    margin-bottom: 14px; animation: fadein 0.4s;
                }
                .meta { border-bottom: 1px dashed #ffb7b2; padding-bottom: 4px; margin-bottom: 6px; }
                .name { color: #ec407a; font-weight: bold; }
                .time { color: #999; font-size: 0.8em; }
                .body { font-size: 1.05em; line-height: 1.5; color: #4e342e; }
                .sub { 
                    background: #fff9c4; color: #d81b60; 
                    padding: 5px 10px; border-radius: 10px; 
                    margin-top: 6px; font-size: 0.9em; 
                }
            """
        elif style_name == "neon":
            return base + """
                body { background-color: #000; color: #fff; text-shadow: 0 0 2px #fff; }
                .msg { 
                    background: rgba(0, 20, 0, 0.3); border: 1px solid #0f0; 
                    padding: 10px; box-shadow: 0 0 8px rgba(0, 255, 0, 0.3); 
                    border-radius: 6px; animation: fadein 0.2s;
                }
                .meta { color: #0f0; font-size: 0.9em; margin-bottom: 4px; border-bottom: 1px solid rgba(0,255,0,0.3); padding-bottom: 2px; }
                .name { font-weight: bold; }
                .sub { color: #0ff; text-shadow: 0 0 3px #0ff; margin-top: 6px; font-size: 0.9em; }
            """
        else: # classic / minimal
            return base + """
                .msg { border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; }
                .sub { color: #88c0d0; margin-left: 10px; }
            """

    def _build_chat_html(self) -> str:
        style_name = self.comment_bubble_style.get()
        css = self._get_css_style(style_name)

        # テンプレート読み込み (custom.css)
        try:
            # HTML出力先と同じフォルダの custom.css を探す
            output_dir = os.path.dirname(self.chat_html_path.get() or self._default_chat_html_path(""))
            custom_css_path = os.path.join(output_dir, "custom.css")
            if os.path.exists(custom_css_path):
                with open(custom_css_path, "r", encoding="utf-8") as f:
                    css += "\n/* Custom CSS */\n" + f.read()
        except Exception as e:
            logger.error(f"Failed to load custom.css: {e}")

        # コメントの表示順序を設定に応じて変更
        chat_list = list(self.chat_history)
        newest_first = self.chat_html_newest_first.get()
        if newest_first:
            chat_list.reverse()  # 上が新しい（逆順）

        items = []
        for c in chat_list:
            # HTMLエスケープ（簡易）
            name = str(c['name']).replace("<", "&lt;").replace(">", "&gt;")
            message = str(c['message']).replace("<", "&lt;").replace(">", "&gt;")
            translated = str(c['translated']).replace("<", "&lt;").replace(">", "&gt;") if c.get("translated") else ""

            sub_html = f"<div class='sub'>{translated}</div>" if translated else ""

            # ユニークなIDを生成（時刻 + 名前で識別）
            msg_id = f"{c['time']}-{name}".replace(" ", "-").replace(":", "-")

            line = f"""
            <div class='msg' data-id='{msg_id}'>
                <div class='meta'>
                    <span class='time'>{c['time']}</span>
                    <span class='name'>{name}</span>
                </div>
                <div class='content'>
                    <div class='body'>{message}</div>
                    {sub_html}
                </div>
            </div>
            """
            items.append(line)

        body = "\n".join(items)

        # スクロール位置の設定（上が新しい場合は上に、下が新しい場合は下に）
        scroll_script = "window.scrollTo(0, 0);" if newest_first else "window.scrollTo(0, document.body.scrollHeight);"

        # JavaScriptで点滅を最小化：既存のメッセージはそのまま、新しいメッセージだけを追加
        js_code = f"""
let lastUpdateTime = 0;
let updateInterval = null;

function updateChat() {{
    fetch(window.location.href + '?t=' + Date.now())
        .then(response => response.text())
        .then(html => {{
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newMessages = doc.querySelectorAll('.msg');
            const existingIds = new Set(
                Array.from(document.querySelectorAll('.msg')).map(m => m.dataset.id)
            );

            // 新しいメッセージを検出して追加
            let hasNewMessages = false;
            newMessages.forEach(msg => {{
                if (!existingIds.has(msg.dataset.id)) {{
                    hasNewMessages = true;
                }}
            }});

            // 変更があった場合のみ更新（点滅を最小化）
            if (hasNewMessages || newMessages.length !== existingIds.size) {{
                document.body.innerHTML = doc.body.innerHTML;
                {scroll_script}
            }}
        }})
        .catch(err => console.error('Update failed:', err));
}}

window.onload = function() {{
    {scroll_script}
    // 1.2秒ごとに更新
    updateInterval = setInterval(updateChat, 1200);
}};
"""

        return f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><style>
{css}
</style>
<script>
{js_code}
</script>
</head><body>{body}</body></html>"""

    def open_chat_html_in_browser(self):
        """チャットHTMLを既定のブラウザで開く"""
        path = self.chat_html_path.get().strip() or self._default_chat_html_path("")

        # HTMLファイルを強制的に生成
        try:
            self._export_chat_html(force=True)
        except Exception as e:
            logger.error(f"Failed to export HTML: {e}", exc_info=True)
            self.log_message(f"❌ HTMLファイルの作成に失敗しました: {e}")
            return

        if not os.path.exists(path):
            self.log_message(f"❌ HTMLファイルが見つかりません: {path}")
            return

        try:
            import webbrowser
            # ファイルパスをURIに変換
            url = f"file://{os.path.abspath(path)}"
            webbrowser.open(url)
            self.log_message(f"🌐 ブラウザで開きました: {path}")
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")
            self.log_message(f"❌ ブラウザの起動に失敗しました: {e}")

    def _on_qt_window_closed(self):
        """PyQt6ウィンドウが×で閉じられた時の処理"""
        # ウィンドウを破棄
        if self.qt_html_window:
            try:
                self.qt_html_window.close()
            except:
                pass
            self.qt_html_window = None

        # トグルスイッチをOFFにする
        if self.chat_html_output.get():
            self.chat_html_output.set(False)
            self._auto_save_settings()

        self.log_message("📄 チャットHTMLビューを閉じました")

    def _on_tkinter_window_closed(self):
        """Tkinterウィンドウが×で閉じられた時の処理"""
        # ウィンドウを破棄
        if hasattr(self, 'chat_html_window') and self.chat_html_window:
            try:
                self.chat_html_window.destroy()
            except:
                pass
            self.chat_html_window = None

        # トグルスイッチをOFFにする
        if self.chat_html_output.get():
            self.chat_html_output.set(False)
            self._auto_save_settings()

        self.log_message("📄 チャットHTMLビューを閉じました")

    def _on_chat_html_window_close(self):
        """チャットHTMLウィンドウが閉じられた時の処理（プログラムから呼ばれる）"""
        # PyQt6ウィンドウを破棄
        if self.qt_html_window:
            try:
                self.qt_html_window.close()
            except:
                pass
            self.qt_html_window = None

        # Tkinterウィンドウを破棄
        if hasattr(self, 'chat_html_window') and self.chat_html_window:
            try:
                if self.chat_html_window.winfo_exists():
                    self.chat_html_window.destroy()
            except:
                pass
            self.chat_html_window = None

    def toggle_chat_html_output(self):
        """HTML出力スイッチ用"""
        self._auto_save_settings()
        if self.chat_html_output.get():
            # ウィンドウを開く（内部でHTMLファイルを強制生成）
            self._open_chat_html_window()
        else:
            # スイッチオフ時はウィンドウを閉じる
            self._on_chat_html_window_close()

    def _open_chat_html_window(self):
        """チャットHTMLを専用ウィンドウで開く（配信用縦長サイズ）"""
        path = self.chat_html_path.get().strip() or self._default_chat_html_path("")

        # HTMLファイルを強制的に生成（ファイルが存在しない場合や空のチャット履歴でも）
        try:
            self._export_chat_html(force=True)
        except Exception as e:
            logger.error(f"Failed to export HTML before opening window: {e}", exc_info=True)
            self.log_message(f"❌ HTMLファイルの作成に失敗しました: {e}")
            return

        # ファイルが確実に存在することを確認
        if not os.path.exists(path):
            logger.error(f"HTML file does not exist after export: {path}")
            self.log_message(f"❌ HTMLファイルが見つかりません: {path}")
            return

        # 既存のウィンドウがあれば閉じる
        if self.qt_html_window is not None:
            try:
                self.qt_html_window.close()
                self.qt_html_window = None
            except:
                pass

        if hasattr(self, 'chat_html_window') and self.chat_html_window and self.chat_html_window.winfo_exists():
            self.chat_html_window.destroy()
            self.chat_html_window = None

        # PyQt6ウィンドウで開く（完全なChromiumブラウザエンジン）
        try:
            self._open_chat_html_window_pyqt(path)
        except ImportError:
            logger.info("PyQt6 not available, falling back to tkinterweb")
            self._open_chat_html_window_tkinter(path)
        except Exception as e:
            logger.error(f"Failed to open with PyQt6: {e}", exc_info=True)
            self._open_chat_html_window_tkinter(path)

    def _open_chat_html_window_pyqt(self, path):
        """PyQt6のQWebEngineViewを使用してHTMLを表示（完全なChromiumブラウザエンジン）"""
        # ファイルの存在を再確認
        if not os.path.exists(path):
            raise FileNotFoundError(f"HTML file not found: {path}")

        from PyQt6.QtWidgets import QApplication, QMainWindow
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtCore import QUrl, QTimer
        from PyQt6.QtGui import QIcon
        import sys

        # QApplicationインスタンスを取得または作成
        if not QApplication.instance():
            self.qt_app = QApplication(sys.argv)
        else:
            self.qt_app = QApplication.instance()

        # HTMLビューウィンドウクラス
        class HtmlViewerWindow(QMainWindow):
            def __init__(self, html_path, parent_gui):
                super().__init__()
                self.html_path = html_path
                self.parent_gui = parent_gui
                self.setWindowTitle("チャット - 配信用")
                self.setGeometry(50, 50, 350, 900)

                # 常に最前面に表示
                self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

                # WebEngineViewを作成
                self.browser = QWebEngineView()
                self.setCentralWidget(self.browser)

                # HTMLを読み込む（初回のみ、以降はJavaScriptで自動更新）
                abs_path = os.path.abspath(self.html_path)
                file_url = QUrl.fromLocalFile(abs_path)

                # デバッグ用：URLをログ出力
                logger.debug(f"Loading HTML from: {abs_path}")
                logger.debug(f"File URL: {file_url.toString()}")

                self.browser.setUrl(file_url)

            def closeEvent(self, event):
                """ウィンドウが閉じられたときの処理"""
                # 親GUIのトグルスイッチをOFFにする
                if self.parent_gui and self.parent_gui.chat_html_output.get():
                    self.parent_gui.master.after(0, self.parent_gui._on_qt_window_closed)
                event.accept()

        # Qt WindowFlagsをインポート
        from PyQt6.QtCore import Qt

        # ウィンドウを作成
        self.qt_html_window = HtmlViewerWindow(path, self)
        self.qt_html_window.show()

        # Qt のイベントループを別スレッドで処理
        def process_qt_events():
            """Qtのイベントを定期的に処理"""
            if self.qt_app and self.qt_html_window:
                self.qt_app.processEvents()
                # 100msごとに再度呼び出す
                self.master.after(100, process_qt_events)

        # イベント処理を開始
        self.master.after(100, process_qt_events)

        self.log_message(f"📄 チャットHTMLビューを開きました (Chromiumエンジン) - {path}")

    def _open_chat_html_window_tkinter(self, path):
        """Tkinterベースのフォールバック表示（tkinterweb or シンプルテキスト）"""
        # 新しいウィンドウを作成
        self.chat_html_window = tk.Toplevel(self.master)
        self.chat_html_window.title("チャット - 配信用")
        self.chat_html_window.geometry("350x900+50+50")
        self.chat_html_window.configure(bg="#1a1a1a")

        # ウィンドウを常に最前面に表示（配信用）
        self.chat_html_window.attributes('-topmost', True)

        # 閉じるボタンの動作を設定（×ボタンで閉じたときにトグルもOFFにする）
        self.chat_html_window.protocol("WM_DELETE_WINDOW", self._on_tkinter_window_closed)

        try:
            # tkinterwebを試す
            from tkinterweb import HtmlFrame
            frame = HtmlFrame(self.chat_html_window, messages_enabled=False)
            frame.pack(fill="both", expand=True)

            # HTMLを読み込む
            def load_html():
                try:
                    if os.path.exists(path):
                        frame.load_file(path)
                except Exception as e:
                    logger.debug(f"Error loading HTML in tkinterweb: {e}")

            load_html()

            # 1.2秒ごとに更新
            def refresh():
                if self.chat_html_window and self.chat_html_window.winfo_exists():
                    load_html()
                    self.chat_html_window.after(1200, refresh)

            self.chat_html_window.after(1200, refresh)
            self.log_message("📄 チャットHTMLビューを開きました (tkinterweb)")

        except ImportError:
            # tkinterwebがない場合、シンプルなTextウィジェットで表示
            logger.info("tkinterweb not available, using simple text display")

            # スクロール可能なテキストウィジェット
            scrollbar = tk.Scrollbar(self.chat_html_window)
            scrollbar.pack(side="right", fill="y")

            text_widget = tk.Text(
                self.chat_html_window,
                bg="#1a1a1a",
                fg="#e0e0e0",
                font=("Segoe UI", 11),
                wrap="word",
                yscrollcommand=scrollbar.set,
                relief="flat",
                padx=10,
                pady=10
            )
            text_widget.pack(fill="both", expand=True)
            scrollbar.config(command=text_widget.yview)

            # HTMLファイルを読み込んで簡易表示
            def load_and_display():
                try:
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # HTMLタグを除去してテキストのみ表示（簡易版）
                        import re
                        # スタイルとスクリプトタグを削除
                        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
                        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
                        # HTMLタグを削除
                        content = re.sub(r'<[^>]+>', '', content)
                        # HTML エンティティをデコード
                        content = content.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

                        text_widget.config(state="normal")
                        text_widget.delete("1.0", "end")
                        
                        # 注釈を追加
                        note = "【⚠ 簡易プレビューモード】\nここにはデザイン（CSS）は適用されません。\n正しい表示を確認するには、設定タブの「🌐 ブラウザで確認」ボタンを押してください。\n\n" + ("-"*50) + "\n\n"
                        
                        text_widget.insert("1.0", note + content)
                        text_widget.config(state="disabled")

                        # 自動スクロール
                        text_widget.see("end")
                except Exception as e:
                    logger.error(f"Error loading HTML: {e}")

            load_and_display()

            # 1.2秒ごとに更新
            def refresh_text():
                if self.chat_html_window and self.chat_html_window.winfo_exists():
                    load_and_display()
                    self.chat_html_window.after(1200, refresh_text)

            self.chat_html_window.after(1200, refresh_text)
            self.log_message("📄 チャットHTMLビューを開きました (シンプル表示)")

        except Exception as e:
            logger.error(f"Failed to open chat HTML window: {e}", exc_info=True)
            
            # エラー詳細をログファイルに出力（デバッグ用）
            try:
                import traceback
                with open("html_preview_error.log", "w", encoding="utf-8") as f:
                    f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                    f.write(f"Error: {e}\n\n")
                    traceback.print_exc(file=f)
            except Exception:
                pass

            if hasattr(self, 'chat_html_window') and self.chat_html_window:
                self.chat_html_window.destroy()
            self.log_message(f"❌ チャットHTMLビューの表示に失敗しました: {e}")



    def _add_comment_tile(self, comment: CommentData):
        """コメントをタイル形式で表示"""
        if not hasattr(self, "comment_tile_frame"):
            logger.error("comment_tile_frame not initialized yet!")
            return

        if not self.comment_tile_frame:
            logger.error("comment_tile_frame is None!")
            return

        try:
            style = self.comment_bubble_style.get()
            if style == "bubble":
                tile_bg = "#1b2b44"
                border = "#38BDF8"
                radius = 18
            elif style == "minimal":
                tile_bg = "#0E1728"
                border = "#1F2C43"
                radius = 8
            else:  # classic
                tile_bg = "#2B3544"
                border = "#3F4E5F"
                radius = 12

            tile = ctk.CTkFrame(
                self.comment_tile_frame,
                fg_color=tile_bg,
                corner_radius=radius,
                border_width=1,
                border_color=border
            )

            # 上段: アイコン + 内容
            header = ctk.CTkFrame(tile, fg_color="transparent")
            header.pack(fill="x", padx=6, pady=(6, 4))

            # アイコンの代わりにカラーサークル + イニシャル
            avatar_color = comment.color if comment.color else "#5B7C99"
            initials = (comment.display_username[:2] or "?").upper()
            avatar = ctk.CTkFrame(
                header,
                width=32,
                height=32,
                corner_radius=16,
                fg_color=avatar_color,
                border_width=2,
                border_color="#FFFFFF"
            )
            avatar.pack(side="left")
            avatar.pack_propagate(False)
            ctk.CTkLabel(
                avatar,
                text=initials,
                font=("Arial", 13, "bold"),
                text_color="#FFFFFF"
            ).pack(expand=True, fill="both")

            info = ctk.CTkFrame(header, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=(8, 0))

            # 1行目: 名前 + バッジ + プラットフォームチップ
            top_line = ctk.CTkFrame(info, fg_color="transparent")
            top_line.pack(fill="x", pady=(0, 1))

            name_line = f"{comment.display_username} {comment.badge_text}" if comment.badge_text else comment.display_username
            username_color = comment.color if comment.color else "#E8F0FF"
            ctk.CTkLabel(
                top_line,
                text=name_line,
                anchor="w",
                justify="left",
                font=("Arial", 13, "bold"),
                text_color=username_color
            ).pack(side="left", anchor="w")

            platform_chip = ctk.CTkLabel(
                top_line,
                text=comment.platform_name,
                fg_color="#5B7C99",
                corner_radius=10,
                font=("Arial", 10, "bold"),
                text_color="#FFFFFF",
                width=60
            )
            platform_chip.pack(side="right", padx=(6, 0))

            # 2行目: 時刻 + メッセージ（同じ行で詰める）
            meta_and_msg = ctk.CTkFrame(info, fg_color="transparent")
            meta_and_msg.pack(fill="x")

            ctk.CTkLabel(
                meta_and_msg,
                text=comment.formatted_timestamp,
                anchor="w",
                font=("Arial", 11),
                text_color="#B0BEC5",
                width=70
            ).pack(side="left", padx=(0, 6))

            ctk.CTkLabel(
                meta_and_msg,
                text=comment.message,
                anchor="w",
                justify="left",
                wraplength=420,
                font=("Arial", 13),
                text_color="#FFFFFF"
            ).pack(side="left", fill="x", expand=True)

            # 翻訳結果（明るい青色）
            if comment.translated:
                ctk.CTkLabel(
                    info,
                    text=f"↳ {comment.translated}",
                    anchor="w",
                    justify="left",
                    wraplength=420,
                    font=("Arial", 13),
                    text_color="#B3D4FF"
                ).pack(fill="x", pady=(3, 1))

            tile.pack(fill="x", padx=6, pady=3)

            # 末尾へスクロール
            try:
                self.comment_tile_frame.after(
                    10, lambda: self.comment_tile_frame._parent_canvas.yview_moveto(1.0)
                )
            except Exception:
                pass

            self.comment_tiles.append(tile)
            if len(self.comment_tiles) > self.comment_tile_limit:
                oldest = self.comment_tiles.pop(0)
                oldest.destroy()

            logger.debug(f"Comment tile added: {comment.display_username}")

        except Exception as e:
            logger.error(f"Failed to add comment tile: {e}", exc_info=True)
            self.log_message("⚠️ コメントタイルの描画に失敗しました。ログを確認してください。", log_type="error")

    def on_comment_received(self, comment: CommentData):
        """
        コメントを受信した時の処理（拡張表示）

        Args:
            comment: CommentDataオブジェクト
        """
        def _update_ui():
            # 拡張フォーマットでログに表示
            badge_str = f"{comment.badge_text} " if comment.badge_text else ""
            msg = f"[{comment.formatted_timestamp}] [{comment.platform_name}] {badge_str}{comment.display_username}: {comment.message}"
            if comment.translated:
                msg += f"\n    ➡ {comment.translated}"

            # 通常コメントログに追加
            self.log_message(msg, log_type="chat", comment_data=comment)
            self._add_comment_tile(comment)

            # 特別イベントの検出（サブスクライバー、モデレーター、VIP）
            if comment.is_subscriber or comment.is_moderator or comment.is_vip:
                event_type = []
                if comment.is_subscriber:
                    event_type.append("サブスク")
                if comment.is_moderator:
                    event_type.append("モデレーター")
                if comment.is_vip:
                    event_type.append("VIP")
                event_msg = f"{comment.display_username} ({', '.join(event_type)})"
                self.log_special_event(event_msg, "badge")

            # オーバーレイ更新
        if comment.translated:
            update_translation(comment.translated)

        # UI操作はメインスレッドに投げる
        self.master.after(0, _update_ui)

    def log_special_event(self, message: str, event_type: str = "other"):
        """
        特別イベントをログに記録

        Args:
            message: イベントメッセージ
            event_type: イベントタイプ ("superchat", "subscription", "badge", "bits", "other")
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        # イベントタイプに応じたアイコン
        icons = {
            "superchat": "💰",
            "subscription": "⭐",
            "badge": "🎖️",
            "bits": "💎",
            "other": "📢"
        }
        icon = icons.get(event_type, "📢")

        event_msg = f"[{timestamp}] {icon} {message}\n"

        # 特別イベントログに表示
        if hasattr(self, 'event_log'):
            self.event_log.insert("end", event_msg)
            self.event_log.see("end")

        # メインログにも記録（履歴用）
        self.log_message(f"[特別イベント] {message}", log_type="event")

        # 効果音（TTSの前に再生）
        if event_type in ("bits", "subscription"):
            self.play_event_sound(event_type)

        # 特別イベントの読み上げ（常にON）
        if True:
            try:
                # イベントタイプに応じた読み上げメッセージを作成
                tts_messages = {
                    "superchat": f"スーパーチャット、{message}",
                    "subscription": f"サブスクリプション、{message}",
                    "bits": f"ビッツ、{message}",
                    "badge": f"バッジ獲得、{message}",
                    "other": f"イベント、{message}"
                }
                tts_msg = tts_messages.get(event_type, message)
                self.tts.speak(tts_msg)
                logger.debug(f"Special event TTS: {tts_msg}")
            except Exception as e:
                logger.error(f"Failed to speak special event: {e}", exc_info=True)

    def select_event_sound(self, event_type: str):
        """効果音ファイルを選択"""
        file_path = filedialog.askopenfilename(
            title="効果音ファイルを選択",
            filetypes=[
                ("Audio files", "*.mp3 *.wav *.ogg"),
                ("All files", "*.*")
            ]
        )
        if not file_path:
            return

        if event_type == "bits":
            self.bits_sound_path.set(file_path)
        elif event_type == "subscription":
            self.sub_sound_path.set(file_path)

    def play_event_sound(self, event_type: str):
        """設定された効果音を再生（存在チェック込み）"""
        if not PYGAME_AVAILABLE:
            logger.warning("pygameが利用できないため効果音を再生できません")
            return

        path = ""
        if event_type == "bits":
            path = self.bits_sound_path.get().strip()
        elif event_type == "subscription":
            path = self.sub_sound_path.get().strip()

        if not path:
            logger.debug(f"効果音未設定のためスキップ ({event_type})")
            return

        if not os.path.exists(path):
            logger.warning(f"効果音ファイルが見つかりません: {path}")
            return

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            sound = pygame.mixer.Sound(path)
            sound.play()
            logger.debug(f"Played event SFX ({event_type}): {path}")
        except Exception as e:
            logger.error(f"効果音の再生に失敗しました ({event_type}): {e}", exc_info=True)

    def start_participant_auto_refresh(self):
        """参加者リストの自動更新を開始（3秒ごと）"""
        self.refresh_main_participant_list()
        # 3秒後に再度実行
        self.participant_refresh_timer = self.master.after(3000, self.start_participant_auto_refresh)

    def refresh_main_participant_list(self):
        """メイン画面の参加者リストを更新"""
        if not hasattr(self, 'main_participant_list'):
            return

        # trackerの初期化確認
        if not hasattr(self, 'tracker'):
            self.tracker = get_tracker()

        # 既存のウィジェットをクリア
        for widget in self.main_participant_list.winfo_children():
            widget.destroy()

        # 参加者数を更新
        count = self.tracker.get_count()
        self.main_participant_count_label.configure(text=f"({count}人)")

        # 参加者を表示
        participants = self.tracker.get_participants()
        if not participants:
                ctk.CTkLabel(
                    self.main_participant_list,
                    text="参加者なし",
                    text_color="gray",
                    font=("Arial", 13, "bold")
                ).pack(pady=6)
        else:
            for i, participant in enumerate(participants, 1):
                username = participant['username']
                label_text = f"{i}. {username}"

                ctk.CTkLabel(
                    self.main_participant_list,
                    text=label_text,
                    font=("Arial", 14, "bold"),
                    anchor="w"
                ).pack(fill="x", padx=6, pady=2)

    def export_log_text(self):
        """ログをテキスト形式で出力"""
        if not self.log_history:
            messagebox.showwarning("警告", "ログが空です。")
            return

        # ファイル保存ダイアログ
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"chatlog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("=" * 60 + "\n")
                f.write("ことつな！ - Chat Log Export\n")
                f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")

                for entry in self.log_history:
                    timestamp = entry["timestamp"]
                    log_type = entry["type"]
                    message = entry["message"]
                    f.write(f"[{timestamp}] [{log_type.upper()}] {message}\n")

            messagebox.showinfo("成功", f"ログをテキスト形式で保存しました:\n{file_path}")
            logger.info(f"Log exported to text: {file_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"ログの保存に失敗しました:\n{e}")
            logger.error(f"Failed to export log as text: {e}", exc_info=True)

    def export_log_json(self):
        """ログをJSON形式で出力"""
        if not self.log_history:
            messagebox.showwarning("警告", "ログが空です。")
            return

        # ファイル保存ダイアログ
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"chatlog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        if not file_path:
            return

        try:
            export_data = {
                "export_info": {
                    "exported_at": datetime.now().isoformat(),
                    "total_entries": len(self.log_history),
                    "channel": self.channel.get(),
                    "translate_mode": self.lang_mode.get()
                },
                "logs": self.log_history
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            messagebox.showinfo("成功", f"ログをJSON形式で保存しました:\n{file_path}")
            logger.info(f"Log exported to JSON: {file_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"ログの保存に失敗しました:\n{e}")
            logger.error(f"Failed to export log as JSON: {e}", exc_info=True)

    def clear_log(self):
        """ログをクリア"""
        result = messagebox.askyesno("確認", "ログをクリアしますか？\n（この操作は元に戻せません）")
        if result:
            self.log_history.clear()
            # システムログをクリア
            if hasattr(self, 'log'):
                self.log.delete("1.0", "end")
                self.log.insert("0.0", "--- システムログクリア ---\n")
            # タイルをクリア
            if hasattr(self, "comment_tiles"):
                for tile in self.comment_tiles:
                    tile.destroy()
                self.comment_tiles.clear()
            logger.info("Chat log cleared by user")

    def start_auth(self):
        client_id = self.client_id.get().strip()
        if not client_id:
            messagebox.showerror("エラー", "Client ID が設定されていません。\n「設定」タブで入力してください。")
            return
        self._set_status("トークン認証を開始します。ブラウザを開いてください。", "info")
        threading.Thread(target=self.run_auth_flow, args=(client_id,), daemon=True).start()

    def _check_saved_token(self):
        """起動時に保存されたトークンをチェックして自動ログイン"""
        saved_token = self.config.get("twitch_access_token", "").strip()

        if not saved_token:
            logger.info("No saved token found.")
            return

        logger.info("Checking saved token...")
        self.log_message("🔍 保存されたトークンをチェックしています...")

        # トークンの有効性をチェック
        if validate_token(saved_token):
            self.token = saved_token
            self.log_message("✅ 保存されたトークンが有効です。自動ログインしました。")
            self._set_status("保存されたトークンで自動ログイン完了", "success")
        else:
            logger.warning("Saved token is invalid.")
            self.log_message("⚠ 保存されたトークンが無効です。再認証が必要です。")
            # 無効なトークンを削除
            self.config["twitch_access_token"] = ""
            save_config(self.config)

    def run_auth_flow(self, client_id):
        url = build_auth_url(client_id)

        self.log_message("🔗 認証ページを開きます (Chrome シークレットモード推奨)")
        self.log_message(f"URL: {url}")

        try:
            # Windows環境でChromeのシークレットモード起動を試みる
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
            ]
            
            chrome_found = False
            if platform.system() == "Windows":
                for path in chrome_paths:
                    if os.path.exists(path):
                        subprocess.Popen([path, "--incognito", url])
                        chrome_found = True
                        self.log_message("✅ Chrome (シークレットモード) で開きました")
                        break
            
            if not chrome_found:
                # Chromeが見つからない場合は既存の挙動
                if shutil.which("wslview"):
                    subprocess.Popen(["wslview", url])
                else:
                    webbrowser.open(url)
                    
        except Exception as e:
            logger.debug(f"Failed to open browser automatically: {e}")
            self.log_message("⚠ ブラウザの自動起動に失敗しました。URLをコピーして開いてください。")

        self.token = run_auth_server_and_get_token()

        if self.token:
            self.log_message("✅ トークンを取得しました")
            self._set_status("トークン取得済み。BOTを起動できます。", "success")

            # トークンをconfig.jsonに保存（次回起動時の自動ログイン用）
            self.config["twitch_access_token"] = self.token
            save_config(self.config)
            self.log_message("💾 トークンを保存しました。次回から自動ログインします。")
        else:
            self.log_message("⚠ トークンの取得に失敗しました。")
            self._set_status("トークンの取得に失敗しました。再試行してください。", "error")

    def logout(self):
        """保存されたトークンをクリアしてログアウト"""
        if not self.token and not self.config.get("twitch_access_token"):
            messagebox.showinfo("情報", "ログインしていません。")
            return

        # BOTが起動中の場合は停止
        if self.bot_instance:
            self.stop_bot()

        # トークンをクリア
        self.token = None
        self.config["twitch_access_token"] = ""
        save_config(self.config)

        self.log_message("🚪 ログアウトしました。")
        self._set_status("ログアウト完了。再度認証が必要です。", "info")
        messagebox.showinfo("ログアウト", "ログアウトしました。\n再度ログインするには「① トークン認証」を実行してください。")

    def start_bot(self):
        # 既存のBOTがあれば停止（多重起動防止）
        if self.bot_instance:
            self.stop_bot()

        if not self.token:
            messagebox.showerror("エラー", "まずは「① トークン認証」を行ってください")
            return
        
        channel = self.channel.get().strip()
        if not channel:
            messagebox.showerror("エラー", "チャンネル名を設定してください")
            return

        deepl_key = self.deepl_key.get().strip()
        if not deepl_key:
            messagebox.showwarning("警告", "DeepL API Keyが設定されていません。\n翻訳機能は動作しませんが、BOTは起動します。")

        self.bot_instance = TranslateBot(
            self.token,
            channel,
            lambda: self.lang_mode.get(),
            self,
            deepl_key,
            tts_enabled_getter=lambda: True,
            tts_include_name_getter=lambda: self.tts_include_name_var.get()
        )
        # 読み上げエンジンを先に起動しておく
        self._ensure_tts_started()
        threading.Thread(target=self.bot_instance.run, daemon=True).start()
        self.log_message(f"🤖 BOTを起動しました (Channel: {channel})")
        self._set_status(f"BOT稼働中: {channel}", "success")

    def stop_bot(self):
        if self.bot_instance:
            self.bot_instance.stop()
            self.log_message("⛔ BOTを停止しました")
            self._set_status("BOTを停止しました。認証済みです。", "warn")

        # 自動送信も停止
        if hasattr(self, 'auto_send_var') and self.auto_send_var.get():
            self.auto_send_var.set(False)
            self.stop_auto_send()
            self.log_message("⏸ 自動送信も停止しました")
            self._set_status("BOTを停止しました。", "warn")

    def cleanup_resources(self):
        """アプリケーション終了時に全てのリソースを解放"""
        logger.info("Starting cleanup_resources...")

        try:
            # リソース監視を停止
            if hasattr(self, 'resource_monitor'):
                logger.info("Stopping resource monitor...")
                self.resource_monitor.stop_monitoring()
                self.stop_resource_auto_update()
                logger.info("Resource monitor stopped.")
        except Exception as e:
            logger.error(f"Failed to stop resource monitor: {e}", exc_info=True)

        try:
            # 音声認識を停止
            logger.info("Stopping voice translator...")
            self.voice_translator.stop()
            logger.info("Voice translator stopped.")
        except Exception as e:
            logger.error(f"Failed to stop voice translator: {e}", exc_info=True)

        try:
            # Botを停止
            if self.bot_instance:
                logger.info("Disconnecting bot instance...")
                self.bot_instance.stop()
                logger.info("Bot disconnected.")
        except Exception as e:
            logger.error(f"Failed to disconnect bot: {e}", exc_info=True)

        try:
            # オーバーレイサーバーを停止
            from src.overlay_server import stop_server
            logger.info("Stopping overlay server...")
            stop_server()
            logger.info("Overlay server stopped.")
        except Exception as e:
            logger.error(f"Failed to stop overlay server: {e}", exc_info=True)

        try:
            # VOICEVOX Engineを停止
            if hasattr(self, 'voicevox_manager') and self.voicevox_manager:
                logger.info("Stopping VOICEVOX manager...")
                self.voicevox_manager.stop()
                logger.info("VOICEVOX manager stopped.")
        except Exception as e:
            logger.error(f"Failed to stop VOICEVOX manager: {e}", exc_info=True)

        logger.info("Cleanup completed.")

    def toggle_voice(self):
        logger.info(f"toggle_voice called, voice_var={self.voice_var.get()}")
        if self.voice_var.get():
            self.log_message("🎤 音声認識を開始します...")
            logger.info("Calling voice_translator.start()")
            success = self.voice_translator.start()
            logger.info(f"voice_translator.start() returned: {success}")
            if not success:
                self.voice_var.set(False)
                self.log_message("❌ マイクの起動に失敗しました (pyaudio等が不足している可能性があります)")
                self._set_status("音声認識の起動に失敗しました。", "error")
            else:
                self._set_status("音声翻訳を開始しました。", "success")
        else:
            self.voice_translator.stop()
            self.log_message("mic 音声認識を停止しました")
            self._set_status("音声翻訳を停止しました。", "info")

    def _on_translation_toggle_changed(self):
        """チャット翻訳トグルが変更されたとき"""
        enabled = self.chat_translation_enabled.get()
        self.config["chat_translation_enabled"] = enabled
        save_config(self.config)
        status = "有効" if enabled else "無効"
        self.log_message(f"チャット翻訳を{status}にしました")

    def _ensure_tts_started(self):
        """チャット読み上げを常時ONにするための起動ヘルパー"""
        if self.tts_started:
            return
        self.tts_started = True

        self.log_message("🔊 チャット読み上げを開始します...")

        auto_start = self.config.get("voicevox_auto_start", True)
        if auto_start and not self.voicevox_manager.is_running():
            self.log_message("⏳ VOICEVOX Engineを起動しています...")
            threading.Thread(
                target=self._start_voicevox_and_tts,
                daemon=True
            ).start()
            return

        self._start_tts()

    def _start_voicevox_and_tts(self):
        """VOICEVOX Engineを起動してからTTSを開始（バックグラウンドスレッド用）"""
        success = self.voicevox_manager.start()

        # UIスレッドで処理
        self.master.after(0, lambda: self._handle_voicevox_startup(success))

    def _handle_voicevox_startup(self, success: bool):
        """VOICEVOX Engine起動結果を処理"""
        if success:
            self.log_message("✅ VOICEVOX Engine の起動に成功しました")
            self._start_tts()
        else:
            voicevox_path = self.voicevox_path.get().strip()
            if not voicevox_path:
                self.log_message("⚠️ VOICEVOX Engineのパスが設定されていません")
                self.log_message("💡 設定タブで「参照...」ボタンから run.exe を選択してください")
            elif not os.path.exists(os.path.abspath(voicevox_path)):
                self.log_message(f"❌ VOICEVOX Engineが見つかりません: {voicevox_path}")
                self.log_message("💡 設定タブで正しいパスを設定してください（参照ボタン推奨）")
            else:
                self.log_message("⚠️ VOICEVOX Engine の起動に失敗しました")
                self.log_message("💡 手動でVOICEVOXを起動するか、pyttsx3で代替できます")

            self.log_message("🔄 フォールバックTTS（pyttsx3）で続行します")
            self._start_tts()

    def _start_tts(self):
        """TTS機能を開始"""
        logger.info("_start_tts() が呼ばれました")
        self.log_message("🔊 読み上げエンジンを起動しています...")

        success = self.tts.start()
        if not success:
            self.tts_started = False
            self.log_message("❌ TTSエンジンの起動に失敗しました (pygame/pyttsx3が必要です)")
            logger.error("TTS起動失敗")
        else:
            # Show which engine is being used
            if self.tts.engine_mode == 'voicevox':
                self.log_message("✅ VOICEVOX (冥鳴ひまり) で読み上げを開始しました")
                logger.info("TTS起動成功: VOICEVOX")
            elif self.tts.engine_mode == 'pyttsx3':
                self.log_message("✅ pyttsx3フォールバックエンジンで読み上げを開始しました (VOICEVOXが利用不可)")
                logger.info("TTS起動成功: pyttsx3")

    def build_dictionary_tab(self):
        """読み上げ辞書タブの構築"""
        # 辞書の取得
        self.dictionary = get_dictionary()

        # スクロール可能なフレームを作成
        scrollable_frame = ctk.CTkScrollableFrame(self.tab_dictionary, fg_color="transparent")
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # フレーム作成
        frm_dict = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        frm_dict.pack(fill="both", expand=True, padx=10, pady=10)

        # 説明ラベル
        ctk.CTkLabel(
            frm_dict,
            text="漢字の読み間違いを修正するための辞書",
            font=("Arial", 12)
        ).pack(pady=(0, 10))

        # 単語追加フレーム
        add_frame = ctk.CTkFrame(frm_dict)
        add_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(add_frame, text="単語:", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=5)
        self.dict_word_entry = ctk.CTkEntry(add_frame, placeholder_text="例: 漢字", width=150)
        self.dict_word_entry.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(add_frame, text="読み:", font=("Arial", 12)).grid(row=0, column=2, padx=5, pady=5)
        self.dict_reading_entry = ctk.CTkEntry(add_frame, placeholder_text="例: かんじ", width=150)
        self.dict_reading_entry.grid(row=0, column=3, padx=5, pady=5)

        ctk.CTkButton(
            add_frame,
            text="追加",
            command=self.add_dictionary_entry,
            width=80
        ).grid(row=0, column=4, padx=5, pady=5)

        # 辞書リストフレーム
        list_frame = ctk.CTkFrame(frm_dict)
        list_frame.pack(fill="both", expand=True)

        # スクロール可能なフレーム
        self.dict_scroll_frame = ctk.CTkScrollableFrame(list_frame, label_text="登録済み辞書")
        self.dict_scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # ボタンフレーム
        button_frame = ctk.CTkFrame(frm_dict)
        button_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(
            button_frame,
            text="辞書を更新",
            command=self.refresh_dictionary_list,
            width=120
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            button_frame,
            text="全てクリア",
            command=self.clear_dictionary,
            width=120,
            fg_color="red",
            hover_color="darkred"
        ).pack(side="left", padx=5)

        # --- 翻訳フィルター ---
        filter_frame = ctk.CTkFrame(frm_dict, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=BORDER)
        filter_frame.pack(fill="x", pady=(12, 6), padx=2)
        ctk.CTkLabel(filter_frame, text="翻訳フィルター（含まれると翻訳スキップ）", font=("Arial", 13, "bold")).pack(anchor="w", padx=10, pady=(8, 4))
        add_filter_row = ctk.CTkFrame(filter_frame, fg_color="transparent")
        add_filter_row.pack(fill="x", padx=10, pady=4)
        self.translation_filter_entry = ctk.CTkEntry(add_filter_row, placeholder_text="例: NGワード", width=220)
        self.translation_filter_entry.pack(side="left", padx=(0, 6))
        ctk.CTkButton(add_filter_row, text="追加", command=self.add_translation_filter, width=80).pack(side="left")
        self.filter_list_frame = ctk.CTkScrollableFrame(filter_frame, height=120, fg_color="transparent")
        self.filter_list_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        # --- 翻訳カスタム辞書 ---
        trans_dict_frame = ctk.CTkFrame(frm_dict, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=BORDER)
        trans_dict_frame.pack(fill="x", pady=(8, 0), padx=2)
        ctk.CTkLabel(trans_dict_frame, text="翻訳カスタム辞書（翻訳前に置換）", font=("Arial", 13, "bold")).pack(anchor="w", padx=10, pady=(8, 4))
        add_tdict_row = ctk.CTkFrame(trans_dict_frame, fg_color="transparent")
        add_tdict_row.pack(fill="x", padx=10, pady=4)
        self.translation_dict_src = ctk.CTkEntry(add_tdict_row, placeholder_text="元の文言", width=180)
        self.translation_dict_src.pack(side="left", padx=(0, 4))
        self.translation_dict_dst = ctk.CTkEntry(add_tdict_row, placeholder_text="置換後", width=180)
        self.translation_dict_dst.pack(side="left", padx=4)
        ctk.CTkButton(add_tdict_row, text="追加", command=self.add_translation_dict_entry, width=80).pack(side="left", padx=4)
        self.translation_dict_list = ctk.CTkScrollableFrame(trans_dict_frame, height=140, fg_color="transparent")
        self.translation_dict_list.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        # 初期リスト表示
        self.refresh_dictionary_list()
        self.refresh_translation_filters()
        self.refresh_translation_dict_list()

    def add_dictionary_entry(self):
        """辞書エントリを追加"""
        word = self.dict_word_entry.get().strip()
        reading = self.dict_reading_entry.get().strip()

        if not word or not reading:
            messagebox.showwarning("入力エラー", "単語と読みの両方を入力してください")
            return

        success = self.dictionary.add_word(word, reading)
        if success:
            self.log_message(f"辞書に追加: {word} → {reading}")
            self.dict_word_entry.delete(0, 'end')
            self.dict_reading_entry.delete(0, 'end')
            self.refresh_dictionary_list()
        else:
            messagebox.showerror("エラー", "辞書への追加に失敗しました")

    def refresh_dictionary_list(self):
        """辞書リストを更新"""
        # 既存のウィジェットをクリア
        for widget in self.dict_scroll_frame.winfo_children():
            widget.destroy()

        # 辞書エントリを表示
        entries = self.dictionary.get_all_entries()
        if not entries:
            ctk.CTkLabel(
                self.dict_scroll_frame,
                text="（辞書は空です）",
                text_color="gray"
            ).pack(pady=10)
        else:
            for word, reading in sorted(entries):
                entry_frame = ctk.CTkFrame(self.dict_scroll_frame)
                entry_frame.pack(fill="x", pady=2)

                ctk.CTkLabel(
                    entry_frame,
                    text=f"{word}  →  {reading}",
                    font=("Arial", 11),
                    width=300,
                    anchor="w"
                ).pack(side="left", padx=10)

                ctk.CTkButton(
                    entry_frame,
                    text="削除",
                    command=lambda w=word: self.remove_dictionary_entry(w),
                    width=60,
                    fg_color="orange",
                    hover_color="darkorange"
                ).pack(side="right", padx=5)

    def remove_dictionary_entry(self, word):
        """辞書エントリを削除"""
        success = self.dictionary.remove_word(word)
        if success:
            self.log_message(f"辞書から削除: {word}")
            self.refresh_dictionary_list()
        else:
            messagebox.showerror("エラー", "辞書からの削除に失敗しました")

    def clear_dictionary(self):
        """辞書を全てクリア"""
        result = messagebox.askyesno(
            "確認",
            "辞書を全てクリアしますか？\nこの操作は取り消せません。"
        )
        if result:
            success = self.dictionary.clear()
            if success:
                self.log_message("辞書をクリアしました")
                self.refresh_dictionary_list()
            else:
                messagebox.showerror("エラー", "辞書のクリアに失敗しました")

    # --- 翻訳フィルタと辞書 ---
    def add_translation_filter(self):
        word = self.translation_filter_entry.get().strip()
        if not word:
            messagebox.showwarning("入力エラー", "フィルタ文字列を入力してください")
            return
        filters = list(self.config.get("translation_filters", []))
        if word in filters:
            messagebox.showinfo("情報", "すでに登録済みです")
            return
        filters.append(word)
        self.config["translation_filters"] = filters
        translator.set_translation_filters(filters)
        save_config(self.config)
        self.translation_filter_entry.delete(0, "end")
        self.refresh_translation_filters()
        self.log_message(f"翻訳フィルタを追加: {word}")

    def remove_translation_filter(self, word):
        filters = list(self.config.get("translation_filters", []))
        if word in filters:
            filters.remove(word)
            self.config["translation_filters"] = filters
            translator.set_translation_filters(filters)
            save_config(self.config)
            self.refresh_translation_filters()
            self.log_message(f"翻訳フィルタを削除: {word}")

    def refresh_translation_filters(self):
        for widget in self.filter_list_frame.winfo_children():
            widget.destroy()
        filters = self.config.get("translation_filters", [])
        if not filters:
            ctk.CTkLabel(self.filter_list_frame, text="（フィルタはありません）", text_color="gray").pack(pady=6)
            return
        for f in filters:
            row = ctk.CTkFrame(self.filter_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2, padx=2)
            ctk.CTkLabel(row, text=f, anchor="w").pack(side="left", padx=6)
            ctk.CTkButton(row, text="削除", width=60, fg_color="#ef4444", hover_color="#dc2626",
                          command=lambda w=f: self.remove_translation_filter(w)).pack(side="right", padx=4)

    def add_translation_dict_entry(self):
        src = self.translation_dict_src.get().strip()
        dst = self.translation_dict_dst.get().strip()
        if not src:
            messagebox.showwarning("入力エラー", "元の文言を入力してください")
            return
        entries = list(self.config.get("translation_dictionary", []))
        entries.append({"source": src, "target": dst})
        self.config["translation_dictionary"] = entries
        translator.set_translation_dictionary(entries)
        save_config(self.config)
        self.translation_dict_src.delete(0, "end")
        self.translation_dict_dst.delete(0, "end")
        self.refresh_translation_dict_list()
        self.log_message(f"翻訳辞書を追加: {src} → {dst}")

    def remove_translation_dict_entry(self, index):
        entries = list(self.config.get("translation_dictionary", []))
        if 0 <= index < len(entries):
            removed = entries.pop(index)
            self.config["translation_dictionary"] = entries
            translator.set_translation_dictionary(entries)
            save_config(self.config)
            self.refresh_translation_dict_list()
            self.log_message(f"翻訳辞書を削除: {removed.get('source', '')}")

    def refresh_translation_dict_list(self):
        for widget in self.translation_dict_list.winfo_children():
            widget.destroy()
        entries = self.config.get("translation_dictionary", [])
        if not entries:
            ctk.CTkLabel(self.translation_dict_list, text="（翻訳辞書はありません）", text_color="gray").pack(pady=6)
            return
        for idx, entry in enumerate(entries):
            row = ctk.CTkFrame(self.translation_dict_list, fg_color="transparent")
            row.pack(fill="x", pady=2, padx=2)
            ctk.CTkLabel(
                row,
                text=f"{entry.get('source','')}  →  {entry.get('target','')}",
                anchor="w"
            ).pack(side="left", padx=6)
            ctk.CTkButton(
                row,
                text="削除",
                width=60,
                fg_color="#ef4444",
                hover_color="#dc2626",
                command=lambda i=idx: self.remove_translation_dict_entry(i)
            ).pack(side="right", padx=4)

    def build_participants_tab(self):
        """参加者管理タブの構築"""
        # 参加者追跡の取得
        self.tracker = get_tracker()

        # スクロール可能なメインフレーム作成
        scrollable_frame = ctk.CTkScrollableFrame(self.tab_participants, fg_color="transparent")
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

        frm_part = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        frm_part.pack(fill="both", expand=True, padx=10, pady=10)

        # 説明ラベルと追跡スイッチ
        top_frame = ctk.CTkFrame(frm_part, fg_color="transparent")
        top_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            top_frame,
            text="チャット上のキーワードを検出して参加者を記録",
            font=("Arial", 12)
        ).pack(side="left")

        # 追跡有効化スイッチ
        self.tracking_var = ctk.BooleanVar(value=self.tracker.enabled)
        ctk.CTkSwitch(
            top_frame,
            text="参加者追跡を有効化",
            command=self.toggle_tracking,
            variable=self.tracking_var,
            font=("Arial", 12)
        ).pack(side="right")

        # 左右2列のコンテナ
        content_frame = ctk.CTkFrame(frm_part, fg_color="transparent")
        content_frame.pack(fill="both", expand=True)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=1)

        # === 左側: キーワード管理 ===
        left_frame = ctk.CTkFrame(content_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        ctk.CTkLabel(
            left_frame,
            text="検出キーワード",
            font=("Arial", 14, "bold")
        ).pack(pady=(10, 5))

        # キーワード追加
        add_keyword_frame = ctk.CTkFrame(left_frame)
        add_keyword_frame.pack(fill="x", padx=10, pady=5)

        self.keyword_entry = ctk.CTkEntry(add_keyword_frame, placeholder_text="例: 参加希望")
        self.keyword_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(
            add_keyword_frame,
            text="追加",
            command=self.add_keyword,
            width=60
        ).pack(side="right")

        # キーワードリスト
        self.keyword_scroll_frame = ctk.CTkScrollableFrame(left_frame, label_text="登録キーワード")
        self.keyword_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh_keyword_list()

        # === 右側: 参加者リスト ===
        right_frame = ctk.CTkFrame(content_frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        # 参加者数表示
        self.participant_count_label = ctk.CTkLabel(
            right_frame,
            text="参加者数: 0人",
            font=("Arial", 14, "bold")
        )
        self.participant_count_label.pack(pady=(10, 5))

        # スクロール可能な参加者リスト
        self.participant_scroll_frame = ctk.CTkScrollableFrame(right_frame, label_text="参加者リスト（ドラッグで順序変更）")
        self.participant_scroll_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # ドラッグアンドドロップ用の変数
        self.drag_data = {"item": None, "index": None}

        # ボタンフレーム（右側の下部）
        button_frame = ctk.CTkFrame(right_frame)
        button_frame.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkButton(
            button_frame,
            text="🔄",
            command=self.refresh_participant_list,
            width=45,
            font=("Arial", 16)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            button_frame,
            text="📢 リスト送信",
            command=self.send_participant_list_to_chat,
            width=120,
            fg_color="#10B981",
            hover_color="#059669"
        ).pack(side="left", padx=2)

        # 自動送信トグル
        self.auto_send_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(
            button_frame,
            text="自動送信(1分)",
            command=self.toggle_auto_send,
            variable=self.auto_send_var,
            font=("Arial", 11)
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            button_frame,
            text="🗑️ クリア",
            command=self.clear_participants,
            width=90,
            fg_color="#EF4444",
            hover_color="#DC2626"
        ).pack(side="left", padx=2)

        # 自動送信用のタイマー変数
        self.auto_send_timer = None

        # 初期リスト表示
        self.refresh_participant_list()
        # タブ表示用のリストも自動更新
        self.start_participant_tab_auto_refresh()

    def build_resource_monitor_tab(self):
        """リソース監視タブの構築"""
        # メインフレーム
        main_frame = ctk.CTkFrame(self.tab_resources, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ヘッダー
        header = ctk.CTkFrame(main_frame, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=BORDER)
        header.pack(fill="x", pady=(0, 10))
        
        header_content = ctk.CTkFrame(header, fg_color="transparent")
        header_content.pack(fill="x", padx=15, pady=12)
        
        ctk.CTkLabel(
            header_content,
            text="リソース監視",
            font=FONT_TITLE
        ).pack(side="left")
        
        # 監視開始/停止ボタン
        self.monitor_switch_var = ctk.BooleanVar(value=False)
        monitor_switch = ctk.CTkSwitch(
            header_content,
            text="監視を開始",
            variable=self.monitor_switch_var,
            command=self.toggle_resource_monitoring,
            font=FONT_LABEL
        )
        monitor_switch.pack(side="right", padx=10)
        
        # デバッグモードスイッチ
        self.debug_mode_var = ctk.BooleanVar(value=False)
        debug_switch = ctk.CTkSwitch(
            header_content,
            text="デバッグモード",
            variable=self.debug_mode_var,
            font=FONT_BODY,
            text_color=TEXT_SUBTLE
        )
        debug_switch.pack(side="right", padx=10)

        # リソース統計表示エリア（2列レイアウト）
        stats_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        stats_container.pack(fill="both", expand=True)
        stats_container.grid_columnconfigure(0, weight=1)
        stats_container.grid_columnconfigure(1, weight=1)

        # 左側: プロセス情報
        process_card = ctk.CTkFrame(stats_container, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=BORDER)
        process_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        process_card.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(process_card, text="プロセス情報", font=FONT_LABEL).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(12, 8))
        
        # メモリ使用量
        ctk.CTkLabel(process_card, text="メモリ使用量:", font=FONT_BODY, text_color=TEXT_SUBTLE).grid(row=1, column=0, sticky="w", padx=15, pady=5)
        self.memory_label = ctk.CTkLabel(process_card, text="-- MB", font=FONT_BODY)
        self.memory_label.grid(row=1, column=1, sticky="w", padx=15, pady=5)
        
        # CPU使用率
        ctk.CTkLabel(process_card, text="CPU使用率:", font=FONT_BODY, text_color=TEXT_SUBTLE).grid(row=2, column=0, sticky="w", padx=15, pady=5)
        self.cpu_label = ctk.CTkLabel(process_card, text="-- %", font=FONT_BODY)
        self.cpu_label.grid(row=2, column=1, sticky="w", padx=15, pady=5)
        
        # スレッド数
        ctk.CTkLabel(process_card, text="アクティブスレッド数:", font=FONT_BODY, text_color=TEXT_SUBTLE).grid(row=3, column=0, sticky="w", padx=15, pady=5)
        self.thread_label = ctk.CTkLabel(process_card, text="--", font=FONT_BODY)
        self.thread_label.grid(row=3, column=1, sticky="w", padx=15, pady=5)
        
        # メモリ使用率
        ctk.CTkLabel(process_card, text="メモリ使用率:", font=FONT_BODY, text_color=TEXT_SUBTLE).grid(row=4, column=0, sticky="w", padx=15, pady=5)
        self.memory_percent_label = ctk.CTkLabel(process_card, text="-- %", font=FONT_BODY)
        self.memory_percent_label.grid(row=4, column=1, sticky="w", padx=15, pady=5)

        # 右側: システム情報
        system_card = ctk.CTkFrame(stats_container, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=BORDER)
        system_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)
        system_card.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(system_card, text="システム情報", font=FONT_LABEL).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(12, 8))
        
        # システムCPU使用率
        ctk.CTkLabel(system_card, text="システムCPU使用率:", font=FONT_BODY, text_color=TEXT_SUBTLE).grid(row=1, column=0, sticky="w", padx=15, pady=5)
        self.system_cpu_label = ctk.CTkLabel(system_card, text="-- %", font=FONT_BODY)
        self.system_cpu_label.grid(row=1, column=1, sticky="w", padx=15, pady=5)
        
        # システムメモリ総量
        ctk.CTkLabel(system_card, text="システムメモリ総量:", font=FONT_BODY, text_color=TEXT_SUBTLE).grid(row=2, column=0, sticky="w", padx=15, pady=5)
        self.system_memory_total_label = ctk.CTkLabel(system_card, text="-- MB", font=FONT_BODY)
        self.system_memory_total_label.grid(row=2, column=1, sticky="w", padx=15, pady=5)
        
        # システムメモリ使用可能
        ctk.CTkLabel(system_card, text="システムメモリ使用可能:", font=FONT_BODY, text_color=TEXT_SUBTLE).grid(row=3, column=0, sticky="w", padx=15, pady=5)
        self.system_memory_available_label = ctk.CTkLabel(system_card, text="-- MB", font=FONT_BODY)
        self.system_memory_available_label.grid(row=3, column=1, sticky="w", padx=15, pady=5)
        
        # システムメモリ使用率
        ctk.CTkLabel(system_card, text="システムメモリ使用率:", font=FONT_BODY, text_color=TEXT_SUBTLE).grid(row=4, column=0, sticky="w", padx=15, pady=5)
        self.system_memory_percent_label = ctk.CTkLabel(system_card, text="-- %", font=FONT_BODY)
        self.system_memory_percent_label.grid(row=4, column=1, sticky="w", padx=15, pady=5)

        # 警告表示エリア
        warning_frame = ctk.CTkFrame(main_frame, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=ACCENT_WARN)
        warning_frame.pack(fill="x", pady=5)
        warning_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(warning_frame, text="警告", font=FONT_LABEL, text_color=ACCENT_WARN).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 5))
        self.warning_label = ctk.CTkLabel(
            warning_frame,
            text="警告はありません",
            font=FONT_BODY,
            text_color=TEXT_SUBTLE,
            wraplength=800,
            justify="left"
        )
        self.warning_label.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 12))

        # デバッグ情報表示エリア（デバッグモード時のみ表示）
        self.debug_frame = ctk.CTkFrame(main_frame, fg_color=PANEL_BG, corner_radius=10, border_width=1, border_color=BORDER)
        self.debug_text = ctk.CTkTextbox(self.debug_frame, height=200, font=("Consolas", 10))
        self.debug_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.debug_frame.pack_forget()  # 初期状態では非表示

        # 更新ボタン
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(10, 0))
        
        ctk.CTkButton(
            button_frame,
            text="手動更新",
            command=self.update_resource_display,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="デバッグ情報をコピー",
            command=self.copy_debug_info,
            width=180,
            fg_color=ACCENT_SECONDARY,
            hover_color="#1EA4D8"
        ).pack(side="left", padx=5)

        # 自動更新タイマー
        self.resource_update_timer = None
        self.update_resource_display()

    def toggle_resource_monitoring(self):
        """リソース監視の開始/停止"""
        if self.monitor_switch_var.get():
            self.resource_monitor.start_monitoring(interval=5.0)
            self.log_message("リソース監視を開始しました", log_type="system")
            # 自動更新を開始
            self.start_resource_auto_update()
        else:
            self.resource_monitor.stop_monitoring()
            self.log_message("リソース監視を停止しました", log_type="system")
            # 自動更新を停止
            self.stop_resource_auto_update()

    def start_resource_auto_update(self):
        """リソース表示の自動更新を開始"""
        self.stop_resource_auto_update()
        self._update_resource_loop()

    def stop_resource_auto_update(self):
        """リソース表示の自動更新を停止"""
        if self.resource_update_timer:
            self.master.after_cancel(self.resource_update_timer)
            self.resource_update_timer = None

    def _update_resource_loop(self):
        """リソース表示の更新ループ"""
        self.update_resource_display()
        # 2秒ごとに更新
        self.resource_update_timer = self.master.after(2000, self._update_resource_loop)

    def update_resource_display(self):
        """リソース表示を更新"""
        stats = self.resource_monitor.get_resource_stats()
        
        if not stats.get("available", False):
            error_msg = stats.get("error", "リソース情報を取得できません")
            self.memory_label.configure(text=f"エラー: {error_msg}", text_color=ACCENT_WARN)
            return
        
        process_stats = stats.get("process", {})
        system_stats = stats.get("system", {})
        warnings = stats.get("warnings", {})
        
        # プロセス情報を更新
        memory_mb = process_stats.get("memory_mb", 0)
        memory_warning = warnings.get("memory_warning", False)
        self.memory_label.configure(
            text=f"{memory_mb:.2f} MB",
            text_color=ACCENT_WARN if memory_warning else "#FFFFFF"
        )
        
        cpu_percent = process_stats.get("cpu_percent", 0)
        cpu_warning = warnings.get("cpu_warning", False)
        self.cpu_label.configure(
            text=f"{cpu_percent:.2f} %",
            text_color=ACCENT_WARN if cpu_warning else "#FFFFFF"
        )
        
        thread_count = process_stats.get("thread_count", 0)
        self.thread_label.configure(text=str(thread_count))
        
        memory_percent = process_stats.get("memory_percent", 0)
        self.memory_percent_label.configure(
            text=f"{memory_percent:.2f} %",
            text_color=ACCENT_WARN if memory_warning else "#FFFFFF"
        )
        
        # システム情報を更新
        system_cpu = system_stats.get("cpu_percent", 0)
        self.system_cpu_label.configure(text=f"{system_cpu:.2f} %")
        
        system_memory_total = system_stats.get("memory_total_mb", 0)
        self.system_memory_total_label.configure(text=f"{system_memory_total:.2f} MB")
        
        system_memory_available = system_stats.get("memory_available_mb", 0)
        self.system_memory_available_label.configure(text=f"{system_memory_available:.2f} MB")
        
        system_memory_percent = system_stats.get("memory_used_percent", 0)
        self.system_memory_percent_label.configure(text=f"{system_memory_percent:.2f} %")
        
        # 警告表示を更新
        warning_messages = []
        if memory_warning:
            warning_messages.append(f"⚠️ メモリ使用量が警告閾値を超えています ({memory_mb:.2f}MB)")
        if cpu_warning:
            warning_messages.append(f"⚠️ CPU使用率が警告閾値を超えています ({cpu_percent:.2f}%)")
        
        if warning_messages:
            self.warning_label.configure(
                text="\n".join(warning_messages),
                text_color=ACCENT_WARN
            )
        else:
            self.warning_label.configure(
                text="警告はありません",
                text_color=TEXT_SUBTLE
            )
        
        # デバッグモード時は詳細情報を表示
        if self.debug_mode_var.get():
            debug_info = self.resource_monitor.get_detailed_debug_info()
            import json
            debug_text = json.dumps(debug_info, indent=2, ensure_ascii=False)
            self.debug_text.delete("0.0", "end")
            self.debug_text.insert("0.0", debug_text)
            self.debug_frame.pack(fill="both", expand=True, pady=(10, 0))
        else:
            self.debug_frame.pack_forget()

    def _on_resource_warning(self, warning_type: str, warning_data: Dict):
        """リソース警告のコールバック"""
        message = warning_data.get("message", "")
        self.log_message(f"[リソース警告] {message}", log_type="system")
        # GUI上でも警告を表示
        self.master.after(0, lambda: self.update_resource_display())

    def copy_debug_info(self):
        """デバッグ情報をクリップボードにコピー"""
        debug_info = self.resource_monitor.get_detailed_debug_info()
        import json
        debug_text = json.dumps(debug_info, indent=2, ensure_ascii=False)
        self.master.clipboard_clear()
        self.master.clipboard_append(debug_text)
        self.log_message("デバッグ情報をクリップボードにコピーしました", log_type="system")

    def toggle_tracking(self):
        """参加者追跡の有効/無効を切り替え"""
        if self.tracking_var.get():
            self.tracker.enable()
            self.log_message("✅ 参加者追跡を有効化しました")
        else:
            self.tracker.disable()
            self.log_message("⏸ 参加者追跡を無効化しました")

    def add_keyword(self):
        """キーワードを追加"""
        keyword = self.keyword_entry.get().strip()
        if not keyword:
            messagebox.showwarning("入力エラー", "キーワードを入力してください")
            return

        self.tracker.add_keyword(keyword)
        self.log_message(f"キーワード追加: {keyword}")
        self.keyword_entry.delete(0, 'end')
        self.refresh_keyword_list()

    def refresh_keyword_list(self):
        """キーワードリストを更新"""
        # 既存のウィジェットをクリア
        for widget in self.keyword_scroll_frame.winfo_children():
            widget.destroy()

        # キーワードを表示
        for keyword in self.tracker.keywords:
            keyword_frame = ctk.CTkFrame(self.keyword_scroll_frame)
            keyword_frame.pack(fill="x", pady=2, padx=2)
            keyword_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                keyword_frame,
                text=keyword,
                font=("Arial", 11),
                anchor="w"
            ).grid(row=0, column=0, sticky="ew", padx=(5, 2))

            ctk.CTkButton(
                keyword_frame,
                text="❌",
                command=lambda k=keyword: self.remove_keyword(k),
                width=35,
                height=26,
                font=("Arial", 14),
                fg_color="#EF4444",
                hover_color="#DC2626"
            ).grid(row=0, column=1, padx=2)

    def remove_keyword(self, keyword):
        """キーワードを削除"""
        self.tracker.remove_keyword(keyword)
        self.log_message(f"キーワード削除: {keyword}")
        self.refresh_keyword_list()

    def refresh_participant_list(self):
        """参加者リストを更新"""
        # 既存のウィジェットをクリア
        for widget in self.participant_scroll_frame.winfo_children():
            widget.destroy()

        # 参加者数を更新
        count = self.tracker.get_count()
        self.participant_count_label.configure(text=f"参加者数: {count}人")

        # 参加者を表示
        participants = self.tracker.get_participants()
        if not participants:
            ctk.CTkLabel(
                self.participant_scroll_frame,
                text="（参加者はいません）",
                text_color="gray",
                font=("Arial", 13, "bold")
            ).pack(pady=10)
        else:
            for i, participant in enumerate(participants):
                entry_frame = ctk.CTkFrame(self.participant_scroll_frame)
                entry_frame.pack(fill="x", pady=2, padx=2)
                entry_frame.grid_columnconfigure(0, weight=1)  # ユーザー名部分を可変に

                # 順番表示とユーザー名（フレキシブルに拡張）
                info_label = ctk.CTkLabel(
                    entry_frame,
                    text=f"{i+1}. {participant['username']}",
                    font=("Arial", 14, "bold"),
                    anchor="w"
                )
                info_label.grid(row=0, column=0, sticky="ew", padx=(5, 2))

                # ドラッグアンドドロップのイベントバインド
                info_label.bind("<Button-1>", lambda e, idx=i, frame=entry_frame: self.start_drag(e, idx, frame))
                info_label.bind("<B1-Motion>", self.on_drag)
                info_label.bind("<ButtonRelease-1>", self.end_drag)
                entry_frame.bind("<Enter>", lambda e, idx=i: self.on_hover_enter(e, idx))

                # ボタンフレーム（右側に固定サイズで配置）
                button_container = ctk.CTkFrame(entry_frame, fg_color="transparent")
                button_container.grid(row=0, column=1, sticky="e")

                # 編集ボタン（アイコン風）
                ctk.CTkButton(
                    button_container,
                    text="✏️",
                    command=lambda u=participant['username']: self.edit_participant(u),
                    width=35,
                    height=26,
                    font=("Arial", 14),
                    fg_color="#3B82F6",
                    hover_color="#2563EB"
                ).pack(side="left", padx=1)

                # 削除ボタン（アイコン風）
                ctk.CTkButton(
                    button_container,
                    text="🗑️",
                    command=lambda u=participant['username']: self.remove_participant(u),
                    width=35,
                    height=26,
                    font=("Arial", 14),
                    fg_color="#EF4444",
                    hover_color="#DC2626"
                ).pack(side="left", padx=1)

    def remove_participant(self, username):
        """参加者を削除"""
        success = self.tracker.remove_participant(username)
        if success:
            self.log_message(f"参加者削除: {username}")
            self.refresh_participant_list()

    def edit_participant(self, username):
        """参加者名を編集"""
        from tkinter import simpledialog

        new_username = simpledialog.askstring(
            "参加者名編集",
            f"新しい名前を入力してください\n（現在: {username}）",
            initialvalue=username
        )

        if new_username and new_username != username:
            success = self.tracker.update_participant(username, new_username)
            if success:
                self.log_message(f"参加者名変更: {username} → {new_username}")
                self.refresh_participant_list()
            else:
                messagebox.showerror("エラー", "参加者名の変更に失敗しました")

    def start_drag(self, event, index, frame):
        """ドラッグ開始"""
        self.drag_data["item"] = frame
        self.drag_data["index"] = index
        self.drag_data["start_y"] = event.y_root
        frame.configure(fg_color="#4A5568")  # ドラッグ中の色

    def on_drag(self, event):
        """ドラッグ中"""
        if self.drag_data["item"]:
            # ドラッグ中の視覚的フィードバック
            delta_y = event.y_root - self.drag_data["start_y"]
            if abs(delta_y) > 5:  # 5ピクセル以上移動したら視覚的に表示
                self.drag_data["item"].configure(fg_color="#2D3748")

    def on_hover_enter(self, event, index):
        """ドラッグ中に他のアイテムにホバー"""
        if self.drag_data["item"] and self.drag_data["index"] is not None:
            from_index = self.drag_data["index"]
            to_index = index

            if from_index != to_index:
                # ホバー位置にハイライト表示
                event.widget.configure(fg_color="#4299E1")

    def end_drag(self, event):
        """ドラッグ終了"""
        if self.drag_data["item"] and self.drag_data["index"] is not None:
            # マウス位置から目的のインデックスを計算
            participants = self.tracker.get_participants()
            if not participants:
                self.drag_data = {"item": None, "index": None}
                return

            # どのフレームの上でドロップされたか判定
            drop_widget = event.widget.winfo_containing(event.x_root, event.y_root)

            # ドロップ先のインデックスを探す
            to_index = None
            for i, child in enumerate(self.participant_scroll_frame.winfo_children()):
                if drop_widget == child or drop_widget.master == child:
                    to_index = i
                    break
                # ラベルウィジェットの場合
                for subwidget in child.winfo_children():
                    if drop_widget == subwidget:
                        to_index = i
                        break
                if to_index is not None:
                    break

            # インデックスが見つかった場合、移動を実行
            if to_index is not None and to_index != self.drag_data["index"]:
                from_index = self.drag_data["index"]
                success = self.tracker.move_participant(from_index, to_index)
                if success:
                    self.log_message(f"参加者順序変更: {from_index + 1}番目 → {to_index + 1}番目")
                    self.refresh_participant_list()
            else:
                # 移動しない場合は元の色に戻す
                self.drag_data["item"].configure(fg_color=["gray92", "gray14"])

        # ドラッグデータをリセット
        self.drag_data = {"item": None, "index": None}

    def send_participant_list_to_chat(self):
        """参加者リストをチャットに送信"""
        if not self.bot_instance:
            messagebox.showwarning("警告", "BOTが起動していません")
            self.log_message("⚠️ BOTが起動していないため、参加者リストを送信できません")
            return

        participants = self.tracker.get_participant_names()
        if not participants:
            message = "【待機参加者リスト】参加者はいません"
        else:
            participant_str = "→".join(participants)
            message = f"【待機参加者リスト】{participant_str}"

        if self._send_text_to_chat(message):
            self.log_message("📢 参加者リストをチャットに送信しました")
        else:
            self.log_message("⚠️ BOTが接続されていないため、送信できませんでした")

    def toggle_auto_send(self):
        """自動送信の有効/無効を切り替え"""
        if self.auto_send_var.get():
            self.log_message("⏰ 参加者リストの自動送信を開始しました (1分ごと)")
            self.start_auto_send()
        else:
            self.log_message("⏸ 参加者リストの自動送信を停止しました")
            self.stop_auto_send()

    def start_auto_send(self):
        """自動送信タイマーを開始"""
        self.stop_auto_send()  # 既存のタイマーをクリア
        self.auto_send_participants()

    def stop_auto_send(self):
        """自動送信タイマーを停止"""
        if self.auto_send_timer:
            self.auto_send_timer.cancel()
            self.auto_send_timer = None

    def auto_send_participants(self):
        """参加者リストを自動送信"""
        if self.auto_send_var.get():
            self.send_participant_list_to_chat()

            # 60秒後に再度実行
            self.auto_send_timer = threading.Timer(60.0, self.auto_send_participants)
            self.auto_send_timer.daemon = True
            self.auto_send_timer.start()

    def start_participant_tab_auto_refresh(self):
        """参加者管理タブのリストを自動更新"""
        self.refresh_participant_list()
        # 3秒ごとに更新
        self.participant_tab_refresh_timer = self.master.after(3000, self.start_participant_tab_auto_refresh)

    def clear_participants(self):
        """参加者リストを全てクリア"""
        if self.tracker.get_count() == 0:
            messagebox.showinfo("情報", "参加者リストは既に空です")
            return

        result = messagebox.askyesno(
            "確認",
            f"参加者リスト({self.tracker.get_count()}人)を全てクリアしますか？\nこの操作は取り消せません。"
        )
        if result:
            self.tracker.clear()
            self.log_message("参加者リストをクリアしました")
            self.refresh_participant_list()

    def toggle_customize_mode(self):
        """カスタマイズモードのON/OFF"""
        if self.customize_mode_var.get():
            # カスタマイズモードON
            self.log_message("🎨 カスタマイズモードON: PanedWindowの境界をドラッグしてレイアウトを調整できます", log_type="system")
            self._apply_customize_mode(True)
        else:
            # カスタマイズモードOFF - レイアウトを保存
            self.log_message("💾 カスタマイズモードOFF: レイアウトを保存しました", log_type="system")
            self._save_layout()
            self._apply_customize_mode(False)

    def _apply_customize_mode(self, enabled: bool):
        """カスタマイズモードの視覚的フィードバック"""
        if enabled:
            # PanedWindowのサッシュを目立たせる
            if hasattr(self, 'main_paned'):
                self.main_paned.configure(sashwidth=8, bg=ACCENT_SECONDARY)
            if hasattr(self, 'right_paned'):
                self.right_paned.configure(sashwidth=8, bg=ACCENT_SECONDARY)
        else:
            # 通常の表示に戻す
            if hasattr(self, 'main_paned'):
                self.main_paned.configure(sashwidth=5, bg=BORDER)
            if hasattr(self, 'right_paned'):
                self.right_paned.configure(sashwidth=5, bg=BORDER)

    def _save_layout(self):
        """現在のレイアウト（PanedWindowの位置）を保存"""
        try:
            layout_data = {}

            # メインPanedWindowの位置を取得
            if hasattr(self, 'main_paned'):
                try:
                    sash_coord = self.main_paned.sash_coord(0)
                    layout_data['main_sash_x'] = sash_coord[0]
                except:
                    pass

            # 右側PanedWindowの位置を取得
            if hasattr(self, 'right_paned'):
                try:
                    sash_coord = self.right_paned.sash_coord(0)
                    layout_data['right_sash_y'] = sash_coord[1]
                except:
                    pass

            # config.jsonに保存
            if layout_data:
                self.config['ui_layout'] = layout_data
                save_config(self.config)
                logger.info(f"UI layout saved: {layout_data}")
        except Exception as e:
            logger.error(f"Failed to save layout: {e}", exc_info=True)

    def _restore_layout(self):
        """保存されたレイアウトを復元"""
        try:
            layout_data = self.config.get('ui_layout', {})

            if layout_data:
                # 保存されたレイアウトを適用
                # update()で完全に描画を待ってからsash位置を設定
                self.master.update_idletasks()
                self.master.update()

                if 'main_sash_x' in layout_data and hasattr(self, 'main_paned'):
                    try:
                        window_width = max(self.master.winfo_width(), 1000)
                        default_x = int(window_width * 0.7)
                        min_x = int(window_width * 0.65)
                        max_x = int(window_width * 0.75)
                        sash_x = layout_data.get('main_sash_x', default_x)
                        sash_x = max(min_x, min(sash_x, max_x))
                        self.main_paned.sash_place(0, sash_x, 0)
                        logger.info(f"Restored main sash position (clamped): x={sash_x}")
                    except Exception as e:
                        logger.debug(f"Could not restore main sash: {e}")

                if 'right_sash_y' in layout_data and hasattr(self, 'right_paned'):
                    try:
                        self.right_paned.sash_place(0, 0, layout_data['right_sash_y'])
                        logger.info(f"Restored right sash position: y={layout_data['right_sash_y']}")
                    except Exception as e:
                        logger.debug(f"Could not restore right sash: {e}")
            else:
                # 保存がない場合は初期設定
                self._force_main_split()

                if hasattr(self, 'comment_paned'):
                    comment_height = self.comment_paned.winfo_height()
                    fallback_height = max(self.master.winfo_height(), 600) * 0.6
                    target = int(comment_height * 0.6) if comment_height > 100 else int(fallback_height)
                    try:
                        self.comment_paned.sash_place(0, 0, target)
                        logger.debug(f"Set comment paned initial position: {target}")
                    except Exception:
                        logger.debug("Failed to set initial comment paned position")

        except Exception as e:
            logger.error(f"Failed to restore layout: {e}", exc_info=True)
        finally:
            # 常に強制的に左:右=70:30付近に合わせ、設定も更新する
            # さらに遅延を追加して確実に適用
            self.master.after(200, self._force_main_split)

    def _force_main_split(self):
        """左右Panedを左約70%:右約30%に強制設定し、configにも保存"""
        try:
            # 完全に描画を待ってからsash位置を設定
            self.master.update_idletasks()
            self.master.update()

            if hasattr(self, 'main_paned'):
                pane_width = max(self.main_paned.winfo_width(), self.master.winfo_width(), 1200)
                sash_x = int(pane_width * 0.7)
                min_x = int(pane_width * 0.65)
                max_x = int(pane_width * 0.75)
                sash_x = max(min_x, min(sash_x, max_x))
                self.main_paned.sash_place(0, sash_x, 0)
                # 保存も更新
                self.config.setdefault('ui_layout', {})
                self.config['ui_layout']['main_sash_x'] = sash_x
                save_config(self.config)
                logger.debug(f"Forced main paned sash to x={sash_x} (saved)")
        except Exception as e:
            logger.debug(f"Failed to force main split: {e}")

    def _add_context_menu(self, widget, panel_name):
        """パネルに右クリックメニューを追加"""
        menu = tk.Menu(widget, tearoff=0)

        # サイズ変更メニュー
        menu.add_command(label="🔹 小さい", command=lambda: self._change_panel_size(panel_name, "小"))
        menu.add_command(label="🔸 中", command=lambda: self._change_panel_size(panel_name, "中"))
        menu.add_command(label="🔶 大きい", command=lambda: self._change_panel_size(panel_name, "大"))

        def show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        # 右クリックイベントをバインド
        widget.bind("<Button-3>", show_menu)

        # タイトルラベルにもバインド（クリックしやすくする）
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                child.bind("<Button-3>", show_menu)

    def _change_panel_size(self, panel_name, size):
        """パネルのサイズを変更"""
        # サイズを保存
        self.panel_sizes[panel_name] = size

        # サイズラベルを更新
        size_label = None
        if panel_name == "comment_log" and hasattr(self, 'comment_size_label'):
            size_label = self.comment_size_label
        elif panel_name == "event_log" and hasattr(self, 'event_size_label'):
            size_label = self.event_size_label
        elif panel_name == "participant_list" and hasattr(self, 'participant_size_label'):
            size_label = self.participant_size_label

        if size_label:
            size_label.configure(text=f"({size})")

        # サイズに応じたminsize（最小サイズ）を設定
        size_map = {
            "小": 150,
            "中": 300,
            "大": 500
        }
        min_size = size_map.get(size, 300)

        # PanedWindowのminsizeを更新
        try:
            if panel_name == "comment_log" and hasattr(self, 'main_paned') and hasattr(self, 'left_frame'):
                # 左側（コメントログ）のminsize
                self.main_paned.paneconfigure(self.left_frame, minsize=min_size)
                logger.info(f"Comment log panel size changed to {size} (minsize={min_size})")

            elif panel_name in ["event_log", "participant_list"] and hasattr(self, 'right_paned'):
                # 右側の上下パネル
                if panel_name == "event_log" and hasattr(self, 'event_frame'):
                    self.right_paned.paneconfigure(self.event_frame, minsize=min_size)
                    logger.info(f"Event log panel size changed to {size} (minsize={min_size})")
                elif panel_name == "participant_list" and hasattr(self, 'participant_frame'):
                    self.right_paned.paneconfigure(self.participant_frame, minsize=min_size)
                    logger.info(f"Participant list panel size changed to {size} (minsize={min_size})")
        except Exception as e:
            logger.error(f"Failed to change panel size: {e}", exc_info=True)

        # config.jsonに保存
        self._save_panel_sizes()

        # UIメッセージ
        panel_name_jp = {
            "comment_log": "コメントログ",
            "event_log": "特別イベント",
            "participant_list": "参加者リスト"
        }
        self.log_message(f"✨ {panel_name_jp.get(panel_name, panel_name)}のサイズを'{size}'に変更しました", log_type="system")

    def _send_text_to_chat(self, text: str) -> bool:
        """BOT経由でチャットに送信（接続チェック込み）"""
        if not text or not text.strip():
            return False
        if not self.bot_instance:
            return False

        try:
            channels = []
            if hasattr(self.bot_instance, "connected_channels"):
                channels = list(getattr(self.bot_instance, "connected_channels") or [])

            if not channels and hasattr(self.bot_instance, "_connection") and self.bot_instance._connection:
                channels = list(self.bot_instance._connection.connected_channels or [])

            if not channels:
                return False

            channel = channels[0]
            import asyncio

            # TwitchIOのイベントループ参照を取得（event_readyでセットしたものを優先）
            loop = getattr(self.bot_instance, "_running_loop", None) or getattr(self.bot_instance, "loop", None)
            if not loop:
                return False

            asyncio.run_coroutine_threadsafe(channel.send(text + '\u200B'), loop)
            logger.debug(f"Sent chat message via helper: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send chat message: {e}", exc_info=True)
            return False

    def _save_panel_sizes(self):
        """パネルサイズ設定を保存"""
        try:
            self.config['ui_panel_sizes'] = self.panel_sizes
            save_config(self.config)
            logger.info(f"Panel sizes saved: {self.panel_sizes}")
        except Exception as e:
            logger.error(f"Failed to save panel sizes: {e}", exc_info=True)

    def _restore_panel_sizes(self):
        """保存されたパネルサイズ設定を復元"""
        try:
            for panel_name, size in self.panel_sizes.items():
                # サイズラベルを更新
                if panel_name == "comment_log" and hasattr(self, 'comment_size_label'):
                    self.comment_size_label.configure(text=f"({size})")
                elif panel_name == "event_log" and hasattr(self, 'event_size_label'):
                    self.event_size_label.configure(text=f"({size})")
                elif panel_name == "participant_list" and hasattr(self, 'participant_size_label'):
                    self.participant_size_label.configure(text=f"({size})")

                # minsizeを設定
                size_map = {
                    "小": 150,
                    "中": 300,
                    "大": 500
                }
                min_size = size_map.get(size, 300)

                if panel_name == "comment_log" and hasattr(self, 'main_paned') and hasattr(self, 'left_frame'):
                    self.main_paned.paneconfigure(self.left_frame, minsize=min_size)
                elif panel_name == "event_log" and hasattr(self, 'right_paned') and hasattr(self, 'event_frame'):
                    self.right_paned.paneconfigure(self.event_frame, minsize=min_size)
                elif panel_name == "participant_list" and hasattr(self, 'right_paned') and hasattr(self, 'participant_frame'):
                    self.right_paned.paneconfigure(self.participant_frame, minsize=min_size)

            logger.info(f"Panel sizes restored: {self.panel_sizes}")
        except Exception as e:
            logger.error(f"Failed to restore panel sizes: {e}", exc_info=True)

    def voice_callback(self, text, translated):
        # 認識テキストと翻訳結果を表示
        if translated == "":
            # フィルタされた場合
            msg = f"🚫 [Voice Filter] {text}"
            self.master.after(0, lambda: self.log_message(msg, log_type="system"))
            return

        msg = f"🎤 [Voice] {text}\n    ➡ {translated}"
        # UI更新はメインスレッドで行う
        self.master.after(0, lambda: self.log_message(msg, log_type="voice"))

        # オーバーレイ更新
        update_translation(translated)

        # 音声翻訳結果をチャット送信（音声翻訳機能がONなら送信）
        if self.voice_var.get() and translated and translated != "(No API Key)":
            if not self._send_text_to_chat(translated):
                logger.warning("Voice translation could not be sent to chat (connection not ready?)")
