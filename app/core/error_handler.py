"""
Error Handler Decorators and Context Managers

業務配布用の統一エラーハンドリング:
- デコレーターによる自動エラー処理
- コンテキストマネージャーによるリソース管理
- 自動ログ記録とユーザー通知
- リトライロジック

Usage:
    from app.core.error_handler import handle_errors, safe_operation

    @handle_errors(notify_user=True, retry_count=3)
    def process_ocr(image_path):
        # ... OCR processing
        pass

    # Or as context manager:
    with safe_operation("OCR Processing", notify_user=True):
        # ... OCR processing
        pass
"""

from functools import wraps
from contextlib import contextmanager
from typing import Callable, Optional, Any
import time
import traceback

from app.core.exceptions import (
    MekikiException,
    OCRError,
    APIError,
    FileIOError,
    UIError,
    ResourceError,
    ErrorCode,
    wrap_exception
)
from app.core.logger import get_logger


logger = get_logger(__name__)


def handle_errors(
    error_type: type = Exception,
    fallback_return: Any = None,
    notify_user: bool = False,
    retry_count: int = 0,
    retry_delay: float = 1.0,
    retry_backoff: float = 2.0,
    log_level: str = "error",
    operation_name: str = ""
):
    """
    エラーハンドリングデコレーター

    Args:
        error_type: キャッチする例外タイプ
        fallback_return: エラー時の戻り値
        notify_user: ユーザーに通知するか
        retry_count: リトライ回数（0=リトライなし）
        retry_delay: 初回リトライ待機時間（秒）
        retry_backoff: リトライごとの待機時間倍率
        log_level: ログレベル（"debug", "info", "warning", "error", "critical"）
        operation_name: 操作名（ログ用）

    Returns:
        デコレータ関数

    Example:
        @handle_errors(notify_user=True, retry_count=3)
        def fetch_data():
            # ... fetch logic
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            operation = operation_name or func.__name__
            last_exception = None
            delay = retry_delay

            for attempt in range(retry_count + 1):
                try:
                    logger.debug(f"Executing {operation} (attempt {attempt + 1}/{retry_count + 1})")
                    result = func(*args, **kwargs)

                    # リトライ成功時
                    if attempt > 0:
                        logger.info(f"{operation} succeeded after {attempt + 1} attempts")

                    return result

                except error_type as e:
                    last_exception = e

                    # MekikiException以外はラップ
                    if not isinstance(e, MekikiException):
                        e = wrap_exception(e, {'operation': operation, 'attempt': attempt + 1})

                    # ログ記録
                    log_method = getattr(logger, log_level, logger.error)
                    log_method(
                        f"{operation} failed (attempt {attempt + 1}/{retry_count + 1}): {e.message if isinstance(e, MekikiException) else str(e)}",
                        exc_info=True,
                        context={'operation': operation, 'attempt': attempt + 1}
                    )

                    # リトライ判定
                    if attempt < retry_count:
                        # リトライ可能なエラーかチェック
                        if isinstance(e, MekikiException):
                            if not e.recoverable:
                                logger.warning(f"{operation} error is not recoverable, skipping retry")
                                break

                            # レート制限の場合は長めに待つ
                            if e.error_code == ErrorCode.API_RATE_LIMITED:
                                delay = 60.0  # 1分待機
                                logger.info(f"Rate limited, waiting {delay} seconds before retry")

                        logger.info(f"Retrying in {delay:.1f} seconds...")
                        time.sleep(delay)
                        delay *= retry_backoff  # 指数バックオフ
                    else:
                        # 最終試行失敗
                        break

            # すべてのリトライ失敗
            if last_exception:
                if notify_user:
                    _notify_user_error(last_exception)

                if isinstance(last_exception, MekikiException):
                    logger.error(
                        f"{operation} failed after {retry_count + 1} attempts: {last_exception.message}",
                        context=last_exception.to_dict()
                    )
                else:
                    logger.error(f"{operation} failed after {retry_count + 1} attempts: {last_exception}")

            return fallback_return

        return wrapper
    return decorator


@contextmanager
def safe_operation(
    operation_name: str,
    notify_user: bool = False,
    log_errors: bool = True,
    cleanup_callback: Optional[Callable] = None
):
    """
    安全な操作コンテキストマネージャー

    リソース管理と例外処理を統合

    Args:
        operation_name: 操作名
        notify_user: ユーザーに通知するか
        log_errors: エラーをログに記録するか
        cleanup_callback: クリーンアップコールバック

    Yields:
        None

    Example:
        with safe_operation("Database Transaction", notify_user=True):
            # ... database operations
            pass
    """
    logger.debug(f"Starting operation: {operation_name}")

    try:
        yield

        logger.debug(f"Operation completed: {operation_name}")

    except MekikiException as e:
        if log_errors:
            logger.error(
                f"Operation failed: {operation_name} - {e.message}",
                exc_info=True,
                context=e.to_dict()
            )

        if notify_user:
            _notify_user_error(e)

        raise

    except Exception as e:
        # 標準例外をラップ
        wrapped = wrap_exception(e, {'operation': operation_name})

        if log_errors:
            logger.error(
                f"Operation failed: {operation_name} - {wrapped.message}",
                exc_info=True,
                context=wrapped.to_dict()
            )

        if notify_user:
            _notify_user_error(wrapped)

        raise wrapped

    finally:
        # クリーンアップ
        if cleanup_callback:
            try:
                logger.debug(f"Running cleanup for: {operation_name}")
                cleanup_callback()
            except Exception as cleanup_error:
                logger.warning(
                    f"Cleanup failed for {operation_name}: {cleanup_error}",
                    exc_info=True
                )


def _notify_user_error(exception: Exception):
    """
    ユーザーにエラーを通知（GUIスレッドセーフ）

    Args:
        exception: 例外オブジェクト
    """
    try:
        import tkinter as tk
        from app.gui.dialogs.error_dialog import show_error_dialog

        # GUIスレッドで実行されているか確認
        root = tk._default_root
        if root:
            # メインスレッドで実行
            root.after(0, lambda: show_error_dialog(root, exception))
        else:
            # GUIが利用不可の場合はコンソールに表示
            logger.warning("GUI not available, printing error to console")
            print(f"\n❌ ERROR: {exception}")
            if isinstance(exception, MekikiException):
                print(f"   Code: {exception.error_code.value}")
                print(f"   Recovery: {exception.recovery_suggestion}")

    except Exception as e:
        logger.error(f"Failed to notify user: {e}", exc_info=True)


# リトライ専用デコレーター（簡易版）
def retry_on_failure(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    リトライ専用デコレーター（通知なし、ログのみ）

    Args:
        max_attempts: 最大試行回数
        delay: 初回待機時間（秒）
        backoff: 待機時間倍率

    Example:
        @retry_on_failure(max_attempts=3)
        def unstable_api_call():
            # ... API call
            pass
    """
    return handle_errors(
        retry_count=max_attempts - 1,
        retry_delay=delay,
        retry_backoff=backoff,
        notify_user=False,
        log_level="warning"
    )


