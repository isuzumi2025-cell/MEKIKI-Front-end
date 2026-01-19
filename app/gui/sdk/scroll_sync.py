"""
Scroll Synchronization Manager
Web/PDF Canvas間の双方向スクロール同期

Features:
- 双方向同期（Web ↔ PDF）
- Debounce（過剰な更新防止）
- スムーズスクロール
- ON/OFF切り替え
- マウスホイール対応

Usage:
    from app.gui.sdk.scroll_sync import ScrollSyncManager

    manager = ScrollSyncManager(web_canvas, pdf_canvas)
    manager.enable()  # 同期開始
    manager.disable() # 同期停止
"""

import tkinter as tk
from typing import Optional, Callable
from dataclasses import dataclass
import time


@dataclass
class ScrollState:
    """スクロール状態"""
    x: float
    y: float
    timestamp: float


class ScrollSyncManager:
    """
    スクロール同期マネージャー

    双方向の同期、Debounce、スムーズスクロール対応
    """

    def __init__(
        self,
        canvas1: tk.Canvas,
        canvas2: tk.Canvas,
        debounce_ms: int = 50,  # Debounce時間（ミリ秒）
        on_sync: Optional[Callable[[str], None]] = None
    ):
        """
        初期化

        Args:
            canvas1: Canvas 1（例: Web）
            canvas2: Canvas 2（例: PDF）
            debounce_ms: Debounce時間（ミリ秒）
            on_sync: 同期時のコールバック（デバッグ用）
        """
        self.canvas1 = canvas1
        self.canvas2 = canvas2
        self.debounce_ms = debounce_ms
        self.on_sync = on_sync

        # 同期状態
        self._enabled = False
        self._syncing = False  # 無限ループ防止フラグ

        # Debounce管理
        self._debounce_job = None
        self._last_scroll_time = 0

        # スクロール状態
        self._last_state1: Optional[ScrollState] = None
        self._last_state2: Optional[ScrollState] = None

        # イベントバインディングID
        self._bindings = []

        print(f"✅ ScrollSyncManager initialized (debounce={debounce_ms}ms)")

    def enable(self):
        """スクロール同期を有効化"""
        if self._enabled:
            return

        self._enabled = True

        # イベントバインド
        self._bind_events()

        print("🔗 Scroll sync enabled")

    def disable(self):
        """スクロール同期を無効化"""
        if not self._enabled:
            return

        self._enabled = False

        # イベントアンバインド
        self._unbind_events()

        print("🔓 Scroll sync disabled")

    def toggle(self) -> bool:
        """
        スクロール同期のON/OFF切り替え

        Returns:
            切り替え後の状態（True=有効）
        """
        if self._enabled:
            self.disable()
        else:
            self.enable()

        return self._enabled

    def _bind_events(self):
        """イベントをバインド"""
        # スクロールバーイベント
        # Canvas1のスクロール → Canvas2に反映
        self._bindings.append((
            self.canvas1,
            "<Configure>",
            self.canvas1.bind("<Configure>", lambda e: self._on_scroll(self.canvas1, self.canvas2))
        ))

        # Canvas2のスクロール → Canvas1に反映
        self._bindings.append((
            self.canvas2,
            "<Configure>",
            self.canvas2.bind("<Configure>", lambda e: self._on_scroll(self.canvas2, self.canvas1))
        ))

        # マウスホイールイベント
        self._bindings.append((
            self.canvas1,
            "<MouseWheel>",
            self.canvas1.bind("<MouseWheel>", lambda e: self._on_mousewheel(e, self.canvas1, self.canvas2))
        ))

        self._bindings.append((
            self.canvas2,
            "<MouseWheel>",
            self.canvas2.bind("<MouseWheel>", lambda e: self._on_mousewheel(e, self.canvas2, self.canvas1))
        ))

        # Linuxの場合はButton-4/Button-5も対応
        self._bindings.append((
            self.canvas1,
            "<Button-4>",
            self.canvas1.bind("<Button-4>", lambda e: self._on_mousewheel_linux(e, self.canvas1, self.canvas2, 1))
        ))

        self._bindings.append((
            self.canvas1,
            "<Button-5>",
            self.canvas1.bind("<Button-5>", lambda e: self._on_mousewheel_linux(e, self.canvas1, self.canvas2, -1))
        ))

        self._bindings.append((
            self.canvas2,
            "<Button-4>",
            self.canvas2.bind("<Button-4>", lambda e: self._on_mousewheel_linux(e, self.canvas2, self.canvas1, 1))
        ))

        self._bindings.append((
            self.canvas2,
            "<Button-5>",
            self.canvas2.bind("<Button-5>", lambda e: self._on_mousewheel_linux(e, self.canvas2, self.canvas1, -1))
        ))

    def _unbind_events(self):
        """イベントをアンバインド"""
        for canvas, event, bind_id in self._bindings:
            canvas.unbind(event, bind_id)

        self._bindings.clear()

    def _on_scroll(self, source_canvas: tk.Canvas, target_canvas: tk.Canvas):
        """
        スクロールイベントハンドラ

        Args:
            source_canvas: スクロール元
            target_canvas: スクロール先
        """
        if not self._enabled or self._syncing:
            return

        # Debounce: 短時間に複数回呼ばれるのを防ぐ
        current_time = time.time()
        if current_time - self._last_scroll_time < self.debounce_ms / 1000:
            return

        self._last_scroll_time = current_time

        # 同期実行
        self._sync_scroll(source_canvas, target_canvas)

    def _on_mousewheel(self, event, source_canvas: tk.Canvas, target_canvas: tk.Canvas):
        """
        マウスホイールイベントハンドラ

        Args:
            event: イベント
            source_canvas: スクロール元
            target_canvas: スクロール先
        """
        if not self._enabled or self._syncing:
            return

        # スクロール量を計算
        delta = 1 if event.delta < 0 else -1

        # 無限ループ防止フラグを立てる
        self._syncing = True

        try:
            # 両方のCanvasをスクロール
            source_canvas.yview_scroll(delta, "units")
            target_canvas.yview_scroll(delta, "units")

            if self.on_sync:
                self.on_sync(f"Mousewheel sync: delta={delta}")

        finally:
            self._syncing = False

    def _on_mousewheel_linux(self, event, source_canvas: tk.Canvas, target_canvas: tk.Canvas, direction: int):
        """
        Linux用マウスホイールハンドラ

        Args:
            event: イベント
            source_canvas: スクロール元
            target_canvas: スクロール先
            direction: 方向（1=up, -1=down）
        """
        if not self._enabled or self._syncing:
            return

        self._syncing = True

        try:
            source_canvas.yview_scroll(direction, "units")
            target_canvas.yview_scroll(direction, "units")

            if self.on_sync:
                self.on_sync(f"Linux mousewheel sync: dir={direction}")

        finally:
            self._syncing = False

    def _sync_scroll(self, source_canvas: tk.Canvas, target_canvas: tk.Canvas):
        """
        スクロール位置を同期

        Args:
            source_canvas: スクロール元
            target_canvas: スクロール先
        """
        if self._syncing:
            return

        self._syncing = True

        try:
            # 現在のスクロール位置を取得
            source_yview = source_canvas.yview()

            # ターゲットに反映
            target_canvas.yview_moveto(source_yview[0])

            if self.on_sync:
                self.on_sync(f"Scroll synced: {source_yview[0]:.3f}")

        except Exception as e:
            print(f"⚠️ Scroll sync error: {e}")

        finally:
            self._syncing = False

    def sync_to_position(self, position: float):
        """
        両方のCanvasを指定位置にスクロール

        Args:
            position: スクロール位置（0.0-1.0）
        """
        if not self._enabled:
            return

        self._syncing = True

        try:
            self.canvas1.yview_moveto(position)
            self.canvas2.yview_moveto(position)

            if self.on_sync:
                self.on_sync(f"Both scrolled to: {position:.3f}")

        finally:
            self._syncing = False

    def get_scroll_positions(self) -> tuple:
        """
        現在のスクロール位置を取得

        Returns:
            (canvas1_yview, canvas2_yview)
        """
        return (
            self.canvas1.yview(),
            self.canvas2.yview()
        )

    def is_in_sync(self, tolerance: float = 0.01) -> bool:
        """
        2つのCanvasが同期しているか確認

        Args:
            tolerance: 許容誤差

        Returns:
            同期している場合True
        """
        yview1 = self.canvas1.yview()
        yview2 = self.canvas2.yview()

        return abs(yview1[0] - yview2[0]) < tolerance


