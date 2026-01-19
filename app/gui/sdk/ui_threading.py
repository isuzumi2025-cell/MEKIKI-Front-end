"""
SDK-01: UIスレッド安全更新ユーティリティ
Safe Telemetry & UI Threading 2.0準拠
"""
import threading
from typing import Callable, Optional, Any
import tkinter as tk


def run_bg(
    task_fn: Callable[[], Any],
    on_success: Callable[[Any], None] = None,
    on_error: Callable[[Exception], None] = None,
    root: Optional[tk.Tk] = None
) -> None:
    """
    バックグラウンドでタスクを実行し、結果をUIスレッドに安全に反映
    
    Args:
        task_fn: バックグラウンドで実行する関数
        on_success: 成功時にUIスレッドで呼ばれるコールバック
        on_error: エラー時にUIスレッドで呼ばれるコールバック
        root: tkinterルート（afterで使用）
    """
    def worker():
        try:
            result = task_fn()
            if on_success and root:
                root.after(0, lambda: on_success(result))
            elif on_success:
                on_success(result)
        except Exception as e:
            if on_error and root:
                root.after(0, lambda: on_error(e))
            elif on_error:
                on_error(e)
            else:
                print(f"[run_bg] Error: {e}")
    
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


def ui_call(root: tk.Tk, fn: Callable, delay_ms: int = 0) -> None:
    """
    UIスレッドで安全に関数を実行
    
    Args:
        root: tkinterルート
        fn: 実行する関数
        delay_ms: 遅延（ミリ秒）
    """
    root.after(delay_ms, fn)


class UIUpdater:
    """UIスレッド安全な更新ヘルパー"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self._is_updating = False
    
    def update(self, fn: Callable) -> None:
        """UIスレッドで関数を実行"""
        self.root.after(0, fn)
    
    def delayed_update(self, fn: Callable, delay_ms: int) -> None:
        """遅延実行"""
        self.root.after(delay_ms, fn)
    
    def set_loading(self, widget, is_loading: bool, text: str = None):
        """ウィジェットのローディング状態を設定"""
        if is_loading:
            widget.configure(state="disabled")
            if text:
                widget.configure(text=text)
        else:
            widget.configure(state="normal")
            if text:
                widget.configure(text=text)
