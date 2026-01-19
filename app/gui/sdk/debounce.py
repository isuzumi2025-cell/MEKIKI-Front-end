"""
SDK-02: デバウンスユーティリティ
リサイズ連打時の再描画抑制
"""
from typing import Callable, Dict, Optional
import tkinter as tk


class Debouncer:
    """デバウンス処理ユーティリティ"""
    
    _instances: Dict[str, 'Debouncer'] = {}
    
    def __init__(self, root: tk.Tk, delay_ms: int = 100):
        """
        Args:
            root: tkinterルート
            delay_ms: デバウンス遅延（ミリ秒）
        """
        self.root = root
        self.delay_ms = delay_ms
        self._pending: Dict[str, str] = {}  # key -> after_id
    
    def call(self, key: str, fn: Callable) -> None:
        """
        デバウンス付きで関数を実行
        
        Args:
            key: 一意のキー（同じキーの連続呼び出しは最後の1回だけ実行）
            fn: 実行する関数
        """
        # 既存の予約をキャンセル
        if key in self._pending:
            self.root.after_cancel(self._pending[key])
        
        # 新しい予約を設定
        after_id = self.root.after(self.delay_ms, fn)
        self._pending[key] = after_id
    
    def cancel(self, key: str) -> None:
        """予約をキャンセル"""
        if key in self._pending:
            self.root.after_cancel(self._pending[key])
            del self._pending[key]
    
    def cancel_all(self) -> None:
        """すべての予約をキャンセル"""
        for key, after_id in list(self._pending.items()):
            self.root.after_cancel(after_id)
        self._pending.clear()


def debounce(root: tk.Tk, key: str, delay_ms: int, fn: Callable) -> None:
    """
    グローバルデバウンス関数
    
    Args:
        root: tkinterルート
        key: 一意のキー
        delay_ms: 遅延（ミリ秒）
        fn: 実行する関数
    """
    if not hasattr(root, '_debouncer'):
        root._debouncer = Debouncer(root, delay_ms)
    
    # 遅延が異なる場合は更新
    if root._debouncer.delay_ms != delay_ms:
        root._debouncer.delay_ms = delay_ms
    
    root._debouncer.call(key, fn)
