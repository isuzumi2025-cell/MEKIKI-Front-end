"""
Phase 3: 同期スクロールCanvas
左右のCanvasのスクロールを同期
"""
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
from typing import Optional, Callable


class SyncScrollCanvas(ctk.CTkFrame):
    """同期スクロール対応Canvas"""
    
    def __init__(
        self,
        master,
        width: int = 800,
        height: int = 600,
        title: str = "",
        **kwargs
    ):
        """
        Args:
            master: 親ウィジェット
            width: キャンバス幅
            height: キャンバス高さ
            title: タイトル
        """
        super().__init__(master, width=width, height=height, **kwargs)
        
        # ヘッダー
        self.header_label = ctk.CTkLabel(
            self,
            text=title,
            font=("Arial", 12, "bold"),
            anchor="w",
            height=30
        )
        self.header_label.pack(fill="x", padx=5, pady=(5, 0))
        
        # キャンバスフレーム
        canvas_frame = ctk.CTkFrame(self, fg_color="transparent")
        canvas_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 縦スクロールバー
        self.v_scrollbar = tk.Scrollbar(canvas_frame, orient="vertical")
        self.v_scrollbar.pack(side="right", fill="y")
        
        # 横スクロールバー
        self.h_scrollbar = tk.Scrollbar(canvas_frame, orient="horizontal")
        self.h_scrollbar.pack(side="bottom", fill="x")
        
        # キャンバス
        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#2B2B2B",
            highlightthickness=0,
            yscrollcommand=self._on_canvas_scroll_y,
            xscrollcommand=self._on_canvas_scroll_x
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # スクロールバーとキャンバスを連携
        self.v_scrollbar.config(command=self._on_scrollbar_y)
        self.h_scrollbar.config(command=self._on_scrollbar_x)
        
        # 内部データ
        self.pil_image: Optional[Image.Image] = None
        self.tk_image: Optional[ImageTk.PhotoImage] = None
        self.image_id: Optional[int] = None
        
        # 同期スクロール用
        self.partner: Optional['SyncScrollCanvas'] = None
        self._sync_enabled: bool = True
        self._is_syncing: bool = False  # 無限ループ防止フラグ
        
        # マウスホイールバインド
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)  # Linux
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)  # Linux
    
    def load_image(self, image: Image.Image, title: str = ""):
        """
        画像を読み込む
        
        Args:
            image: PIL Imageオブジェクト
            title: タイトル
        """
        # 画像の検証
        if image is None:
            print("⚠️ 警告: 画像がNoneです")
            # プレースホルダー画像を作成
            image = self._create_placeholder_image("画像なし")
        
        if not isinstance(image, Image.Image):
            print(f"⚠️ 警告: 画像の型が不正です: {type(image)}")
            image = self._create_placeholder_image("画像形式エラー")
        
        self.pil_image = image
        
        if title:
            self.header_label.configure(text=title)
        
        # PIL ImageをPhotoImageに変換
        try:
            self.tk_image = ImageTk.PhotoImage(self.pil_image)
        except Exception as e:
            print(f"⚠️ 画像変換エラー: {str(e)}")
            # エラー時はプレースホルダーを使用
            self.pil_image = self._create_placeholder_image(f"変換エラー\n{str(e)[:30]}")
            self.tk_image = ImageTk.PhotoImage(self.pil_image)
        
        # キャンバスクリア
        self.canvas.delete("all")
        
        # 画像を配置
        self.image_id = self.canvas.create_image(
            0, 0,
            anchor="nw",
            image=self.tk_image
        )
        
        # スクロール領域を設定
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        
        # 座標変換用スケール値を設定（元画像サイズ = 表示サイズ なので 1.0）
        # 他のコンポーネントがgetattr(canvas, 'scale_x', 1.0)で参照する
        self.canvas.scale_x = 1.0
        self.canvas.scale_y = 1.0
        self.canvas.offset_x = 0
        self.canvas.offset_y = 0
        
        # 元画像サイズも保存
        self.canvas.original_width = self.pil_image.width
        self.canvas.original_height = self.pil_image.height

    
    def bind_partner(self, partner: 'SyncScrollCanvas'):
        """
        スクロールパートナーを設定
        
        Args:
            partner: 同期するSyncScrollCanvasインスタンス
        """
        self.partner = partner
    
    def enable_sync(self):
        """同期を有効化"""
        self._sync_enabled = True
    
    def disable_sync(self):
        """同期を無効化"""
        self._sync_enabled = False
    
    def _on_canvas_scroll_y(self, *args):
        """キャンバスの縦スクロール時のコールバック"""
        self.v_scrollbar.set(*args)
        self._sync_to_partner("y", args)
    
    def _on_canvas_scroll_x(self, *args):
        """キャンバスの横スクロール時のコールバック"""
        self.h_scrollbar.set(*args)
        self._sync_to_partner("x", args)
    
    def _on_scrollbar_y(self, *args):
        """縦スクロールバー操作時のコールバック"""
        self.canvas.yview(*args)
        if self.partner and self._sync_enabled and not self._is_syncing:
            self._is_syncing = True
            self.partner.canvas.yview(*args)
            self._is_syncing = False
    
    def _on_scrollbar_x(self, *args):
        """横スクロールバー操作時のコールバック"""
        self.canvas.xview(*args)
        if self.partner and self._sync_enabled and not self._is_syncing:
            self._is_syncing = True
            self.partner.canvas.xview(*args)
            self._is_syncing = False
    
    def _on_mouse_wheel(self, event):
        """マウスホイールスクロール時のコールバック"""
        if event.num == 5 or event.delta < 0:
            # 下スクロール
            delta = 1
        else:
            # 上スクロール
            delta = -1
        
        self.canvas.yview_scroll(delta, "units")
        
        # パートナーも同期
        if self.partner and self._sync_enabled and not self._is_syncing:
            self._is_syncing = True
            self.partner.canvas.yview_scroll(delta, "units")
            self._is_syncing = False
    
    def _sync_to_partner(self, direction: str, scroll_args):
        """パートナーと同期
        
        Args:
            direction: "x" or "y"
            scroll_args: スクロール引数
        """
        if not self.partner or not self._sync_enabled or self._is_syncing:
            return
        
        self._is_syncing = True
        
        try:
            # パートナーのスクロール位置を同期
            if direction == "y":
                first, last = scroll_args
                self.partner.canvas.yview_moveto(float(first))
            elif direction == "x":
                first, last = scroll_args
                self.partner.canvas.xview_moveto(float(first))
        finally:
            self._is_syncing = False
    
    def get_scroll_position(self) -> tuple:
        """現在のスクロール位置を取得"""
        y_pos = self.canvas.yview()
        x_pos = self.canvas.xview()
        return (x_pos, y_pos)
    
    def set_scroll_position(self, x_pos: tuple, y_pos: tuple):
        """スクロール位置を設定"""
        self.canvas.xview_moveto(x_pos[0])
        self.canvas.yview_moveto(y_pos[0])
    
    def _create_placeholder_image(self, message: str = "画像なし", width: int = 800, height: int = 600) -> Image.Image:
        """
        プレースホルダー画像を作成
        
        Args:
            message: 表示するメッセージ
            width: 画像幅
            height: 画像高さ
        
        Returns:
            PIL Image
        """
        # グレーの背景画像を作成
        img = Image.new('RGB', (width, height), color='#2B2B2B')
        draw = ImageDraw.Draw(img)
        
        # 中央に赤い枠を描画
        margin = 50
        draw.rectangle(
            [margin, margin, width - margin, height - margin],
            outline='#FF4444',
            width=5
        )
        
        # テキストを描画
        text = f"⚠️ {message}"
        
        # テキストのバウンディングボックスを取得（簡易計算）
        text_width = len(text) * 10
        text_height = 20
        text_x = (width - text_width) // 2
        text_y = (height - text_height) // 2
        
        draw.text((text_x, text_y), text, fill='#FF4444')
        
        return img