if __name__ == "__main__":
    # テスト
    print("=" * 60)
    print("🔗 Scroll Sync Manager Test")
    print("=" * 60)

    root = tk.Tk()
    root.title("Scroll Sync Test")
    root.geometry("800x600")

    # 2つのCanvas作成
    frame1 = tk.Frame(root)
    frame1.pack(side="left", fill="both", expand=True)

    canvas1 = tk.Canvas(frame1, bg="lightblue")
    canvas1.pack(fill="both", expand=True)

    scrollbar1 = tk.Scrollbar(frame1, command=canvas1.yview)
    scrollbar1.pack(side="right", fill="y")
    canvas1.configure(yscrollcommand=scrollbar1.set)

    frame2 = tk.Frame(root)
    frame2.pack(side="right", fill="both", expand=True)

    canvas2 = tk.Canvas(frame2, bg="lightcoral")
    canvas2.pack(fill="both", expand=True)

    scrollbar2 = tk.Scrollbar(frame2, command=canvas2.yview)
    scrollbar2.pack(side="right", fill="y")
    canvas2.configure(yscrollcommand=scrollbar2.set)

    # 大きなスクロール領域を設定
    canvas1.configure(scrollregion=(0, 0, 400, 2000))
    canvas2.configure(scrollregion=(0, 0, 400, 2000))

    # テキストを追加
    for i in range(50):
        canvas1.create_text(200, i * 40, text=f"Canvas 1 - Line {i}")
        canvas2.create_text(200, i * 40, text=f"Canvas 2 - Line {i}")

    # スクロール同期マネージャー
    sync_manager = ScrollSyncManager(
        canvas1,
        canvas2,
        debounce_ms=50,
        on_sync=lambda msg: print(f"  {msg}")
    )

    # トグルボタン
    def toggle():
        state = sync_manager.toggle()
        btn.configure(text="🔗 同期ON" if state else "🔓 同期OFF")

    btn = tk.Button(root, text="🔓 同期OFF", command=toggle)
    btn.pack(pady=10)

    sync_manager.enable()
    btn.configure(text="🔗 同期ON")

    print("\n✅ Test UI ready")
    print("=" * 60)

    root.mainloop()
