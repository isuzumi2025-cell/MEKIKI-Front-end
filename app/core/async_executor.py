"""
MEKIKI Async Executor
非同期処理ユーティリティ

Created: 2026-01-28
"""

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Optional, Any
from dataclasses import dataclass
from enum import Enum
import traceback


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """タスク結果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    traceback: Optional[str] = None


class AsyncExecutor:
    """
    非同期タスク実行マネージャー
    
    責務:
    - バックグラウンドタスク実行
    - UIスレッドへのコールバック
    - タスクキャンセル
    - エラーハンドリング
    """
    
    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._pending_futures: dict[str, Future] = {}
        self._tk_root = None
    
    def set_tk_root(self, root):
        """Tkルートウィンドウを設定 (UIスレッドコールバック用)"""
        self._tk_root = root
    
    def submit(
        self,
        task: Callable[[], Any],
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_progress: Optional[Callable[[str], None]] = None,
        task_id: Optional[str] = None
    ) -> str:
        """
        タスクをバックグラウンドで実行
        
        Args:
            task: 実行する関数
            on_complete: 完了時コールバック (UIスレッドで実行)
            on_progress: 進捗コールバック
            task_id: タスク識別子
        
        Returns:
            task_id
        """
        if task_id is None:
            task_id = f"task_{id(task)}"
        
        def wrapped_task():
            try:
                result = task()
                return TaskResult(success=True, data=result)
            except Exception as e:
                return TaskResult(
                    success=False,
                    error=str(e),
                    traceback=traceback.format_exc()
                )
        
        def on_done(future: Future):
            try:
                result = future.result()
            except Exception as e:
                result = TaskResult(success=False, error=str(e))
            
            # 完了したらリストから削除
            if task_id in self._pending_futures:
                del self._pending_futures[task_id]
            
            # UIスレッドでコールバック
            if on_complete:
                self._run_in_ui_thread(lambda: on_complete(result))
        
        future = self._executor.submit(wrapped_task)
        future.add_done_callback(on_done)
        self._pending_futures[task_id] = future
        
        return task_id
    
    def cancel(self, task_id: str) -> bool:
        """タスクをキャンセル"""
        if task_id in self._pending_futures:
            future = self._pending_futures[task_id]
            return future.cancel()
        return False
    
    def cancel_all(self):
        """全タスクをキャンセル"""
        for task_id in list(self._pending_futures.keys()):
            self.cancel(task_id)
    
    def is_running(self, task_id: str) -> bool:
        """タスクが実行中か確認"""
        if task_id in self._pending_futures:
            return not self._pending_futures[task_id].done()
        return False
    
    def _run_in_ui_thread(self, callback: Callable):
        """UIスレッドで実行"""
        if self._tk_root:
            try:
                self._tk_root.after(0, callback)
            except Exception:
                # ウィンドウが既に破棄されている場合
                pass
        else:
            # Tkルートがない場合は直接実行
            callback()
    
    def shutdown(self, wait: bool = True):
        """エグゼキュータをシャットダウン"""
        self.cancel_all()
        self._executor.shutdown(wait=wait)


# シングルトンインスタンス
_async_executor: Optional[AsyncExecutor] = None


def get_async_executor() -> AsyncExecutor:
    """AsyncExecutorシングルトン取得"""
    global _async_executor
    if _async_executor is None:
        _async_executor = AsyncExecutor()
    return _async_executor
