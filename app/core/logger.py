"""
Structured Logger for MEKIKI OCR

業務配布用のログ管理システム:
- ローテーション対応（10MB、5世代）
- 構造化ログ（JSON形式）
- エラーコンテキスト保持
- 診断バンドル生成

Usage:
    from app.core.logger import get_logger

    logger = get_logger(__name__)
    logger.info("OCR処理開始", extra={'file': 'test.pdf'})
    logger.error("APIエラー", exc_info=True)
"""

import logging
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from logging.handlers import RotatingFileHandler
import traceback


# ログディレクトリ
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ログファイルパス
MAIN_LOG_FILE = LOG_DIR / "mekiki.log"
ERROR_LOG_FILE = LOG_DIR / "mekiki_error.log"
DIAGNOSTIC_LOG_FILE = LOG_DIR / "diagnostic.log"


class StructuredFormatter(logging.Formatter):
    """構造化ログフォーマッター（JSON形式）"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # 追加のコンテキスト情報
        if hasattr(record, 'extra_context'):
            log_data['context'] = record.extra_context

        # エラーコード
        if hasattr(record, 'error_code'):
            log_data['error_code'] = record.error_code

        # 例外情報
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }

        return json.dumps(log_data, ensure_ascii=False, indent=None)


class HumanReadableFormatter(logging.Formatter):
    """人間が読みやすいログフォーマッター"""

    # ログレベルの色付け（Windows対応）
    LEVEL_COLORS = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🔥'
    }

    def format(self, record: logging.LogRecord) -> str:
        emoji = self.LEVEL_COLORS.get(record.levelname, '📝')
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')

        # ベースメッセージ
        message = f"[{timestamp}] {emoji} {record.levelname} - {record.name} - {record.getMessage()}"

        # コンテキスト情報
        if hasattr(record, 'extra_context'):
            context_str = json.dumps(record.extra_context, ensure_ascii=False)
            message += f"\n  📋 Context: {context_str}"

        # エラーコード
        if hasattr(record, 'error_code'):
            message += f"\n  🔖 Error Code: {record.error_code}"

        # 例外情報
        if record.exc_info:
            message += f"\n  📍 {record.pathname}:{record.lineno}"
            message += "\n" + self.formatException(record.exc_info)

        return message


class MekikiLogger:
    """
    MEKIKI OCR用のカスタムロガー

    Features:
    - 自動ローテーション（10MB、5世代）
    - 構造化ログ（JSON）+ 人間向けフォーマット
    - エラーログの分離
    - 診断バンドル生成
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 重複ハンドラー防止
        if self.logger.handlers:
            return

        # 1. コンソールハンドラー（人間向けフォーマット）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(HumanReadableFormatter())
        self.logger.addHandler(console_handler)

        # 2. メインログファイル（全レベル、構造化JSON）
        main_handler = RotatingFileHandler(
            MAIN_LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(main_handler)

        # 3. エラーログファイル（ERROR以上のみ、人間向けフォーマット）
        error_handler = RotatingFileHandler(
            ERROR_LOG_FILE,
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(HumanReadableFormatter())
        self.logger.addHandler(error_handler)

        # 診断モードフラグ
        self._diagnostic_mode = False

    def debug(self, message: str, **kwargs):
        """DEBUGレベルログ"""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """INFOレベルログ"""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """WARNINGレベルログ"""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs):
        """ERRORレベルログ"""
        self._log(logging.ERROR, message, exc_info=exc_info, **kwargs)

    def critical(self, message: str, exc_info: bool = True, **kwargs):
        """CRITICALレベルログ"""
        self._log(logging.CRITICAL, message, exc_info=exc_info, **kwargs)

    def _log(self, level: int, message: str, exc_info: bool = False, **kwargs):
        """内部ログメソッド"""
        extra = {}

        # コンテキスト情報
        if 'context' in kwargs:
            extra['extra_context'] = kwargs['context']

        # エラーコード
        if 'error_code' in kwargs:
            extra['error_code'] = kwargs['error_code']

        self.logger.log(level, message, exc_info=exc_info, extra=extra)

    def log_exception(self, exc: Exception, context: Optional[Dict[str, Any]] = None):
        """
        例外をログに記録（MekikiException対応）

        Args:
            exc: 例外オブジェクト
            context: 追加のコンテキスト情報
        """
        from app.core.exceptions import MekikiException

        error_data = {'exception_type': type(exc).__name__}

        if isinstance(exc, MekikiException):
            # カスタム例外の場合
            error_data.update({
                'error_code': exc.error_code.value,
                'message': exc.message,
                'context': exc.context,
                'recoverable': exc.recoverable,
                'recovery_suggestion': exc.recovery_suggestion
            })
        else:
            # 標準例外の場合
            error_data['message'] = str(exc)

        if context:
            error_data.setdefault('context', {}).update(context)

        self.error(
            f"Exception occurred: {error_data['message']}",
            exc_info=True,
            context=error_data
        )

    def enable_diagnostic_mode(self):
        """診断モード有効化（詳細ログ出力）"""
        self._diagnostic_mode = True

        # 診断ログハンドラー追加
        if not any(isinstance(h, RotatingFileHandler) and h.baseFilename == str(DIAGNOSTIC_LOG_FILE)
                   for h in self.logger.handlers):
            diagnostic_handler = RotatingFileHandler(
                DIAGNOSTIC_LOG_FILE,
                maxBytes=50 * 1024 * 1024,  # 50MB
                backupCount=2,
                encoding='utf-8'
            )
            diagnostic_handler.setLevel(logging.DEBUG)
            diagnostic_handler.setFormatter(HumanReadableFormatter())
            self.logger.addHandler(diagnostic_handler)

        self.info("診断モード有効化")

    def generate_diagnostic_bundle(self, output_path: Optional[Path] = None) -> Path:
        """
        診断バンドル生成（サポート用）

        Args:
            output_path: 出力先パス（省略時は自動生成）

        Returns:
            生成されたZIPファイルのパス
        """
        import zipfile
        import platform
        from datetime import datetime

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = LOG_DIR / f"diagnostic_bundle_{timestamp}.zip"

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # ログファイル
            for log_file in [MAIN_LOG_FILE, ERROR_LOG_FILE, DIAGNOSTIC_LOG_FILE]:
                if log_file.exists():
                    zipf.write(log_file, arcname=log_file.name)

            # システム情報
            system_info = {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'architecture': platform.machine(),
                'timestamp': datetime.now().isoformat()
            }
            zipf.writestr('system_info.json', json.dumps(system_info, indent=2))

        self.info(f"診断バンドル生成: {output_path}")
        return output_path


# グローバルロガー管理
_loggers: Dict[str, MekikiLogger] = {}


def get_logger(name: str) -> MekikiLogger:
    """
    ロガー取得（シングルトンパターン）

    Args:
        name: ロガー名（通常は __name__）

    Returns:
        MekikiLoggerインスタンス
    """
    if name not in _loggers:
        _loggers[name] = MekikiLogger(name)
    return _loggers[name]


def enable_all_diagnostic_mode():
    """すべてのロガーの診断モードを有効化"""
    for logger in _loggers.values():
        logger.enable_diagnostic_mode()


if __name__ == "__main__":
    # テスト
    print("=" * 60)
    print("🧪 Structured Logger Test")
    print("=" * 60)

    logger = get_logger("test_module")

    logger.debug("デバッグメッセージ", context={'key': 'value'})
    logger.info("情報メッセージ", context={'user': 'test_user'})
    logger.warning("警告メッセージ")
    logger.error("エラーメッセージ", error_code="E1001")

    # 例外ログテスト
    try:
        raise ValueError("テスト例外")
    except Exception as e:
        logger.log_exception(e, context={'operation': 'test'})

    # カスタム例外テスト
    from app.core.exceptions import OCRError, ErrorCode
    try:
        raise OCRError(
            "OCRタイムアウト",
            ErrorCode.OCR_TIMEOUT,
            context={'timeout_sec': 30}
        )
    except OCRError as e:
        logger.log_exception(e)

    # 診断バンドル生成テスト
    logger.enable_diagnostic_mode()
    bundle_path = logger.generate_diagnostic_bundle()
    print(f"\n✅ 診断バンドル: {bundle_path}")

    print("\n" + "=" * 60)
    print(f"📁 ログファイル:")
    print(f"   Main: {MAIN_LOG_FILE}")
    print(f"   Error: {ERROR_LOG_FILE}")
    print(f"   Diagnostic: {DIAGNOSTIC_LOG_FILE}")
    print("=" * 60)
