"""
開発用ログ設定
デバッグ時の情報を詳細に出力
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

# ログディレクトリ
LOG_DIR = Path(__file__).parent.parent / "logs"

def setup_dev_logging(
    level: str = "DEBUG",
    to_file: bool = True,
    to_console: bool = True
):
    """
    開発用ログ設定
    
    Args:
        level: ログレベル (DEBUG, INFO, WARNING, ERROR)
        to_file: ファイルに出力するか
        to_console: コンソールに出力するか
    """
    LOG_DIR.mkdir(exist_ok=True)
    
    # フォーマット
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))
    
    # 既存ハンドラをクリア
    root_logger.handlers.clear()
    
    # コンソールハンドラ
    if to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # ファイルハンドラ
    if to_file:
        log_file = LOG_DIR / f"dev_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        print(f"📝 Log file: {log_file}")
    
    # 特定モジュールのログレベル調整
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """モジュール用ロガー取得"""
    return logging.getLogger(name)


# アプリ起動時に呼び出し
def init_logging():
    """アプリ起動時のログ初期化"""
    import os
    level = "DEBUG" if os.environ.get("MEKIKI_DEBUG") else "INFO"
    setup_dev_logging(level=level)
