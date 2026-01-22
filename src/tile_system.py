"""
タイルシステム - Windowsスタートメニュー風のカスタマイズ可能なレイアウト
各ウィジェットをタイルとして管理し、ドラッグ&ドロップで配置変更、サイズ調整が可能
"""
import tkinter as tk
import customtkinter as ctk
from typing import Dict, Tuple, Optional, Callable
from src.logger import logger


class TileSize:
    """タイルサイズの定義"""
    SMALL = (1, 1)   # 1x1グリッド
    MEDIUM = (2, 2)  # 2x2グリッド
    LARGE = (3, 2)   # 3x2グリッド
    XLARGE = (4, 3)  # 4x3グリッド


class Tile:
    """
    ドラッグ可能なタイルウィジェット
    """
    def __init__(self, parent, title: str, content_widget, size: Tuple[int, int] = TileSize.MEDIUM):
        """
        Args:
            parent: 親ウィジェット
            title: タイルのタイトル
            content_widget: タイル内に表示するウィジェット
            size: タイルサイズ (width, height) グリッド単位
        """
        self.parent = parent
        self.title = title
        self.size = size
        self.grid_position = (0, 0)  # グリッド上の位置 (column, row)

        # タイルのコンテナフレーム
        self.frame = ctk.CTkFrame(parent, corner_radius=10, border_width=2)

        # ヘッダー（ドラッグハンドル）
        self.header = ctk.CTkFrame(self.frame, height=30, corner_radius=8)
        self.header.pack(fill="x", padx=2, pady=(2, 0))

        # タイトルラベル
        self.title_label = ctk.CTkLabel(
            self.header,
            text=title,
            font=("Arial", 12, "bold"),
            anchor="w"
        )
        self.title_label.pack(side="left", padx=10, pady=5)

        # サイズ変更ボタン
        self.size_button = ctk.CTkButton(
            self.header,
            text="⊡",
            width=25,
            height=25,
            font=("Arial", 14),
            command=self.cycle_size
        )
        self.size_button.pack(side="right", padx=5)

        # コンテンツエリア
        self.content_frame = ctk.CTkFrame(self.frame)
        self.content_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # コンテンツウィジェットを配置
        self.content_widget = content_widget
        if content_widget:
            content_widget.pack(in_=self.content_frame, fill="both", expand=True)

        # ドラッグ関連の変数
        self.drag_data = {"x": 0, "y": 0, "dragging": False}
        self.is_draggable = False

        # リサイズコールバック
        self.on_resize_callback: Optional[Callable] = None

    def enable_drag(self):
        """ドラッグを有効化"""
        self.is_draggable = True
        self.frame.configure(border_color="#4A90E2")
        self.header.configure(cursor="fleur")

        # ドラッグイベントをバインド
        self.header.bind("<Button-1>", self.start_drag)
        self.header.bind("<B1-Motion>", self.on_drag)
        self.header.bind("<ButtonRelease-1>", self.end_drag)
        self.title_label.bind("<Button-1>", self.start_drag)
        self.title_label.bind("<B1-Motion>", self.on_drag)
        self.title_label.bind("<ButtonRelease-1>", self.end_drag)

    def disable_drag(self):
        """ドラッグを無効化"""
        self.is_draggable = False
        self.frame.configure(border_color="gray")
        self.header.configure(cursor="")

        # イベントバインド解除
        self.header.unbind("<Button-1>")
        self.header.unbind("<B1-Motion>")
        self.header.unbind("<ButtonRelease-1>")
        self.title_label.unbind("<Button-1>")
        self.title_label.unbind("<B1-Motion>")
        self.title_label.unbind("<ButtonRelease-1>")

    def start_drag(self, event):
        """ドラッグ開始"""
        if not self.is_draggable:
            return
        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root
        self.drag_data["dragging"] = True
        self.frame.lift()
        logger.debug(f"Started dragging tile: {self.title}")

    def on_drag(self, event):
        """ドラッグ中"""
        if not self.is_draggable or not self.drag_data["dragging"]:
            return

        # 現在の位置を計算
        delta_x = event.x_root - self.drag_data["x"]
        delta_y = event.y_root - self.drag_data["y"]

        # フレームを移動
        x = self.frame.winfo_x() + delta_x
        y = self.frame.winfo_y() + delta_y
        self.frame.place(x=x, y=y)

        # 次のイベント用に位置を更新
        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root

    def end_drag(self, event):
        """ドラッグ終了"""
        if not self.is_draggable or not self.drag_data["dragging"]:
            return
        self.drag_data["dragging"] = False
        logger.debug(f"Ended dragging tile: {self.title}")

    def cycle_size(self):
        """サイズを循環的に変更 (小→中→大→特大→小...)"""
        sizes = [TileSize.SMALL, TileSize.MEDIUM, TileSize.LARGE, TileSize.XLARGE]
        current_index = sizes.index(self.size) if self.size in sizes else 0
        next_index = (current_index + 1) % len(sizes)
        self.size = sizes[next_index]

        logger.info(f"Tile {self.title} size changed to {self.size}")

        # リサイズコールバックを呼び出し
        if self.on_resize_callback:
            self.on_resize_callback(self)

    def set_grid_position(self, column: int, row: int):
        """グリッド上の位置を設定"""
        self.grid_position = (column, row)

    def get_layout_data(self) -> Dict:
        """レイアウトデータを取得（保存用）"""
        return {
            "title": self.title,
            "size": self.size,
            "position": self.grid_position
        }