# ログのみ（例外を再送出）
def log_errors(operation_name: str = ""):
    """
    エラーログ専用デコレーター（例外を再送出）

    Args:
        operation_name: 操作名

    Example:
        @log_errors("Data Processing")
        def process_data():
            # ... processing
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            operation = operation_name or func.__name__

            try:
                return func(*args, **kwargs)
            except Exception as e:
                # ログ記録のみ
                if isinstance(e, MekikiException):
                    logger.error(
                        f"{operation} failed: {e.message}",
                        exc_info=True,
                        context=e.to_dict()
                    )
                else:
                    logger.error(
                        f"{operation} failed: {e}",
                        exc_info=True
                    )
                raise  # 例外を再送出

        return wrapper
    return decorator


if __name__ == "__main__":
    # テスト
    print("=" * 60)
    print("🧪 Error Handler Test")
    print("=" * 60)

    # リトライテスト
    attempt_counter = 0

    @handle_errors(retry_count=3, retry_delay=0.5, retry_backoff=1.5)
    def unstable_function():
        global attempt_counter
        attempt_counter += 1
        if attempt_counter < 3:
            raise APIError("APIタイムアウト", ErrorCode.API_TIMEOUT)
        return "Success!"

    print("\n1. Retry Test:")
    result = unstable_function()
    print(f"   Result: {result}")

    # コンテキストマネージャーテスト
    print("\n2. Context Manager Test:")

    cleanup_called = False

    def cleanup():
        global cleanup_called
        cleanup_called = True
        print("   Cleanup executed")

    try:
        with safe_operation("Test Operation", cleanup_callback=cleanup):
            print("   Inside context")
            raise FileIOError("ファイルが見つかりません", ErrorCode.FILE_NOT_FOUND)
    except MekikiException as e:
        print(f"   Caught: {e.error_code.value} - {e.message}")

    print(f"   Cleanup called: {cleanup_called}")

    # フォールバック戻り値テスト
    print("\n3. Fallback Return Test:")

    @handle_errors(fallback_return="default_value")
    def failing_function():
        raise ValueError("Always fails")

    result = failing_function()
    print(f"   Fallback result: {result}")

    print("\n" + "=" * 60)
