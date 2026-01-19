"""
Custom Exception Hierarchy for MEKIKI OCR

業務配布用のエラー管理システム:
- エラーコードによる分類
- コンテキスト情報の保持
- ユーザー向けメッセージとログ用メッセージの分離
- 復旧オプションの提供

Usage:
    from app.core.exceptions import OCRError, ErrorCode

    raise OCRError(
        message="Gemini APIがタイムアウトしました",
        error_code=ErrorCode.API_TIMEOUT,
        context={'model': 'gemini-2.0-flash', 'timeout': 30}
    )
"""

from enum import Enum
from typing import Dict, Any, Optional


class ErrorCode(Enum):
    """エラーコード定義"""
    # API関連エラー (1xxx)
    API_TIMEOUT = "E1001"
    API_RATE_LIMITED = "E1002"
    API_AUTH_FAILED = "E1003"
    API_INVALID_KEY = "E1004"
    API_QUOTA_EXCEEDED = "E1005"
    API_NETWORK_ERROR = "E1006"
    API_CONTENT_POLICY = "E1007"

    # OCR関連エラー (2xxx)
    OCR_TIMEOUT = "E2001"
    OCR_INVALID_IMAGE = "E2002"
    OCR_EXTRACTION_FAILED = "E2003"
    OCR_ENGINE_UNAVAILABLE = "E2004"
    OCR_UNSUPPORTED_FORMAT = "E2005"

    # ファイルI/O関連エラー (3xxx)
    FILE_NOT_FOUND = "E3001"
    FILE_PERMISSION_DENIED = "E3002"
    FILE_CORRUPTED = "E3003"
    FILE_TOO_LARGE = "E3004"
    FILE_LOCK_FAILED = "E3005"

    # UI/Widget関連エラー (4xxx)
    WIDGET_DESTROYED = "E4001"
    WIDGET_NOT_FOUND = "E4002"
    UI_UPDATE_FAILED = "E4003"
    RENDER_ERROR = "E4004"

    # メモリ/リソース関連エラー (5xxx)
    MEMORY_EXHAUSTED = "E5001"
    RESOURCE_LEAK = "E5002"
    THREAD_DEADLOCK = "E5003"

    # 設定/初期化関連エラー (6xxx)
    CONFIG_MISSING = "E6001"
    CONFIG_INVALID = "E6002"
    INITIALIZATION_FAILED = "E6003"

    # その他 (9xxx)
    UNKNOWN_ERROR = "E9999"