class TileGridManager:
    """
    タイルをグリッド上に配置・管理するマネージャー
    """
    def __init__(self, parent, grid_cols: int = 12, grid_rows: int = 8, cell_size: int = 80):
        """
        Args:
            parent: 親ウィジェット
            grid_cols: グリッドの列数
            grid_rows: グリッドの行数
            cell_size: 1セルのサイズ（ピクセル）
        """
        self.parent = parent
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.cell_size = cell_size

        # グリッドコンテナ
        self.container = ctk.CTkFrame(parent)
        self.container.pack(fill="both", expand=True)

        # タイルのリスト
        self.tiles: Dict[str, Tile] = {}

        # グリッドの占有状態（True = 占有済み）
        self.grid = [[False for _ in range(grid_cols)] for _ in range(grid_rows)]

    def add_tile(self, tile: Tile, column: int = 0, row: int = 0):
        """
        タイルをグリッドに追加

        Args:
            tile: 追加するタイル
            column: 配置する列
            row: 配置する行
        """
        # 配置可能かチェック
        if not self._can_place(column, row, tile.size[0], tile.size[1]):
            logger.warning(f"Cannot place tile {tile.title} at ({column}, {row})")
            return False

        # タイルを配置
        tile.set_grid_position(column, row)
        self.tiles[tile.title] = tile

        # グリッドを更新
        self._mark_occupied(column, row, tile.size[0], tile.size[1], True)

        # タイルのリサイズコールバックを設定
        tile.on_resize_callback = self._on_tile_resized

        # レイアウトを更新
        self._layout_tile(tile)

        logger.info(f"Added tile {tile.title} at ({column}, {row}) with size {tile.size}")
        return True

    def _can_place(self, col: int, row: int, width: int, height: int) -> bool:
        """指定位置にタイルを配置できるかチェック"""
        if col + width > self.grid_cols or row + height > self.grid_rows:
            return False

        for r in range(row, row + height):
            for c in range(col, col + width):
                if self.grid[r][c]:
                    return False
        return True

    def _mark_occupied(self, col: int, row: int, width: int, height: int, occupied: bool):
        """グリッドの占有状態を更新"""
        for r in range(row, row + height):
            for c in range(col, col + width):
                self.grid[r][c] = occupied

    def _layout_tile(self, tile: Tile):
        """タイルをグリッド上に配置"""
        col, row = tile.grid_position
        width, height = tile.size

        x = col * self.cell_size
        y = row * self.cell_size
        w = width * self.cell_size
        h = height * self.cell_size

        tile.frame.place(x=x, y=y, width=w, height=h)

    def _on_tile_resized(self, tile: Tile):
        """タイルのサイズが変更されたときの処理"""
        # 既存の占有をクリア
        col, row = tile.grid_position
        old_width, old_height = tile.size
        self._mark_occupied(col, row, old_width, old_height, False)

        # 新しいサイズで配置可能かチェック
        new_width, new_height = tile.size
        if self._can_place(col, row, new_width, new_height):
            self._mark_occupied(col, row, new_width, new_height, True)
            self._layout_tile(tile)
        else:
            # 配置できない場合は元のサイズに戻す
            logger.warning(f"Cannot resize tile {tile.title} - reverting to previous size")
            tile.size = (old_width, old_height)
            self._mark_occupied(col, row, old_width, old_height, True)

    def enable_customization(self):
        """カスタマイズモードを有効化"""
        for tile in self.tiles.values():
            tile.enable_drag()

    def disable_customization(self):
        """カスタマイズモードを無効化"""
        for tile in self.tiles.values():
            tile.disable_drag()

    def get_layout_data(self) -> Dict:
        """全タイルのレイアウトデータを取得"""
        return {
            title: tile.get_layout_data()
            for title, tile in self.tiles.items()
        }

    def restore_layout(self, layout_data: Dict):
        """保存されたレイアウトデータを復元"""
        # 実装は後で追加
        pass