class MekikiException(Exception):
    """
    MEKIKI OCRベース例外クラス

    すべてのカスタム例外の基底クラス
    エラーコード、コンテキスト情報、復旧提案を含む

    Attributes:
        message: ユーザー向けエラーメッセージ（日本語）
        error_code: エラーコード（ErrorCode enum）
        context: エラー発生時のコンテキスト情報
        recoverable: 復旧可能かどうか
        recovery_suggestion: 復旧方法の提案
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
        recovery_suggestion: str = ""
    ):
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.recoverable = recoverable
        self.recovery_suggestion = recovery_suggestion
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """例外情報を辞書に変換（ログ用）"""
        return {
            'error_code': self.error_code.value,
            'message': self.message,
            'context': self.context,
            'recoverable': self.recoverable,
            'recovery_suggestion': self.recovery_suggestion,
            'exception_type': self.__class__.__name__
        }

    def __str__(self) -> str:
        return f"[{self.error_code.value}] {self.message}"


class OCRError(MekikiException):
    """OCR処理関連のエラー"""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.OCR_EXTRACTION_FAILED,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
        recovery_suggestion: str = ""
    ):
        if not recovery_suggestion:
            recovery_suggestion = "別のOCRエンジンを試すか、画像の品質を確認してください。"
        super().__init__(message, error_code, context, recoverable, recovery_suggestion)


class APIError(MekikiException):
    """外部API関連のエラー"""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.API_NETWORK_ERROR,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
        recovery_suggestion: str = ""
    ):
        if not recovery_suggestion:
            if error_code == ErrorCode.API_TIMEOUT:
                recovery_suggestion = "ネットワーク接続を確認し、再試行してください。"
            elif error_code == ErrorCode.API_RATE_LIMITED:
                recovery_suggestion = "しばらく待ってから再試行してください（1分後）。"
            elif error_code == ErrorCode.API_INVALID_KEY:
                recovery_suggestion = "APIキー設定を確認してください（設定 → API設定）。"
            elif error_code == ErrorCode.API_QUOTA_EXCEEDED:
                recovery_suggestion = "APIの利用上限に達しました。料金プランを確認してください。"
            else:
                recovery_suggestion = "ネットワーク接続とAPI設定を確認してください。"

        super().__init__(message, error_code, context, recoverable, recovery_suggestion)


class FileIOError(MekikiException):
    """ファイルI/O関連のエラー"""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.FILE_NOT_FOUND,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
        recovery_suggestion: str = ""
    ):
        if not recovery_suggestion:
            if error_code == ErrorCode.FILE_NOT_FOUND:
                recovery_suggestion = "ファイルパスが正しいか確認してください。"
            elif error_code == ErrorCode.FILE_PERMISSION_DENIED:
                recovery_suggestion = "ファイルの読み書き権限を確認してください。"
            elif error_code == ErrorCode.FILE_CORRUPTED:
                recovery_suggestion = "ファイルが破損している可能性があります。別のファイルをお試しください。"
            else:
                recovery_suggestion = "ファイルパスとアクセス権限を確認してください。"

        super().__init__(message, error_code, context, recoverable, recovery_suggestion)


class UIError(MekikiException):
    """UI/Widget関連のエラー"""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UI_UPDATE_FAILED,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
        recovery_suggestion: str = ""
    ):
        if not recovery_suggestion:
            recovery_suggestion = "画面を再読み込みしてください。"

        super().__init__(message, error_code, context, recoverable, recovery_suggestion)


class ResourceError(MekikiException):
    """メモリ/リソース関連のエラー"""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.MEMORY_EXHAUSTED,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = False,
        recovery_suggestion: str = ""
    ):
        if not recovery_suggestion:
            if error_code == ErrorCode.MEMORY_EXHAUSTED:
                recovery_suggestion = "メモリ不足です。他のアプリケーションを閉じて再試行してください。"
            else:
                recovery_suggestion = "システムリソースを確認してください。"

        super().__init__(message, error_code, context, recoverable, recovery_suggestion)


class ConfigError(MekikiException):
    """設定/初期化関連のエラー"""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.CONFIG_INVALID,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
        recovery_suggestion: str = ""
    ):
        if not recovery_suggestion:
            recovery_suggestion = "設定ファイルを確認するか、デフォルト設定にリセットしてください。"

        super().__init__(message, error_code, context, recoverable, recovery_suggestion)


# ユーティリティ関数
def wrap_exception(exc: Exception, context: Optional[Dict[str, Any]] = None) -> MekikiException:
    """
    標準例外をMekikiExceptionにラップ

    Args:
        exc: 元の例外
        context: 追加のコンテキスト情報

    Returns:
        ラップされたMekikiException
    """
    context = context or {}
    context['original_type'] = type(exc).__name__
    context['original_message'] = str(exc)

    # 例外タイプに基づいて適切なMekikiExceptionに変換
    if isinstance(exc, FileNotFoundError):
        return FileIOError(
            f"ファイルが見つかりません: {exc}",
            ErrorCode.FILE_NOT_FOUND,
            context
        )
    elif isinstance(exc, PermissionError):
        return FileIOError(
            f"ファイルアクセス権限がありません: {exc}",
            ErrorCode.FILE_PERMISSION_DENIED,
            context
        )
    elif isinstance(exc, MemoryError):
        return ResourceError(
            "メモリ不足が発生しました",
            ErrorCode.MEMORY_EXHAUSTED,
            context,
            recoverable=False
        )
    elif isinstance(exc, TimeoutError):
        return APIError(
            f"タイムアウトが発生しました: {exc}",
            ErrorCode.API_TIMEOUT,
            context
        )
    else:
        # 不明な例外
        return MekikiException(
            f"予期しないエラーが発生しました: {exc}",
            ErrorCode.UNKNOWN_ERROR,
            context,
            recoverable=False
        )


if __name__ == "__main__":
    # テスト
    print("=" * 60)
    print("🧪 Custom Exception Test")
    print("=" * 60)

    # OCRエラーのテスト
    try:
        raise OCRError(
            "Gemini APIがタイムアウトしました",
            ErrorCode.OCR_TIMEOUT,
            context={'model': 'gemini-2.0-flash', 'timeout_sec': 30}
        )
    except OCRError as e:
        print(f"\n✅ OCRError caught:")
        print(f"   Code: {e.error_code.value}")
        print(f"   Message: {e.message}")
        print(f"   Context: {e.context}")
        print(f"   Recovery: {e.recovery_suggestion}")
        print(f"   Dict: {e.to_dict()}")

    # APIエラーのテスト
    try:
        raise APIError(
            "APIキーが無効です",
            ErrorCode.API_INVALID_KEY,
            context={'api_name': 'Gemini'}
        )
    except APIError as e:
        print(f"\n✅ APIError caught:")
        print(f"   {e}")
        print(f"   Recovery: {e.recovery_suggestion}")

    # ラップテスト
    try:
        open("/nonexistent/file.txt")
    except Exception as e:
        wrapped = wrap_exception(e, {'operation': 'test_open'})
        print(f"\n✅ Wrapped exception:")
        print(f"   {wrapped}")
        print(f"   Original: {wrapped.context['original_type']}")

    print("\n" + "=" * 60)
